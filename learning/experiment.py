"""One process owns one format, model, optimizer, RNG and history."""
from contextlib import contextmanager
from pathlib import Path
import copy
import hashlib
import json
import random
import shutil
import time
import traceback
import torch
from .adapters import COMBAT_VERSION, ENGINE_VERSION, RNG_VERSION
from .common import ROOT, read_json, write_json, sha256
from .data import read_shards
from .evaluate import comparisons, choose_controls, selection_key, overall_status
from .export import export, load_model
from .features import schema
from .formats import FORMATS, PLAYERS
from .model import Policy
from .schedule import calibration_jobs, teacher_jobs, stock_teacher_jobs, rollout_jobs, evaluation_jobs, freeze_schedule
from .teacher_protocol import dagger_status
from .checkpoints import validate_checkpoint, EXECUTION_VERSION
from .ppo import PLAN_VERSION
from .train import checkpoint, restore_rng, train, imitation_quality
from .updates import rollout_identity
from .selection import validate_frozen_selection


def read_log(path):
    path=Path(path)
    if not path.exists(): return []
    lines=path.read_bytes().splitlines();rows={}
    for i,line in enumerate(lines):
        try: row=json.loads(line)
        except (json.JSONDecodeError,UnicodeDecodeError):
            if i==len(lines)-1: break
            raise
        rows[row['id']]=row
    return list(rows.values())


@contextmanager
def run_lock(directory):
    import os
    with (Path(directory)/'run.lock').open('a+b') as handle:
        if handle.tell()==0: handle.write(b'0');handle.flush()
        handle.seek(0)
        if os.name=='nt':
            import msvcrt
            try: msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
            except OSError: raise ValueError('this experiment is already running') from None
        else:
            import fcntl
            try: fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except OSError: raise ValueError('this experiment is already running') from None
        try: yield
        finally:
            handle.seek(0)
            if os.name=='nt': msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
            else: fcntl.flock(handle,fcntl.LOCK_UN)


def default_config(device='cuda', *, engine=None):
    """Eight shared game workers; each trainer has one thread."""
    from .rules_catalog import resolve_dir
    if engine is None: engine='lite'
    bc_games=dict(duel=300,ffa4=600,team2v2=400)
    return dict(hours=12.,workers=8,device=device,trainer_threads=1,seed=20261018,engine=engine,evaluation_engine='native',reward_mode='adaptive',phase='auto',allow_approximate=engine=='lite',rules_dir=str(resolve_dir()),
        formats=list(FORMATS),calibration_blocks=3,validation_interval=10,
        validation_games=dict(duel=6,ffa4=4,team2v2=8),final_blocks=30,final_holdout_hours=0.,
        min_distinct=dict(trend=3,promotion=12,final=12,gate=12),
        bc_games=bc_games,
        native_bc_games={fmt:0 if engine=='lite' else games for fmt,games in bc_games.items()},bc_batch_games=8,
        bc_accuracy=dict(all=.4,recruit=.6,move=.35,attack=.35),shaping_weight=None,
        rollout_games=4,minibatch=256,bc_records=2048 if device=='cpu' else 8192,
        bc_validation_records=1024 if device=='cpu' else 4096,epochs=4,learning_rate=3e-4,
        trainer_memory_gb=6.,
        human_data=str(ROOT/'data/datasets/human'))


def validate_config(config):
    floors=dict(trend=3,promotion=12,final=12,gate=12)
    if set(config.get('min_distinct',{}))!=set(floors) or any(
            not isinstance(config['min_distinct'][key],int) or config['min_distinct'][key]<floor
            for key,floor in floors.items()):
        raise ValueError('distinct scenario floors cannot be lower than trend=3, promotion/final/gate=12')
    if config.get('phase','auto') not in ('auto','bc'): raise ValueError('new runs start in auto or bc; use phase for PPO/evaluation')
    if config['hours']<=0: raise ValueError('hours must be positive')
    if not 0<=config.get('final_holdout_hours',0.)<config['hours']/6:
        raise ValueError('holdout reserve must be finite, nonnegative and smaller than the final budget')
    if not 1<=config['workers']<=16: raise ValueError('workers is the GLOBAL game process count, in [1,16]')
    if config['final_blocks']<30: raise ValueError('formal evaluation needs 30 full blocks per control')
    if not config['formats'] or len(set(config['formats']))!=len(config['formats']) or not set(config['formats'])<=set(FORMATS):
        raise ValueError('choose unique formats from duel ffa4 team2v2')
    if config['rollout_games']<4 or config['rollout_games']%4: raise ValueError('rollout games must be a multiple of four')
    for name in ('trainer_threads','calibration_blocks','validation_interval','minibatch','epochs','bc_records','bc_validation_records','bc_batch_games'):
        if config[name]<1: raise ValueError(name+' must be positive')
    if float(config.get('trainer_memory_gb',0))<0: raise ValueError('trainer memory guard must not be negative')
    for fmt,n in config['validation_games'].items():
        if fmt not in PLAYERS or n<PLAYERS[fmt] or n%PLAYERS[fmt]: raise ValueError('validation games must contain full seat rotations')
    if set(config['validation_games'])!=set(FORMATS): raise ValueError('validation games must cover all formats')
    if config['validation_games']['team2v2']%8:raise ValueError('2v2 validation requires both teammate contexts, eight games per block')
    if set(config['bc_games'])!=set(FORMATS) or any(n<1 for n in config['bc_games'].values()):raise ValueError('positive BC game target required per format')
    anchors=config.get('native_bc_games',{})
    if set(anchors)!=set(FORMATS) or any(not isinstance(n,int) or n<0 or n>config['bc_games'][fmt] for fmt,n in anchors.items()):
        raise ValueError('native BC games must be nonnegative integers no greater than each format BC target')
    if set(config['bc_accuracy'])!={'all','recruit','move','attack'} or any(not 0<v<=1 for v in config['bc_accuracy'].values()):raise ValueError('invalid BC accuracy thresholds')
    if config.get('shaping_weight') is not None: raise ValueError('V5 uses versioned reward controls; replace --shaping-weight with control set')
    if config.get('engine') not in ('native','lite'): raise ValueError('unknown engine')
    if config.get('evaluation_engine',config['engine']) not in ('native','lite'): raise ValueError('unknown evaluation engine')
    if config.get('reward_mode') not in ('fixed','scheduled','adaptive'): raise ValueError('unknown reward mode')


def peak_rss_mb():
    """Kernel high-water RSS of this trainer, so per-update memory is auditable."""
    try:
        for line in Path('/proc/self/status').read_text().splitlines():
            if line.startswith('VmHWM:'): return int(line.split()[1])//1024
    except OSError:
        pass
    return None


def coverage_gate(results):
    totals={k:[0,0] for k in ('all','recruit','move','attack')}
    for result in results:
        if result.get('result',{}).get('faults') or result.get('training_eligible') is False:continue
        c=result.get('coverage',{})
        totals['all'][0]+=c.get('matched',0);totals['all'][1]+=c.get('total',0)
        for kind in ('recruit','move','attack'):
            v=c.get('kinds',{}).get(kind,{})
            totals[kind][0]+=v.get('matched',0);totals[kind][1]+=v.get('total',0)
    metrics={k:dict(matched=m,total=n,ratio=m/n if n else 0) for k,(m,n) in totals.items()}
    return dict(passed=all(v['total']>0 and v['ratio']>=(.9 if k=='all' else .8) for k,v in metrics.items()),actions=metrics)


def opening_gate(results):
    checks=[]
    for r in results:
        if r.get('status')!='complete' or not r.get('behavior'): continue
        seat=r.get('meta',{}).get('seat')
        rows=[d for d in r['behavior'] if seat is not None and d.get('side')==seat]
        ended=[d for d in rows if d.get('end_turn')]
        checks.append(dict(left_castle=any(d.get('left_castle') for d in rows),
            village=any(d.get('village_captured') for d in rows),
            reasonable_end=any(d.get('usable_moves') is not None and d['usable_moves']<=4 for d in ended)))
    return dict(passed=len(checks)>=2 and all(all(c.values()) for c in checks),games=checks)


def human_coverage(directory,fmt):
    path=Path(directory)/'import.json'
    if not path.exists(): return []
    results=[]
    for game in read_json(path)['games']:
        if game['format']!=fmt or game['status']!='imported': continue
        kinds=game['coverage']
        results.append(dict(coverage=dict(kinds=kinds,total=sum(v['total'] for v in kinds.values()),
            matched=sum(v['matched'] for v in kinds.values()))))
    return results


class FormatExperiment:
    def __init__(self,directory,fmt,manifest,clock,collector,resume=False,branch=False):
        self.directory=Path(directory);self.fmt=fmt;self.manifest=manifest
        self.config=manifest['config'];self.clock=clock;self.collector=collector
        self.directory.mkdir(parents=True,exist_ok=True)
        torch.set_num_threads(self.config['trainer_threads'])
        requested=self.config['device']
        self.device=('cuda' if torch.cuda.is_available() else 'cpu') if requested=='auto' else requested
        if self.device.startswith('cuda') and not torch.cuda.is_available(): raise ValueError('CUDA requested but unavailable')
        from .manifest import active_teacher
        self.teacher_record=active_teacher(manifest)
        legacy=self.teacher_record['kind']=='gpt6astra'
        self.teachers=[p['path'] for p in manifest['opponents']] if legacy else ['baseline']
        self.reference_opponents=self.teachers+['baseline'] if legacy else ['baseline']
        self.native_fixed=self.reference_opponents
        self.fixed=self.native_fixed if self.config['engine']=='native' else self.teachers if legacy else []
        self.exe=manifest['baseline']['path']
        info=None;loaded=None
        if (resume or branch) and (self.directory/'latest.pt').exists():
            self.model,loaded=load_model(self.directory/'latest.pt',fmt,self.device)
            if branch:
                info=read_json(self.directory.parent/'branch.json')
                record=info['checkpoints'][fmt]
                if sha256(self.directory/'latest.pt')!=record['sha256']:
                    raise ValueError('branch checkpoint changed after it was copied')
                validate_checkpoint(loaded,fmt,None)
                if loaded.get('manifest_sha256')!=info['parent_manifest_sha256']:
                    raise ValueError('branch checkpoint belongs to a different parent manifest')
            else:
                validate_checkpoint(loaded,fmt,sha256(self.directory.parent/'manifest.json'))
        if loaded is not None:
            self.optimizer=torch.optim.Adam(self.model.parameters(),lr=self.config['learning_rate'])
            if not (branch and info['reset_optimizer']):
                self.optimizer.load_state_dict(loaded['optimizer'])
            restore_rng(loaded,self.device)
            if branch:
                from .branch import adopt
                self.state=adopt(loaded['runner'],info,clock,
                    self.config.get('phase','auto'))
                seed=self.config['seed']+FORMATS.index(fmt)*100003
                random.seed(seed);torch.manual_seed(seed)
            else:
                self.state=loaded['runner']
                if self.state['clock']!=clock: raise ValueError('resume cannot reset shared budget')
            expected=self.identity()
            inherited={key:loaded.get(key) for key in expected}
            if any(inherited[key]!=value for key,value in expected.items()):
                # Old weights may still seed a fresh plan, but never continue a run.
                if not (branch and info.get('reset_optimizer')):
                    raise ValueError(f'checkpoint combat profile {inherited!r} does not match {expected!r}; '
                                     'old weights are explicit initialization only')
                self.state['initialized_from']=inherited
        else:
            if branch: raise ValueError('branch source has no latest checkpoint')
            seed=self.config['seed']+FORMATS.index(fmt)*100003
            random.seed(seed);torch.manual_seed(seed)
            self.model=Policy(fmt).to(self.device)
            self.optimizer=torch.optim.Adam(self.model.parameters(),lr=self.config['learning_rate'])
            self.state=dict(format=fmt,stage='calibration',phase=self.config.get('phase','auto'),clock=clock,batch=0,version=0,history=[],snapshots=[],
                best_key=None,bc_key=None,ppo_key=None,best_kind=None,pending_train=None,pending_validation=None,
                teacher_shards=[],effective=False,error=None)
            self.save()
        from .control import RewardController
        self.controller=RewardController(self.directory.parent,self.fmt,state=self.state.get('reward_controller'),config=dict(mode=self.config['reward_mode']))
        self.state.setdefault('dagger_shards',[])
        self.state.setdefault('policy_shards',[])
        self.state.setdefault('dagger_status',dagger_status(self.teacher_record))
        self.state.setdefault('counters',dict(environment_games=0,collection_batches=0,optimizer_steps=0,unique_families_seen=0,decisions_seen=0,effective_dataset_passes=0.))
        self.save()
        self.support=self.ensure_export(self.model,'support','LearningSupport')
        write_json(self.directory/'hardware.json',dict(device=self.device,cuda_runtime=torch.version.cuda,
            gpu=torch.cuda.get_device_name(self.device) if self.device.startswith('cuda') else None,
            trainer_threads=torch.get_num_threads()))

    def save(self):
        if hasattr(self,'controller'): self.state['reward_controller']=self.controller.state_dict()
        self._write_checkpoint(self.directory/'latest.pt')
        write_json(self.directory/'state.json',self.state)

    def _write_checkpoint(self,path):
        checkpoint(path,self.model,self.optimizer,runner=copy.deepcopy(self.state),
            execution=dict(plan_version=PLAN_VERSION),manifest_sha256=sha256(self.directory.parent/'manifest.json'),**self.identity())

    def identity(self):
        """Provenance of the combat engine and teacher this run trains against."""
        from .manifest import active_teacher
        record=active_teacher(self.manifest)
        if record['kind']=='wesnoth_default_rca':
            lite=self.config['engine']=='lite'
            return dict(engine=self.config['engine'],engine_version=ENGINE_VERSION if lite else '1.18.8',
                        rng_version=RNG_VERSION if lite else 'native-1.18.8',
                        combat_version=COMBAT_VERSION if lite else 'native-1.18.8',
                        teacher=record['kind'],teacher_profile='native',
                        teacher_source_sha256=record['runtime_sha256'],teacher_identity=record)
        if self.config['engine']=='lite':
            from .teachers import identity as teacher_identity
            return dict(engine='lite',engine_version=ENGINE_VERSION,rng_version=RNG_VERSION,
                        combat_version=COMBAT_VERSION,**teacher_identity())
        return dict(engine='native',engine_version='1.18.8',rng_version='native-1.18.8',
                    combat_version='native-1.18.8',teacher='gpt6astra',teacher_profile='native',
                    teacher_source_sha256='native-1.18.8',teacher_parent_sha256=None)

    def ensure_export(self,model,folder,name,mode='greedy',version=None):
        destination=self.directory/'policies'/folder;addon=destination/name
        if addon.exists():
            # Internal exports are not SDK submissions (export(package=False)).
            # Check their frozen schema and weights without imposing the SDK's
            # 16 MiB submission limit during resume.
            metadata=read_json(destination/'export.json')
            weights=metadata.get('models',{}).get(model.format_name,{})
            if metadata.get('features')!=json.loads(json.dumps(schema())) or not (addon/'lua/bot.lua').is_file():
                raise ValueError('internal policy export schema or entry differs')
            if sha256(addon/'lua'/f'weights_{model.format_name}.lua')!=weights.get('sha256'):
                raise ValueError('internal policy export weights differ')
        else: export(model,destination,name=name,mode=mode,version=version or folder,package=False,identity=self.identity())
        tensor_path=destination/'model.pt'
        if not tensor_path.exists():
            from .model import ARCHITECTURE
            temporary=tensor_path.with_suffix('.tmp')
            torch.save(dict(model={k:v.detach().cpu() for k,v in model.state_dict().items()},features=schema(),architecture=ARCHITECTURE,format=model.format_name),temporary)
            temporary.replace(tensor_path)
        return str(addon)

    def execute(self,jobs,name):
        from .rules_catalog import resolve_dir
        for job in jobs:
            job['teacher_identity']=dict(self.teacher_record)
            job.setdefault('engine',self.config['engine'])
            job['rules_dir']=str(resolve_dir(self.config.get('rules_dir')))
            job.setdefault('reward_config',self.controller.freeze())
            job.setdefault('meta',{})['engine_id']=job['engine']
            if job['engine']=='lite':
                job['meta'].update(engine_version=ENGINE_VERSION,rng_version=RNG_VERSION,combat_version=COMBAT_VERSION)
                if self.teacher_record['kind']=='gpt6astra':
                    from .teachers import identity as teacher_identity, lineage as teacher_lineage
                    job['meta'].update(**teacher_identity())
                    job['meta']['teacher_lineage']=teacher_lineage()
                else:
                    job['meta'].update(teacher=self.teacher_record['kind'],teacher_profile='none')
                job.setdefault('allow_approximate',self.config.get('allow_approximate',False))
            if job.get('split_rule') == 'scenario-v2':
                if job.get('training_scenario'):
                    from .schedule import compose_training_scenario
                    compose_training_scenario(job)
                else:
                    from .maps import bind_scenario
                    bind_scenario(job)
        schedule=self.directory/'schedules'/(name+'.json')
        if schedule.exists(): jobs=read_json(schedule)
        else: freeze_schedule(schedule,jobs)
        log=self.directory/'jobs.jsonl';existing={r['id']:r for r in read_log(log)}
        pending=[]
        for job in jobs:
            record=existing.get(job['id'])
            if record is not None and record.get('status')!='infrastructure_error':
                continue
            # An unlogged or infrastructure-failed attempt may have left a shard.
            # The batch was not committed, so discard that attempt before retrying.
            if job.get('shard'):
                for name in (job['shard'],job['shard'].replace('.jsonl.gz','.dagger.jsonl.gz')):
                    if Path(name).exists():
                        from .sequences import discard_sequences
                        discard_sequences(name,job['id'])
            pending.append(job)
        if pending: self.collector(pending,log)
        latest={r['id']:r for r in read_log(log)}
        return jobs,[latest[j['id']] for j in jobs if j['id'] in latest]

    def human_paths(self): return sorted((Path(self.config['human_data'])/self.fmt).glob('*.jsonl.gz'))

    def update_deadline(self):
        key='deadline' if self.state.get('phase') in ('bc','ppo') else 'update_deadline'
        return self.state.get('phase_deadline') or self.clock.get(key,self.clock['update_deadline'])

    def evaluation_deadline(self):
        return (self.state.get('phase_deadline') if self.state.get('phase')=='evaluate' else None) or self.clock['deadline']

    def complete_phase(self):
        phase=self.state['phase'];self.state.update(stage=phase+'_complete',status='stage_complete')
        self.save()
        summary=dict(format=self.fmt,status='stage_complete',phase=phase,version=self.state['version'],
            pretraining_complete=self.state['effective'],forced_ppo=self.state.get('forced_ppo'),
            teacher=dict(kind=self.teacher_record['kind'],version=self.teacher_record['version'],
                query=self.teacher_record['query'],
                dagger_status=self.state.get('dagger_status',dagger_status(self.teacher_record)),
                dagger_shards=len(self.state.get('dagger_shards',[]))),
            checkpoint=str(self.directory/'latest.pt'),error=self.state.get('error'),clock=self.clock)
        write_json(self.directory/'report/summary.json',summary)
        return summary

    def teacher_batch(self,count,index,anchor):
        """Frozen teacher games; only a declared query capability becomes a controller seat."""
        if self.state['dagger_status']=='active':
            return teacher_jobs(self.directory,self.teachers,self.native_fixed if anchor else self.fixed,
                self.support,index,self.config['seed'],self.update_deadline(),self.exe,
                formats=[self.fmt],count=count,index_stride=self.config['bc_batch_games'])
        return stock_teacher_jobs(self.directory,self.teacher_record,self.support,index,self.config['seed'],
            self.update_deadline(),self.exe,formats=[self.fmt],count=count,index_stride=self.config['bc_batch_games'])

    def teacher_evidence(self):
        return [r for r in read_log(self.directory/'jobs.jsonl') if r.get('meta',{}).get('phase')=='teacher'
            and r.get('status')=='complete' and not r.get('result',{}).get('faults')
            and r.get('training_eligible',True) and r.get('coverage',{}).get('matched',0)>0]

    def finish_train(self):
        pending=self.state['pending_train'];method=pending['method']
        pool=self.state['teacher_shards']+self.state['dagger_shards']+list(map(str,self.human_paths()))
        if method=='ppo': pool=pool+list(self.state.get('policy_shards',[]))
        pool_seed=self.config['seed']+self.state['version']
        reads={}
        bc=read_shards(pool,partition='train',limit=self.config['bc_records'],seed=pool_seed,format_name=self.fmt,stats=reads.setdefault('bc',{}))
        validation=read_shards(pool,partition='validation',limit=self.config['bc_validation_records'],seed=self.config['seed'],format_name=self.fmt,stats=reads.setdefault('validation',{})) if method=='bc' else []
        rows=bc+validation if method=='bc' else read_shards(pending['paths'],format_name=self.fmt)
        for row in bc+validation+rows:
            if row.get('source') in ('astra','stock_rca'):
                if row.get('teacher')!=self.teacher_record['kind'] or (
                        row.get('teacher_identity') is not None and row['teacher_identity']!=self.teacher_record):
                    raise ValueError('training labels differ from the active teacher')
        if method == 'ppo':
            from .updates import eligible_rows
            eligible_rows(rows)
        identity=dict(train=rollout_identity(rows))
        if method=='ppo': identity['bc']=rollout_identity(bc)
        if pending.get('identity') is not None and pending['identity']!=identity:
            raise ValueError('scheduled rollout changed since the checkpoint')
        pending['identity']=identity
        self.save()
        def progress(cursor):
            self.state['pending_train']['cursor']=cursor
            if cursor['updates']%50==0: self.save()
        frozen=pending.get('reward_config',self.controller.freeze())
        if method=='ppo':
            for group in self.optimizer.param_groups: group['lr']=1e-4
        control=self.identity() if method=='ppo' else {}
        rehearsal_exclude=dict(impl=control.get('teacher'),sha256=control.get('teacher_source_sha256')) if method=='ppo' else None
        metrics=train(self.model,self.optimizer,rows,method,epochs=self.config['epochs'],minibatch=self.config['minibatch'],
            deadline=self.update_deadline(),progress=pending['cursor'],on_step=progress,bc_records=bc,entropy=frozen['entropy'],bc_aux=frozen['bc_aux'],plan_seed=int(self.config['seed']),
            rehearsal_exclude=rehearsal_exclude,allow_policy_rehearsal=method=='ppo')
        if metrics.get('cursor') is not None: pending['cursor']=metrics['cursor']
        if metrics['interrupted']: self.save();return False
        committed=metrics.get('committed_decisions',metrics.get('decisions_seen',0))
        history=dict(batch=self.state['batch'],method=method,
            elapsed_hours=(time.time()-self.clock['started'])/3600,reads=reads,peak_rss_mb=peak_rss_mb(),**metrics)
        if method == 'ppo':
            counters = self.state['counters']
            for key in ('planned_steps', 'committed_steps', 'stopped_by_kl_steps'):
                counters[key] = counters.get(key, 0) + metrics[key]
        if metrics.get('kl_stopped') and metrics.get('updates',0)==0:
            # The whole logical batch was rejected before any parameter change.
            self.state['history'].append(history)
            self.state['kl_stops']=self.state.get('kl_stops',0)+1
            self.state['pending_train']=None
            self.state['batch']+=1
            self.save();return True
        self.state['version']+=1
        counters=self.state['counters']
        counters['optimizer_steps']+=metrics['updates'];counters['decisions_seen']+=committed
        self.state['families_seen']=sorted(set(self.state.get('families_seen',[]))|{r['game_family'] for r in bc+rows})
        counters['unique_families_seen']=len(self.state['families_seen'])
        counters['effective_dataset_passes']+=metrics.get('effective_dataset_passes',0.)
        self.state['history'].append(history)
        if method=='bc':
            quality=imitation_quality(self.model,rows,thresholds=self.config['bc_accuracy'])
            accuracy=quality['formats'][self.fmt]['accuracy']
            if accuracy>self.state.get('bc_quality_best',-1): self.state['bc_quality_best']=accuracy;self.state['bc_plateau']=0
            else: self.state['bc_plateau']=self.state.get('bc_plateau',0)+1
            evidence=self.teacher_evidence()
            coverage=coverage_gate(evidence+human_coverage(self.config['human_data'],self.fmt))
            corpus=dict(games=len(evidence),required=self.config['bc_games'][self.fmt],passed=len(evidence)>=self.config['bc_games'][self.fmt])
            from .evaluate import gate_design
            design=gate_design(rows,self.config['min_distinct']['gate'])
            if design['status']=='insufficient_design': self.state['effective']=False
            write_json(self.directory/'bc_gate.json',dict(imitation=quality,coverage=coverage,corpus=corpus,
                opening=dict(passed=False),passed=False,**dict(design,status='insufficient_design' if design['status']=='insufficient_design' else 'pending')))
        self.state['batch']+=1
        self.state['pending_train']=None
        self.state['pending_validation']=method if self.state['version']%self.config['validation_interval']==0 else None
        self.save()
        self._write_checkpoint(self.directory/f'last_{method}.pt')
        return True

    def validate_model(self,method):
        version=self.state['version']
        greedy=self.ensure_export(self.model,f'v{version:06}-greedy',f'SnapV{version:06}',version=f'v{version}')
        control=self.teachers[0]
        stock=self.teacher_record['kind']=='wesnoth_default_rca'
        reference_engine='native' if stock else self.config['engine']
        fixed=self.reference_opponents if stock else self.fixed
        contexts=('baseline_partner','self_team') if reference_engine=='native' else ('astra_partner','self_team')
        promotion=version%100==0
        min_distinct=self.config['min_distinct']['promotion' if promotion else 'trend']
        blocks=12 if promotion else self.config['validation_games'][self.fmt]//(PLAYERS[self.fmt]*(len(contexts) if self.fmt=='team2v2' else 1))
        jobs=evaluation_jobs(self.directory,greedy,control,fixed,blocks,
            self.config['seed']+1000000+(0 if promotion else version*101),self.update_deadline(),self.exe,label=f'val{version:06}',formats=[self.fmt],team_contexts=contexts,
            faction_cycle=0 if promotion else (version//self.config['validation_interval']-1)%3,min_distinct=min_distinct)
        for job in jobs:
            job['engine']=reference_engine
            job['learning']=dict(support=self.support,sides={str(side):dict(teacher=False,version=f'v{version}') for side in job['meta']['policy_sides']})
        jobs,results=self.execute(jobs,f'validation-{version:06}')
        comparison=comparisons(jobs,results,min_blocks=blocks,min_distinct=min_distinct,team_contexts=contexts)
        write_json(self.directory/'validation'/f'v{version:06}.json',dict(tier='promotion' if promotion else 'trend',format=self.fmt,
            engine_id=self.config['engine'],seed=self.config['seed']+1000000+(0 if promotion else version*101),blocks=blocks,control=control,
            contexts=list(contexts),min_distinct=min_distinct,comparison=comparison))
        from .reward_metrics import build_control_metrics
        try:
            if self.controller.freeze()['mode']=='adaptive':
                self.collect_reward_references(jobs,version)
            references=[r for r in read_log(self.directory/'jobs.jsonl') if r.get('meta',{}).get('phase')=='reward_reference']
            metrics=build_control_metrics(jobs,results,references,comparison)
            metrics['status']='complete' if len(metrics['validation_blocks'])>=blocks else 'inconclusive'
            self.state.pop('control_metrics_error',None)
        except Exception as exc:
            # Optional reward diagnostics must not skip BC/opening checks.
            # Preserve the fault; never turn failed metrics into passing evidence.
            error_path=self.directory/'validation'/f'control-v{version:06}.error.log'
            error_path.parent.mkdir(parents=True,exist_ok=True)
            error_path.write_text(traceback.format_exc(),encoding='utf-8')
            metrics=dict(status='error',error=repr(exc),partition='validation',validation_blocks=[],excluded_evidence=[])
            self.state['control_metrics_error']=dict(version=version,error=repr(exc))
        metrics['new_games']=self.state.get('control_metrics',{}).get('new_games',0)
        self.state['control_metrics']=metrics
        write_json(self.directory/'validation'/f'control-v{version:06}.json',metrics)
        key=selection_key(comparison) if promotion and comparison[self.fmt]['blocks']>=blocks else None
        champion=self.state.get('champion')
        if promotion and champion:
            champion_jobs=evaluation_jobs(self.directory,greedy,champion,fixed,12,self.config['seed']+1000000,
                self.update_deadline(),self.exe,label=f'champion{version:06}',formats=[self.fmt],team_contexts=contexts,min_distinct=min_distinct)
            for job in champion_jobs: job['engine']=reference_engine
            champion_jobs,champion_results=self.execute(champion_jobs,f'champion-{version:06}')
            champion_comparison=comparisons(champion_jobs,champion_results,min_blocks=12,min_distinct=min_distinct,team_contexts=contexts)
            write_json(self.directory/'validation'/f'champion-v{version:06}.json',dict(tier='promotion',format=self.fmt,
                engine_id=self.config['engine'],seed=self.config['seed']+1000000,blocks=12,control=champion,
                contexts=list(contexts),comparison=champion_comparison))
            if champion_comparison[self.fmt]['status']!='passed': key=None
        save_method_best=False;save_best=False
        if key is not None:
            field=method+'_key'
            if self.state[field] is None or key>self.state[field]:
                self.state[field]=key;save_method_best=True
            if self.state['best_key'] is None or key>self.state['best_key']:
                save_best=True
                self.state['best_key']=key;self.state['best_kind']=method
                self.state['champion']=greedy
                self.state['best_engine']='best_lite' if self.config['engine']=='lite' else 'native_candidate'
        gate=read_json(self.directory/'bc_gate.json') if method=='bc' else None
        if method=='bc' and gate.get('distinct_scenarios',0)>=self.config['min_distinct']['gate'] and gate['imitation']['effective'] and gate['coverage']['passed'] and gate['corpus']['passed'] and time.time()<self.update_deadline():
            from .sample import opening_map
            probes=rollout_jobs(self.directory,greedy,[greedy],fixed,self.support,f'v{version}',0,
                self.config['seed']+900000,self.update_deadline(),self.exe,4,current=greedy,formats=[self.fmt])
            for j in probes:
                j['engine']=reference_engine
                j['id']='opening-'+str(version)+'-'+j['id'];j['max_turns']=5
                j.pop('training_scenario', None)
                j['meta'].pop('eligibility_swap', None)
                focal=j['meta']['seat']
                j['bots']=[greedy if i==focal else 'baseline' for i in range(1,len(j['bots'])+1)]
                j['map_override']=opening_map(len(j['bots']))
                map_hash=hashlib.sha256(json.dumps(j['map_override'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
                j['meta'].update(map='opening_probe',map_sha256=map_hash)
                family=dict(format=self.fmt,map=map_hash,seed=j['seed'],factions=j['factions'],teams=j.get('teams'))
                j['game_family']=hashlib.sha256(json.dumps(family,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                j['output']=str(self.directory/'replays'/(j['id']+'.json'));j.pop('shard',None)
            _,opening=self.execute(probes,f'opening-{version:06}')
            gate['opening']=opening_gate(opening)
            self.state['effective']=all(gate[k]['effective' if k=='imitation' else 'passed'] for k in ('imitation','coverage','corpus','opening'))
            gate['passed']=self.state['effective'];gate['status']='passed' if gate['passed'] else 'not_passed'
            write_json(self.directory/'bc_gate.json',gate)
        self.state['snapshots'].append(greedy);self.state['pending_validation']=None;self.save()
        if save_method_best: self._write_checkpoint(self.directory/f'best_{method}.pt')
        if save_best: self._write_checkpoint(self.directory/'best.pt')

    def collect_reward_references(self,jobs,version):
        """Bounded Astra calibration on validation layouts; never added to BC data."""
        from .reward_metrics import METRICS_VERSION, MIN_REFERENCE_GAMES, _diagnostics
        from .rules_catalog import load, resolve_dir
        rows=[r for r in read_log(self.directory/'jobs.jsonl') if r.get('meta',{}).get('phase')=='reward_reference']
        existing=list(_diagnostics(rows));attempted={r['id'] for r in rows}
        stock=self.teacher_record['kind']=='wesnoth_default_rca'
        engine='native' if stock else self.config['engine']
        source='stock_rca' if stock else 'astra'
        rules=schema()['rules_sha256'] if engine=='native' else load(resolve_dir(self.config.get('rules_dir')))['rules_version']
        proposals=[];seen=set()
        for job in jobs:
            if job['meta'].get('map_partition')!='validation': continue
            for side in job['meta']['policy_sides']:
                context=job['meta']['context'];faction=job['factions'][side-1];map_hash=job['meta']['map_sha256']
                key=(map_hash,faction,context)
                if key in seen: continue
                seen.add(key)
                known={d['game_family'] for d in existing if (d['map_sha256'],d['faction'],d['context'])==key
                       and d['engine_id']==engine and d.get('rules_version')==rules and d.get('format')==self.fmt
                       and d.get('metrics_version')==METRICS_VERSION and d.get('source')==source
                       and d.get('teacher')==self.teacher_record['kind'] and d.get('map_partition')=='validation'}
                identity=hashlib.sha256(json.dumps([self.fmt,engine,rules,*key,METRICS_VERSION]).encode()).hexdigest()[:16]
                repeat=0
                for _ in range(max(0,MIN_REFERENCE_GAMES-len(known))):
                    ident=f'reward-reference-{self.fmt}-{identity}-{repeat}'
                    while ident in attempted:
                        repeat+=1;ident=f'reward-reference-{self.fmt}-{identity}-{repeat}'
                    attempted.add(ident);repeat+=1
                    reference=copy.deepcopy(job)
                    reference['id']=ident;reference['seed']=int(hashlib.sha256(ident.encode()).hexdigest()[:8],16)
                    reference['bots'][side-1]=self.teachers[0]
                    reference['output']=str(self.directory/'replays'/(ident+'.json'))
                    reference['engine']=engine
                    reference['learning']=dict(support=self.support,sides={str(side):dict(teacher=self.teacher_record['kind'],version='teacher-frozen')})
                    reference['meta'].update(phase='reward_reference',label=f'reward-reference-v{version:06}',seat=side)
                    family=dict(format=self.fmt,map=map_hash,seed=reference['seed'],factions=reference['factions'],teams=reference.get('teams'))
                    reference['game_family']=hashlib.sha256(json.dumps(family,sort_keys=True,separators=(',',':')).encode()).hexdigest()
                    proposals.append(reference)
                    if len(proposals)>=12: break
                if len(proposals)>=12: break
            if len(proposals)>=12: break
        if proposals: self.execute(proposals,f'reward-reference-v{version:06}')

    def learn(self):
        self.state.setdefault('dagger_status',dagger_status(self.teacher_record))
        if self.state['pending_train']:
            method=self.state['pending_train']['method']
            if not self.finish_train(): return
        while True:
            from .phases import apply_phase
            apply_phase(self)
            phase=self.state.get('phase','auto')
            if phase=='evaluate': return
            if self.state['pending_validation']: self.validate_model(self.state['pending_validation'])
            if phase=='bc' and self.state['effective']: return
            if time.time()>=self.update_deadline(): return
            self.controller.boundary(self.state['batch'],self.state.pop('control_metrics',None))
            method='ppo' if phase=='ppo' or (phase!='bc' and self.state['effective']) else 'bc'
            self.state['stage']=method;index=self.state['batch'];version=self.state['version']
            if method=='bc':
                evidence=self.teacher_evidence()
                remaining=max(0,self.config['bc_games'][self.fmt]-len(evidence))
                refresh=self.state.get('bc_plateau',0)>=10
                native_count=sum(r.get('meta',{}).get('engine_id','native')=='native' for r in evidence)
                anchor=self.config['engine']=='lite' and native_count<self.config['native_bc_games'][self.fmt]
                count=min(self.config['bc_batch_games'],remaining) if remaining else self.config['bc_batch_games'] if refresh else 0
                if anchor: count=min(count,self.config['native_bc_games'][self.fmt]-native_count)
                jobs=self.teacher_batch(count,index,anchor)
                if anchor:
                    for job in jobs: job['engine']='native'
                if refresh:
                    student=self.ensure_export(self.model,f'v{version:06}-greedy',f'SnapV{version:06}',version=f'v{version}')
                    corrections=rollout_jobs(self.directory,student,[student],self.fixed,self.support,f'v{version}',index,
                        self.config['seed']+7100000,self.update_deadline(),self.exe,4,current=student,formats=[self.fmt])
                    for job in corrections:
                        if self.state['dagger_status']=='active':
                            job['learning']['dagger_teacher']=self.teachers[0]
                        job['meta']['phase']='dagger_refresh'
                    jobs.extend(corrections)
                    self.state['bc_plateau']=0;self.state['bc_refreshes']=self.state.get('bc_refreshes',0)+1
                    if self.state['bc_refreshes']>1:
                        for group in self.optimizer.param_groups: group['lr']*=.9
            else:
                sample=self.ensure_export(self.model,f'v{version:06}-sample',f'RollV{version:06}',mode='sample',version=f'v{version}')
                current=self.ensure_export(self.model,f'v{version:06}-greedy',f'SnapV{version:06}',version=f'v{version}')
                jobs=rollout_jobs(self.directory,sample,self.state['snapshots'] or [current],self.fixed,self.support,f'v{version}',
                    index,self.config['seed'],self.update_deadline(),self.exe,self.config['rollout_games'],current=current,formats=[self.fmt])
                if self.state['dagger_status']=='active':
                    for job in jobs: job['learning']['dagger_teacher']=self.teachers[0]
            jobs,results=self.execute(jobs,f'{method}-batch-{index:06}')
            if any(r['status']=='infrastructure_error' for r in results): raise RuntimeError('sampling failed; inspect jobs.jsonl')
            successful={r['id'] for r in results if r['status']=='complete' and not r.get('result',{}).get('faults') and r.get('training_eligible',True)}
            paths=[j['shard'] for j in jobs if j['id'] in successful]
            self.state['counters']['environment_games']+=len(successful);self.state['counters']['collection_batches']+=1
            self.state['control_metrics']=dict(partition='train',new_games=len(successful),faulted_games=0)
            for path in paths:
                dagger=Path(path).with_name(Path(path).name.replace('.jsonl.gz','.dagger.jsonl.gz'))
                if dagger.exists():
                    if self.state['dagger_status']!='active':
                        raise ValueError('a teacher without a query capability cannot produce a DAgger shard')
                    self.state['dagger_shards']=sorted(set(self.state['dagger_shards']+[str(dagger)]))
            if method=='ppo':
                self.state['policy_shards']=sorted(set(self.state['policy_shards']+[str(p) for p in paths]))
            if method=='bc':
                original=[j['shard'] for j in jobs if j['id'] in successful and j.get('meta',{}).get('phase')=='teacher']
                self.state['teacher_shards']=sorted(set(self.state['teacher_shards']+original))
                paths=self.state['teacher_shards']+list(map(str,self.human_paths()))
            if not read_shards(paths,partition='train',limit=self.config['bc_records'],format_name=self.fmt):
                self.state['batch']+=1;self.save();continue
            self.state['pending_train']=dict(paths=paths,method=method,cursor=dict(epoch=0,step=0),reward_config=self.controller.freeze());self.save()
            if not self.finish_train(): break

    def _checkpoint_version(self,path):
        state=torch.load(path,map_location='cpu',weights_only=False)
        if state.get('runner',{}).get('pending_train'): return -1
        return int(state.get('runner',{}).get('version',-1))

    def _nominate_final(self,candidate,champion):
        """One full validation nomination; training and holdout are untouched."""
        from .selection import _panel_complete
        version=self._checkpoint_version(candidate)
        if version<=self._checkpoint_version(champion):
            return dict(choice='champion',reason='no newer complete candidate')
        deadline=self.evaluation_deadline()-self.config.get('final_holdout_hours',0.)*3600
        if time.time()>=deadline:
            return dict(choice='champion',reason='no nomination time remains')
        model,candidate_state=load_model(candidate,self.fmt)
        if candidate_state.get('runner',{}).get('pending_train'):
            return dict(choice='champion',reason='candidate update is incomplete')
        champion_model,champion_state=load_model(champion,self.fmt)
        champion_key=champion_state.get('runner',{}).get('best_key')
        if champion_key is None:
            return dict(choice='champion',reason='champion validation score unavailable')
        policy=self.ensure_export(model,f'nominate-v{version:06}-'+sha256(candidate)[:16],f'NominateV{version:06}',version=f'v{version}')
        opponent=self.ensure_export(champion_model,'nominate-champion-'+sha256(champion)[:16],'NominateChampion')
        stock=self.teacher_record['kind']=='wesnoth_default_rca'
        reference_engine='native' if stock else self.config['engine']
        fixed=self.reference_opponents if stock else self.fixed
        contexts=('baseline_partner','self_team') if reference_engine=='native' else ('astra_partner','self_team')
        identity=dict(candidate_sha256=sha256(candidate),champion_sha256=sha256(champion),
            profile=self.identity(),features=schema(),seed=self.config['seed']+1000000,contexts=list(contexts),
            min_distinct=self.config['min_distinct']['promotion'],evaluation_engine=reference_engine)
        identity=json.loads(json.dumps(identity))
        panels=[]
        for label,control in ((self.teacher_record['kind'] if stock else 'astra',self.teachers[0]),('champion',opponent)):
            path=self.directory/'validation'/f'nominate-v{version:06}-{label}.json'
            expected=dict(identity,control=control)
            panel=read_json(path) if path.exists() else None
            if not (panel and panel.get('identity')==expected and _panel_complete(panel,self.fmt)):
                if time.time()>=deadline:
                    return dict(choice='champion',reason='nomination time exhausted')
                # Hash-bound schedule names cannot replay another checkpoint's games.
                suffix=hashlib.sha256(json.dumps(expected,sort_keys=True).encode()).hexdigest()[:16]
                name=f'nominate-v{version:06}-{label}-{suffix}'
                jobs=evaluation_jobs(self.directory,policy,control,fixed,12,identity['seed'],deadline,
                    self.exe,label=name,formats=[self.fmt],team_contexts=contexts,min_distinct=identity['min_distinct'])
                for job in jobs: job['engine']=reference_engine
                jobs,results=self.execute(jobs,name)
                panel=dict(identity=expected,comparison=comparisons(jobs,results,min_blocks=12,min_distinct=identity['min_distinct'],team_contexts=contexts))
                write_json(path,panel)
            panels.append(panel)
            if not _panel_complete(panel,self.fmt):
                return dict(choice='champion',reason=label+' nomination panel incomplete')
            if panel['comparison'][self.fmt]['status']!='passed':
                return dict(choice='champion',reason=label+' nomination did not pass')
        if panels[0]['comparison'][self.fmt]['difference']<=champion_key:
            return dict(choice='champion',reason='candidate did not beat the retained champion score')
        return dict(choice='candidate',reason='full reference and champion nomination passed')

    def _select_final(self):
        frozen=self.directory/'selected.pt';record=self.directory/'selection.json'
        if frozen.exists() and record.exists():
            saved=validate_frozen_selection(record,sha256(frozen));return frozen,saved['selected_kind'],saved
        champion=self.directory/'best.pt'
        candidates=[p for p in [self.directory/'last_ppo.pt',self.directory/'last_bc.pt',self.directory/'latest.pt'] if p.exists() and self._checkpoint_version(p)>=0]
        if not champion.exists() and not candidates:
            raise RuntimeError('no complete checkpoint to select')
        if not champion.exists():
            chosen=candidates[0];kind='fallback';version=self._checkpoint_version(chosen);candidate=chosen;candidate_version=version
            detail=dict(choice='fallback',reason='no retained champion')
        else:
            champion_version=self._checkpoint_version(champion)
            ranked=sorted(candidates,key=lambda p:self._checkpoint_version(p),reverse=True)
            candidate=ranked[0] if ranked else champion
            candidate_version=self._checkpoint_version(candidate)
            detail=self._nominate_final(candidate,champion)
            if detail['choice']=='candidate':
                chosen=candidate;kind='candidate';version=candidate_version
            else:
                chosen=champion;kind='champion';version=champion_version
        temp=frozen.with_suffix('.tmp')
        shutil.copyfile(chosen,temp);temp.replace(frozen)
        record_data=dict(candidate=str(candidate) if candidate else None,candidate_version=candidate_version if candidate else None,
            champion=str(champion) if champion.exists() else None,champion_version=self._checkpoint_version(champion) if champion.exists() else None,
            selected=str(chosen),selected_kind=kind,selected_version=version,reason=detail['reason'],
            selected_sha256=sha256(frozen),frozen_before_holdout=True,format=self.fmt)
        write_json(record,record_data)
        return frozen,kind,record_data

    def final_evaluation(self):
        self.state['stage']='final';self.save()
        frozen,selected_kind,selection=self._select_final()
        selected,selected_state=load_model(frozen,self.fmt)
        selected_version=selected_state['runner']['version']
        policy=self.ensure_export(selected,'final-selected','FinalSelected',version=self.fmt+'-v'+str(selected_version))
        plans={}
        evaluation_engine=self.config.get('evaluation_engine',self.config['engine'])
        fixed=self.native_fixed if evaluation_engine=='native' else self.teachers
        contexts=('baseline_partner','self_team') if evaluation_engine=='native' else ('astra_partner','self_team')
        for i,control in enumerate(fixed):
            label=Path(control).stem
            plans[label]=evaluation_jobs(self.directory,policy,control,fixed,self.config['final_blocks'],
                self.config['seed']+200000000+i*100003,self.evaluation_deadline(),self.exe,label='final-'+label,formats=[self.fmt],team_contexts=contexts,min_distinct=self.config['min_distinct']['final'])
        jobs=sorted([j for plan in plans.values() for j in plan],key=lambda j:(j['meta']['block'],j['meta']['rotation'],j['meta']['context'],j['meta']['label']))
        for job in jobs: job['engine']=evaluation_engine
        _,results=self.execute(jobs,'final')
        reports={label:comparisons(plan,results,min_distinct=self.config['min_distinct']['final'],team_contexts=contexts)[self.fmt] for label,plan in plans.items()}
        last_method=(selected_state.get('runner',{}).get('history') or [{}])[-1].get('method')
        summary=dict(format=self.fmt,status=overall_status(reports),controls=reports,selected_kind=selected_kind,
            selection=selection,
            pretraining_complete=self.state['effective'],bc_games_collected=len(self.teacher_evidence()),bc_games_required=self.config['bc_games'][self.fmt],
            version=selected_version,evaluation_engine=evaluation_engine,
            evaluation_scope='lite Astra comparison only; not native Wesnoth playing strength' if evaluation_engine=='lite' else 'native Wesnoth 1.18.8 comparison',
            checkpoint=str(frozen),checkpoint_sha256=sha256(frozen),parameters=sum(p.numel() for p in selected.parameters()),
            feature_version=schema()['version'],error=self.state['error'],clock=self.clock,
            forced_ppo=self.state.get('forced_ppo'),phase_history=self.state.get('phase_history',[]),
            bc_gate=read_json(self.directory/'bc_gate.json') if (self.directory/'bc_gate.json').exists() else None)
        from .report import write_profile_report
        write_profile_report(self.directory/'report',summary,self.state['history'])
        self.state['stage']='finished';self.state['status']=summary['status'];self.save();return summary

    def run(self):
        if self.state['stage']=='finished': return read_json(self.directory/'report/summary.json')
        if self.state['stage']=='failed':
            self.state['stage']=self.state.pop('failed_stage')
            self.state['error']=None
            self.state.pop('status',None)
        try:
            from .phases import apply_phase
            apply_phase(self)
            if self.state['stage'].endswith('_complete'): return read_json(self.directory/'report/summary.json')
            if self.state.get('phase')=='evaluate':
                if self.state.get('pending_train'): self.finish_train()
                return self.final_evaluation()
            if self.state['stage']=='calibration':
                references=self.reference_opponents if self.teacher_record['kind']=='wesnoth_default_rca' else self.fixed
                if len(references)==1:
                    write_json(self.directory/'controls.json',dict(controls={self.fmt:references[0]},calibration='single fixed reference'))
                    self.state['stage']='bc';self.save()
            if self.state['stage']=='calibration':
                jobs=calibration_jobs(self.directory,references,self.config['calibration_blocks'],self.config['seed'],self.update_deadline(),self.exe,formats=[self.fmt])
                jobs,results=self.execute(jobs,'calibration')
                if len(results)==len(jobs) and all(r['status']=='complete' for r in results):
                    write_json(self.directory/'controls.json',choose_controls(jobs,results,references));self.state['stage']='bc';self.save()
                elif any(r['status']=='infrastructure_error' for r in results): raise RuntimeError('calibration failed')
            if self.state['stage'] in ('bc','ppo'): self.learn()
            if self.state.get('phase','auto') in ('bc','ppo'): return self.complete_phase()
            return self.final_evaluation()
        except KeyboardInterrupt: self.save();raise
        except Exception as exc:
            # The trainer process writes the one traceback (trainer_error.log); a
            # second copy here would duplicate the same stack under errors.log.
            self.state.update(failed_stage=self.state['stage'],stage='failed',status='trainer_failed',error=repr(exc))
            self.save()
            write_json(self.directory/'report/summary.json',dict(format=self.fmt,status='trainer_failed',
                version=self.state['version'],failed_stage=self.state['failed_stage'],error=self.state['error'],clock=self.clock))
            raise
