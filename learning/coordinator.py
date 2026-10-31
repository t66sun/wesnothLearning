"""Isolated trainer processes; one shared, fair pool of native game workers."""
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import get_context
from pathlib import Path
from queue import Empty
import json
import time
import traceback
from .common import ROOT, read_json, repair_tail, sha256, write_json
from .formats import FORMATS
from .branch import prepare as prepare_branch
from .manifest import output_path, freeze, verify_frozen
from .experiment import FormatExperiment, default_config, validate_config, run_lock
from .export import export_checkpoints
from .sample import play_job


class FairScheduler:
    def __init__(self,formats):
        self.order=deque(formats);self.pending={f:deque() for f in formats}

    def add(self,fmt,jobs): self.pending[fmt].extend(jobs)

    def pop(self):
        for _ in range(len(self.order)):
            fmt=self.order[0];self.order.rotate(-1)
            if self.pending[fmt]: return fmt,self.pending[fmt].popleft()
        return None


def limit_memory(gigabytes):
    """Cap trainer address space so a runaway read fails inside the trainer.

    The kernel then raises MemoryError, the trainer records its traceback and the
    coordinator reports a partial failure instead of an OOM kill of the run.
    """
    if not gigabytes: return None
    try:
        import resource
        budget=int(float(gigabytes)*1024**3)
        soft,hard=resource.getrlimit(resource.RLIMIT_AS)
        if hard!=resource.RLIM_INFINITY: budget=min(budget,hard)
        resource.setrlimit(resource.RLIMIT_AS,(budget,budget))
        return budget
    except (ImportError,ValueError,OSError):
        return None


def trainer_main(directory,fmt,manifest,clock,requests,replies,resume,branch=False):
    limit_memory(manifest.get('config',{}).get('trainer_memory_gb'))
    def collect(jobs,log):
        requests.put((fmt,jobs,str(log)))
        reply=replies.get()
        if reply.get('error'): raise RuntimeError(reply['error'])
        return reply['results']
    try: FormatExperiment(directory,fmt,manifest,clock,collect,resume,branch=branch).run()
    except BaseException:
        Path(directory).mkdir(parents=True,exist_ok=True)
        Path(directory,'trainer_error.log').write_text(traceback.format_exc(),encoding='utf-8')
        raise


def broker(processes,requests,replies,workers,directory,play=play_job):
    """At most workers submitted games across all trainers, round robin by format."""
    if not 1<=workers<=16: raise ValueError('workers must be in [1,16]')
    scheduler=FairScheduler(processes);batches={};inflight={};peak=0
    events=Path(directory)/'scheduler.jsonl';repaired=set()
    def emit(row):
        with events.open('a',encoding='utf-8') as f: f.write(json.dumps(dict(time=time.time(),**row))+'\n')
    def complete(fmt,job,result):
        batch=batches[fmt];batch['results'].append(result)
        log=Path(batch['log'])
        if log not in repaired:
            repaired.add(log)
            log.parent.mkdir(parents=True,exist_ok=True)
            repair_tail(log)
        with log.open('a',encoding='utf-8') as f: f.write(json.dumps(result,ensure_ascii=False)+'\n')
        batch['remaining']-=1
        if batch['remaining']==0:
            replies[fmt].put(dict(results=batch['results']));del batches[fmt]
    exits=Path(directory)/'trainer_exit.log';reported=set()
    with ProcessPoolExecutor(max_workers=workers,mp_context=get_context('spawn')) as pool:
        while any(p.is_alive() for p in processes.values()) or inflight or batches:
            try:
                while True:
                    fmt,jobs,log=requests.get_nowait()
                    if fmt in batches: raise RuntimeError('overlapping trainer batches')
                    if not jobs: replies[fmt].put(dict(results=[]));continue
                    batches[fmt]=dict(remaining=len(jobs),results=[],log=log);scheduler.add(fmt,jobs)
            except Empty: pass
            for fmt,p in processes.items():
                if not p.is_alive() and p.exitcode not in (None,0) and fmt not in reported:
                    reported.add(fmt)
                    with exits.open('a',encoding='utf-8') as f:
                        f.write(json.dumps(dict(time=time.time(),format=fmt,exit_code=p.exitcode))+ '\n')
                if not p.is_alive() and fmt in batches:
                    while scheduler.pending[fmt]:
                        job=scheduler.pending[fmt].popleft();complete(fmt,job,dict(id=job['id'],status='trainer_failed'))
            while len(inflight)<workers:
                item=scheduler.pop()
                if item is None: break
                fmt,job=item
                if time.time()>=job['deadline']:
                    complete(fmt,job,dict(id=job['id'],status='budget_interrupted'));continue
                inflight[pool.submit(play,job)]=(fmt,job)
                peak=max(peak,len(inflight));emit(dict(event='start',format=fmt,id=job['id'],active=len(inflight)))
            done=[f for f in inflight if f.done()]
            for future in done:
                fmt,job=inflight.pop(future)
                try: result=future.result()
                except Exception as exc: result=dict(id=job['id'],status='infrastructure_error',error=repr(exc))
                complete(fmt,job,result);emit(dict(event='finish',format=fmt,id=job['id'],active=len(inflight)))
            if not done: time.sleep(.02)
    return dict(workers=workers,peak_native_games=peak,exit_codes={f:p.exitcode for f,p in processes.items()})


class Experiment:
    def __init__(self,directory,config=None,opponents=None,wesnoth=None,resume=False,branch_from=None):
        self.directory=output_path(directory);self.resume=resume;self.branch_from=branch_from
        if resume:
            self.manifest=read_json(self.directory/'manifest.json')
            self.config=self.manifest['config']
            from .features import select_rules
            select_rules(self.config.get('rules_dir',ROOT/'data/rules/1.18.8'))
            verify_frozen(self.manifest)
            self.clock=read_json(self.directory/'clock.json')
        elif branch_from:
            source=Path(branch_from).resolve()
            parent=read_json(source/'manifest.json');parent_clock=read_json(source/'clock.json')
            requested=dict(config or {})
            self.config=default_config(requested.get('device','cuda'),engine=requested.get('engine'))|requested
            validate_config(self.config)
            from .features import select_rules
            from .rules_catalog import load, resolve_dir
            self.config['rules_dir']=str(resolve_dir(self.config.get('rules_dir')))
            if self.config['engine']!=parent['config']['engine']:
                raise ValueError('branch must keep the parent engine')
            if set(self.config['formats'])!=set(parent['config']['formats']):
                raise ValueError('branch must keep the parent formats')
            select_rules(self.config['rules_dir']);load(self.config['rules_dir'])
            self.directory.mkdir(parents=True,exist_ok=False)
            opponents_dir=source/'frozen/opponents'
            self.manifest,_=freeze(self.directory,opponents_dir if opponents_dir.exists() else (opponents or ROOT/'data/opponents'),
                parent.get('baseline',{}).get('path') or wesnoth,self.config)
            if self.manifest['rules']!=parent['rules']:
                raise ValueError('branch rules differ from the parent')
            started=time.time();duration=self.config['hours']*3600
            self.clock=dict(started=started,update_deadline=started+duration*10/12,deadline=started+duration)
            records=prepare_branch(source,self.directory,self.config['formats'],seed=self.config['seed'],
                reset_optimizer=bool(self.config.get('branch_reset_optimizer')),clock=parent_clock)
            records.update(parent=str(source),parent_manifest_sha256=sha256(source/'manifest.json'),
                parent_clock=parent_clock)
            write_json(self.directory/'branch.json',records)
            write_json(self.directory/'clock.json',self.clock)
        else:
            requested=dict(config or {})
            self.config=default_config(requested.get('device','cuda'),engine=requested.get('engine'))|requested;validate_config(self.config)
            from .features import select_rules
            from .rules_catalog import load, resolve_dir
            self.config['rules_dir']=str(resolve_dir(self.config.get('rules_dir')))
            select_rules(self.config['rules_dir'])
            load(self.config['rules_dir'])
            if self.config['engine']=='lite' and not self.config['allow_approximate']:
                raise ValueError('training rules contain documented approximations; enable allow_approximate for lite')
            self.directory.mkdir(parents=True,exist_ok=False)
            self.manifest,_=freeze(self.directory,opponents or ROOT/'data/opponents',wesnoth,self.config)
            started=time.time();duration=self.config['hours']*3600
            self.clock=dict(started=started,update_deadline=started+duration*10/12,deadline=started+duration)
            write_json(self.directory/'clock.json',self.clock)

    def run(self):
        with run_lock(self.directory):
            ctx=get_context('spawn');requests=ctx.Queue();processes={};replies={}
            for fmt in self.config['formats']:
                replies[fmt]=ctx.Queue()
                p=ctx.Process(target=trainer_main,args=(str(self.directory/fmt),fmt,self.manifest,self.clock,requests,replies[fmt],self.resume,bool(self.branch_from)),name='trainer-'+fmt)
                processes[fmt]=p;p.start()
            try: scheduling=broker(processes,requests,replies,self.config['workers'],self.directory)
            except BaseException:
                # A broken pool can leave a trainer blocked on replies.get().
                # Stop our remaining trainers before the final join on any
                # coordinator failure, as well as on an explicit interrupt.
                for p in processes.values():
                    if p.is_alive(): p.terminate()
                raise
            finally:
                for p in processes.values(): p.join()
                requests.close()
                for q in replies.values(): q.close()
            reports={}
            for fmt in self.config['formats']:
                path=self.directory/fmt/'report/summary.json'
                reports[fmt]=read_json(path) if path.exists() else dict(status='trainer_failed',exit_code=processes[fmt].exitcode)
            successful=all(processes[f].exitcode==0 and not reports[f].get('error') for f in processes)
            status=('stage_complete' if any(r.get('status')=='stage_complete' for r in reports.values()) else 'finished') if successful else 'partial_failure'
            summary=dict(status=status,formats=reports,clock=self.clock,scheduler=scheduling)
            checkpoints={f:self.directory/f/'selected.pt' for f in FORMATS}
            if all(p.exists() for p in checkpoints.values()) and not (self.directory/'delivery/NeuralArena.zip').exists():
                # Packaging is a separate, explicit command after the continuous-memory parity audit.
                summary['delivery']='pending_explicit_export_with_sequence_audit'
            write_json(self.directory/'summary.json',summary)
            return summary
