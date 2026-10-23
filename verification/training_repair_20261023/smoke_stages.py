"""Bounded real-Astra/lite stage handoff, two real PPO batches and final selection.

This is integration evidence, not BC convergence or a formal strength panel.
The normal quality gates stay false; PPO is entered through the explicit force
command. All optimizer work, trajectories, checkpoints and comparisons are real.
"""
import collections, json, pathlib, time
import torch
from learning.common import ROOT, write_json, read_json, sha256
from learning.data import split
from learning.experiment import FormatExperiment, default_config
from learning.export import load_model
from learning.sample import play_job
from learning.schedule import teacher_jobs
from learning.__main__ import main

OUT=ROOT/'verification/training_repair_20261023/stage_outputs_v2'
OUT.mkdir(parents=True,exist_ok=True)


def collect(jobs, log):
    log=pathlib.Path(log);log.parent.mkdir(parents=True,exist_ok=True)
    results=[]
    with log.open('a',encoding='utf-8') as stream:
        for job in jobs:
            result=play_job(job)
            stream.write(json.dumps(result)+'\n');stream.flush()
            assert result['status']=='complete', (job['id'], result)
            results.append(result)
    return results


class Smoke(FormatExperiment):
    def execute(self,jobs,name):
        # One full rotation block exercises the final-evaluation implementation
        # while retaining its >=30-block formal acceptance requirement.
        if name.startswith('validation-') or name=='final':
            jobs=[j for j in jobs if j['meta']['block']==0]
        for j in jobs:
            j['max_turns']=3
        return super().execute(jobs,name)

    def validate_model(self,method):
        super().validate_model(method)
        count=sum(h['method']=='ppo' for h in self.state['history'])
        if method=='bc' or count>=2:
            # End only this diagnostic phase after its requested work. No shared
            # clock or frozen manifest change; the next CLI command grants time.
            self.state['phase_deadline']=time.time()-1
            self.save()


all_results={}
for fmt in ('duel','ffa4','team2v2'):
    root=OUT/fmt
    root.mkdir(exist_ok=True)
    cfg=default_config('cpu')
    cfg.update(formats=[fmt],phase='bc',epochs=1,minibatch=32,validation_interval=1,
               bc_batch_games=2,bc_records=128,bc_validation_records=128)
    cfg['bc_games']={f:2 for f in ('duel','ffa4','team2v2')}
    # Require at least one real train family in the two-game diagnostic corpus.
    for seed in range(20261023,20261123):
        trial=teacher_jobs(root/fmt,['gpt6astra.zip'],['gpt6astra.zip'],'unused',0,seed,
                           time.time()+1000,'unused',formats=[fmt],count=2,index_stride=2)
        if any(split(j['game_family'])=='train' for j in trial):
            cfg['seed']=seed;break
    clock=dict(started=time.time(),update_deadline=time.time()+900,deadline=time.time()+1000)
    manifest=dict(config=cfg,features=__import__('learning.features',fromlist=['schema']).schema(),
                  opponents=[dict(path=str(ROOT/'opponents/gpt6astra.zip'))],
                  baseline=dict(path=str(ROOT/'.runtime/install/bin/wesnoth')))
    if (root/'manifest.json').exists():
        manifest=read_json(root/'manifest.json');cfg=manifest['config'];clock=read_json(root/'clock.json')
        runner=Smoke(root/fmt,fmt,manifest,clock,collect,resume=True)
        bc=read_json(root/fmt/'report/summary.json')
    else:
        write_json(root/'manifest.json',manifest);write_json(root/'clock.json',clock)
        runner=Smoke(root/fmt,fmt,manifest,clock,collect)
        runner.state['version']=99  # Directly exercise promotion validation at v100.
        runner.save()
        bc=runner.run()
    assert bc['status']=='stage_complete' and runner.state['stage']=='bc_complete'
    assert [h['method'] for h in runner.state['history']]==['bc']
    assert not runner.state['effective'], 'short smoke must not masquerade as qualified BC'
    assert runner.state['history'][0]['updates']>0
    bc_hash=sha256(root/fmt/'last_bc.pt')
    try:
        main(['phase','ppo','--run-dir',str(root),'--hours','.25'])
        raise AssertionError('unqualified PPO request was accepted')
    except SystemExit as exc:
        assert exc.code==2
    main(['phase','ppo','--run-dir',str(root),'--force','--reason','isolated real stage-handoff smoke','--hours','.25'])
    runner=Smoke(root/fmt,fmt,manifest,clock,collect,resume=True)
    resumed_optimizer_steps=runner.state['counters']['optimizer_steps']
    ppo=runner.run()
    methods=[h['method'] for h in runner.state['history']]
    assert methods==['bc','ppo','ppo'], methods
    assert ppo['status']=='stage_complete' and runner.state['stage']=='ppo_complete'
    assert all(h['updates']>0 for h in runner.state['history'])
    assert runner.state['counters']['optimizer_steps']>resumed_optimizer_steps
    assert not runner.state['effective'] and runner.state.get('forced_ppo')
    assert sha256(root/fmt/'last_bc.pt')==bc_hash
    main(['phase','evaluate','--run-dir',str(root),'--hours','.25'])
    runner=Smoke(root/fmt,fmt,manifest,clock,collect,resume=True)
    final=runner.run()
    selected,selected_state=load_model(root/fmt/'selected.pt',fmt)
    assert runner.state['stage']=='finished'
    assert final['selected_kind']=='ppo' and final['version']==102, final
    assert selected_state['runner']['history'][-1]['method']=='ppo'
    assert sha256(root/fmt/'selected.pt')==sha256(root/fmt/'last_ppo.pt')
    assert not final['pretraining_complete'] and final['forced_ppo']
    assert final['controls']['gpt6astra']['planned_blocks']==30
    assert final['controls']['gpt6astra']['blocks']==1
    assert final['controls']['gpt6astra']['status']=='inconclusive'
    all_results[fmt]=dict(methods=methods,bc_gate=read_json(root/fmt/'bc_gate.json'),
        optimizer_steps=runner.state['counters']['optimizer_steps'],
        updates=[h['updates'] for h in runner.state['history']],
        final=final,selected_sha256=sha256(root/fmt/'selected.pt'),
        qualifier='explicit forced PPO; real updates; bounded incomplete final panel')
    write_json(OUT/'summary.json',all_results)
    print('STAGE_SMOKE_PASS',fmt,methods,'selected',final['version'],flush=True)
print('ALL_STAGE_SMOKES_PASS',flush=True)
