import copy
import json
from multiprocessing import get_context
from pathlib import Path
import random
import tempfile
import time
import unittest
from unittest.mock import patch
import torch
from learning.common import ROOT, TAIL_CHUNK, repair_tail, write_json, read_json
from learning.formats import FORMATS
from learning.experiment import FormatExperiment, default_config, run_lock, coverage_gate, opening_gate, human_coverage
from learning.coordinator import FairScheduler, broker, Experiment
from learning import coordinator
from learning.export import load_model
from learning.sample import collect
from learning.train import train, checkpoint
from tests.test_core import record


def fake_game(job):
    time.sleep(.03)
    return dict(id=job['id'],status='complete',pid=__import__('os').getpid())


def fake_trainer(fmt,directory,requests,replies,failed=False):
    for stage in range(2):
        jobs=[dict(id=f'{fmt}-{stage}-{i}',deadline=time.time()+120) for i in range(3)]
        requests.put((fmt,jobs,str(Path(directory)/(fmt+'.jsonl'))))
        reply=replies.get(timeout=120)
        if len(reply['results'])!=3: raise RuntimeError('lost results')
        if failed: raise SystemExit(2)


class ExperimentTests(unittest.TestCase):
    def test_resume_and_format_isolation(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);write_json(root/'manifest.json',{})
            config=default_config()|dict(device='cpu',epochs=1,minibatch=2)
            manifest=dict(config=config,opponents=[dict(path='gpt6astra.zip')],baseline=dict(path='unused'))
            clock=dict(started=1.,update_deadline=3000000000.,deadline=3000001000.)
            # Avoid exporting fixtures; this test concerns checkpoints only.
            with patch.object(FormatExperiment,'ensure_export',return_value='unused'):
                runners={f:FormatExperiment(root/f,f,manifest,clock,None) for f in FORMATS}
                before={f:copy.deepcopy(r.model.state_dict()) for f,r in runners.items()}
                r=runners['duel'];train(r.model,r.optimizer,[record(index=i) for i in range(4)],'bc',epochs=1,minibatch=2)
                r.state['snapshots']=['duel-only'];r.save()
                for fmt in ('ffa4','team2v2'):
                    self.assertFalse(runners[fmt].optimizer.state)
                    self.assertEqual(runners[fmt].state['snapshots'],[])
                    for key,v in before[fmt].items(): self.assertTrue(torch.equal(v,runners[fmt].model.state_dict()[key]))
                expected_random=random.getstate();expected_torch=torch.get_rng_state()
                resumed=FormatExperiment(root/'duel','duel',manifest,clock,None,resume=True)
                self.assertEqual(resumed.clock,clock);self.assertTrue(resumed.optimizer.state)
                self.assertEqual(resumed.state['snapshots'],['duel-only'])
                self.assertEqual(random.getstate(),expected_random);self.assertTrue(torch.equal(torch.get_rng_state(),expected_torch))
                with self.assertRaises(ValueError): load_model(root/'duel/latest.pt','ffa4')
                with self.assertRaises(ValueError): train(r.model,r.optimizer,[dict(record(),format='ffa4')],'bc')

    def test_scheduler_round_robin_and_global_process_limit(self):
        with tempfile.TemporaryDirectory() as temp:
            ctx=get_context('spawn');requests=ctx.Queue();replies={f:ctx.Queue() for f in FORMATS};processes={}
            for f in FORMATS:
                processes[f]=ctx.Process(target=fake_trainer,args=(f,temp,requests,replies[f],f=='ffa4'));processes[f].start()
            try:
                metrics=broker(processes,requests,replies,4,temp,play=fake_game)
            finally:
                for p in processes.values(): p.join(30)
            self.assertLessEqual(metrics['peak_native_games'],4)
            self.assertGreaterEqual(metrics['peak_native_games'],2)
            self.assertEqual(processes['duel'].exitcode,0);self.assertEqual(processes['team2v2'].exitcode,0)
            self.assertEqual(processes['ffa4'].exitcode,2)
            self.assertEqual(len(Path(temp,'duel.jsonl').read_text().splitlines()),6)
            scheduler=FairScheduler(FORMATS)
            for f in FORMATS: scheduler.add(f,[1,2])
            self.assertEqual([scheduler.pop()[0] for _ in range(6)],list(FORMATS)*2)
            requests.close()
            for q in replies.values(): q.close()

    def test_tail_repair_drops_only_the_unterminated_line(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            complete=root/'complete.jsonl';complete.write_bytes(b'{"id":1}\n{"id":2}\n')
            repair_tail(complete);self.assertEqual(complete.read_bytes(),b'{"id":1}\n{"id":2}\n')
            partial=root/'partial.jsonl';partial.write_bytes(b'{"id":1}\n{"id":2}\n{"id":3"')
            repair_tail(partial);self.assertEqual(partial.read_bytes(),b'{"id":1}\n{"id":2}\n')
            longtail=root/'longtail.jsonl';longtail.write_bytes(b'{"id":1}\n'+b'x'*(TAIL_CHUNK+4096))
            repair_tail(longtail);self.assertEqual(longtail.read_bytes(),b'{"id":1}\n')
            absent=root/'absent.jsonl';repair_tail(absent);self.assertFalse(absent.exists())

    def test_scheduler_repairs_each_log_once(self):
        with tempfile.TemporaryDirectory() as temp:
            ctx=get_context('spawn');requests=ctx.Queue();replies={f:ctx.Queue() for f in FORMATS};processes={}
            for f in FORMATS:
                (Path(temp)/(f+'.jsonl')).write_text('{"id":"partial"')
                processes[f]=ctx.Process(target=fake_trainer,args=(f,temp,requests,replies[f],f=='ffa4'));processes[f].start()
            original=coordinator.repair_tail;repaired=[]
            def counting(path):
                repaired.append(str(path));original(path)
            try:
                with patch.object(coordinator,'repair_tail',counting):
                    broker(processes,requests,replies,4,temp,play=fake_game)
            finally:
                for p in processes.values(): p.join(30)
            self.assertEqual(sorted(repaired),sorted(str(Path(temp)/(f+'.jsonl')) for f in FORMATS))
            for f in FORMATS:
                lines=(Path(temp)/(f+'.jsonl')).read_text().splitlines()
                self.assertTrue(lines)
                self.assertFalse(any('partial' in line for line in lines))
                for line in lines: json.loads(line)
            requests.close()
            for q in replies.values(): q.close()

    def test_collect_repairs_the_batch_log_tail(self):
        with tempfile.TemporaryDirectory() as temp:
            log=Path(temp,'batch.jsonl');log.write_bytes(b'{"id":1}\n{"id":2"')
            with patch('learning.sample.repair_tail',wraps=repair_tail) as repaired:
                self.assertEqual(collect([],4,str(log)),[])
            self.assertEqual([str(c.args[0]) for c in repaired.call_args_list],[str(log)])
            self.assertEqual(log.read_bytes(),b'{"id":1}\n')

    def test_execute_retries_infrastructure_errors_and_discards_their_shards(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);write_json(root/'manifest.json',{})
            config=default_config()|dict(device='cpu')
            manifest=dict(config=config,opponents=[dict(path='gpt6astra.zip')],baseline=dict(path='unused'))
            clock=dict(started=1.,update_deadline=3000000000.,deadline=3000001000.)
            with patch.object(FormatExperiment,'ensure_export',return_value='unused'), \
                    patch('learning.rules_catalog.resolve_dir',return_value=root), \
                    patch('learning.experiment.freeze_schedule',side_effect=lambda path,jobs: write_json(path,jobs)):
                runner=FormatExperiment(root/'duel','duel',manifest,clock,None)
                (root/'duel/schedules').mkdir(parents=True,exist_ok=True)
                job=dict(id='job-1',shard=str(root/'job-1.jsonl.gz'),bots=['a','b'],deadline=clock['deadline'])
                job2=dict(id='job-2',bots=['a','b'],deadline=clock['deadline'])
                with __import__('gzip').open(job['shard'],'wt',encoding='utf-8') as handle:
                    handle.write(json.dumps(dict(format='duel',source='astra',engine_id='lite-0.2',
                                                 game_family='family-3',game_id='retry-1',side=1))+'\n')
                (root/'duel/jobs.jsonl').write_text(json.dumps(dict(id='job-1',status='infrastructure_error'))+'\n')
                seen={}
                def collect(pending,log):
                    seen['exists']=Path(job['shard']).exists()
                    with open(log,'a') as handle:
                        for item in pending: handle.write(json.dumps(dict(id=item['id'],status='complete'))+'\n')
                runner.collector=collect
                jobs,results=runner.execute([job,job2],'retry')
                self.assertFalse(seen['exists'])
                self.assertEqual([r['status'] for r in results],['complete','complete'])
                self.assertEqual(len((root/'duel/jobs.jsonl').read_text().splitlines()),3)

    def test_gates_fail_without_evidence(self):
        self.assertFalse(coverage_gate([])['passed']);self.assertFalse(opening_gate([])['passed'])
        c=dict(total=100,matched=90,kinds={k:dict(total=10,matched=8) for k in ('recruit','move','attack')})
        self.assertTrue(coverage_gate([dict(coverage=c)])['passed'])
        c['kinds']['move']['matched']=7
        self.assertFalse(coverage_gate([dict(coverage=c)])['passed'])
        with tempfile.TemporaryDirectory() as temp:
            write_json(Path(temp)/'import.json',dict(games=[dict(format='duel',status='imported',coverage=c['kinds']),
                dict(format='ffa4',status='prepared_pending_native_replay')]))
            self.assertEqual(len(human_coverage(temp,'duel')),1)
            self.assertEqual(human_coverage(temp,'ffa4'),[])
            self.assertFalse(coverage_gate(human_coverage(temp,'duel'))['passed'])

    def test_simultaneous_run_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            with run_lock(temp):
                with self.assertRaises(ValueError):
                    with run_lock(temp): pass
