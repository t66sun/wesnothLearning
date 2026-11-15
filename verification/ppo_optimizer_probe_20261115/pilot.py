"""Freeze an online pilot of one PPO intervention. Prepare performs no game or update."""
from collections import defaultdict
from copy import deepcopy
from functools import partial
import json
from pathlib import Path
import sys
import tarfile
import time
from unittest.mock import patch

import torch

from learning import coordinator, ppo
from learning.common import read_json, sha256
from learning.export import export, load_model
from learning.lite_policy import game_spec
from learning.maps import bind_scenario, run_family
from learning.phases import request_phase
from learning.schedule import compose_training_scenario
from learning.sample import collect
from learning.tasks import TASK_ID
from verification.duel_ppo_comparison_20261106.audit import board_digest, write_new
from verification.duel_ppo_comparison_20261106.contract import production_trainer
from verification.duel_ppo_comparison_20261106.panels import role
from verification.ppo_batch_comparison_20261107.panels import plan_jobs
from verification.ppo_batch_contract_20261107 import driver as paired
from verification.ppo_terminal_return_20261108.driver import PARENT, TerminalReturnExperiment

from audit_archive import RUNS, paired as paired_scores, records, slot, terminal_points

OLD = RUNS['349']
sys.path.append(str(OLD.parent/'adapter/verification/ppo_vs_bc_20261115'))
from lineage import worker

HERE = Path(__file__).resolve().parent
SEEDS = (2026111861, 2026111862)
BATCHES = 10
N_ROLLOUT = 8
MAPS = ('fallenstar_lake','sullas_ruins')
BLOCKS = tuple(range(0,30,2)) + (29,)
LIMIT = dict(preflight=300,cell=1080,panel=2100,audit=480,total=7200)
CELLS = {
    f'{arm}-{seed}':dict(arm=arm,seed=seed,lr=1e-4 if arm=='stock' else 5e-5)
    for seed,order in zip(SEEDS,(('stock','half'),('half','stock'))) for arm in order
}
RESULT_SHA = '871237bc2cd9e813dcace6c43c5b2252d8d848214c212bc45150fd1dff626fdf'


def archive_identity(path, commit):
    with tarfile.open(path) as tar:
        assert tar.pax_headers['comment']==commit
        for file in (HERE/'pilot.py', HERE.parent/'ppo_diagnosis_20261115/audit_archive.py'):
            member=f'verification/{file.parent.name}/{file.name}'
            assert file.read_bytes()==tar.extractfile(member).read()
    return dict(path=str(path),sha256=sha256(path),commit=commit)


def rate_update(original, rate):
    def overridden(model, optimizer, *args, **kwargs):
        for group in optimizer.param_groups:
            group['lr']=rate
        result=original(model,optimizer,*args,**kwargs)
        return dict(result,learning_rate=rate)
    return overridden


class PilotExperiment(TerminalReturnExperiment):
    def execute(self,jobs,name):
        if name.startswith('ppo-batch-'):
            cell=self.directory.parent
            root=cell.parent.parent
            budget=read_json(cell/'budget.json')
            manifest=read_json(root/'pilot-launch.json')
            n=self.state['batch']-budget['first_batch']
            assert 0<=n<BATCHES, 'fixed pilot game budget exhausted'
            expected=manifest['train_design'][str(manifest['cells'][cell.name]['seed'])][n]
            assert [prepared_identity(job,manifest['runtime']['rules']['path']) for job in jobs]==expected
        return super().execute(jobs,name)


def trainer_main(directory,*args,**kwargs):
    run=Path(directory).parent
    launch=read_json(run.parent.parent/'pilot-launch.json')
    coordinator.FormatExperiment=PilotExperiment
    with patch.object(ppo,'update',rate_update(ppo.update,launch['cells'][run.name]['lr'])):
        return production_trainer(directory,*args,**kwargs)


def resume_arm(run):
    with patch.object(coordinator,'trainer_main',trainer_main):
        return coordinator.Experiment(run,resume=True).run()


def train_identity(job):
    meta=job['meta']
    side=meta['seat']
    return [job['scenario_family'],job['game_family'],job['seed'],job['factions'],side,
            job['learning']['sides'][str(side)]['sampling_seed'],meta['map'],job['task_id']]


def prepared_identity(job,rules):
    spec=dict(deepcopy(job),task_id=TASK_ID,engine='lite',rules_dir=rules)
    compose_training_scenario(spec,max_turns=30)
    return train_identity(spec)


def training_template(output,control,wesnoth,rules):
    doc={}
    for seed in SEEDS:
        doc[str(seed)]=[
            [prepared_identity(j,rules) for j in paired.ordinal_rollouts(
                output,'PilotLearner',['PilotLearner'],[control],'Support','v38',batch,seed,0,
                wesnoth,N_ROLLOUT,first_batch=0)] for batch in range(BATCHES)]
        assert len({j[1] for batch in doc[str(seed)] for j in batch})==80
    return doc


def make_panel(output,manifest,role_info,deadline):
    astra=manifest['runtime']['astra']['path']
    rules=manifest['runtime']['rules']['path']
    result=[]
    for index,name in enumerate(MAPS):
        board=manifest['boards'][name]
        for key, policy in role_info.items():
            for j in plan_jobs(output/'games',policy['addon'],astra,manifest['wesnoth'],policy['weights'],deadline,
                               rules,'holdout',board):
                m=j['meta']
                if m['block'] not in BLOCKS:
                    continue
                seat=m['policy_sides'][0]
                j['id']=f'{name}-{key}-{m["block"]}-{seat}'
                j['output']=str(output/'games'/f"{j['id']}.json")
                j['seed']=2026111820+len(BLOCKS)*index+BLOCKS.index(m['block'])
                j['game_family']=run_family(j)
                bind_scenario(j)
                m.update(role=key,board_sha256=board['board_sha256'])
                result.append(j)
    return sorted(result,key=lambda j:(j['meta']['block'],j['meta']['map'],j['meta']['rotation'],j['meta']['role']))


def panel_identity(job):
    m=job['meta']
    return [job['id'],m['map'],m['board_sha256'],job['scenario_family'],job['seed'],
            job['factions'],m['policy_sides'],m['role'],job['task_id']]


def validate_templates(output, manifest):
    roles={k:dict(addon=f'pilot-{k}',weights=k) for k in ['bc',*CELLS]}
    pol=make_panel(output,manifest,roles,0)
    assert len(pol)==len({j['id'] for j in pol})==320
    model=read_json(Path(manifest['runtime']['rules']['path'])/'rules.json')
    matches=defaultdict(set)
    for j in pol:
        m=j['meta']
        assert j['task_id']==TASK_ID and j['score_only_astra'] and j['score_only_policy'] and 'learning' not in j
        spec=game_spec(j,model)
        assert len(spec['units'])==2 and all(u['leader'] for u in spec['units'])
        matches[m['map'],m['block'],m['rotation']].add((j['scenario_family'],j['seed'],tuple(j['factions'])))
    assert len(matches)==64 and all(len(s)==1 for s in matches.values())
    assert all(matches[map_,i,0]==matches[map_,i,1] for map_ in MAPS for i in BLOCKS)
    return [panel_identity(j) for j in pol]


def prepare(output,archive,commit,evidence):
    assert sha256(evidence)==RESULT_SHA and read_json(evidence)['followup_warranted']
    old=read_json(OLD/'launch.json')
    assert worker()==old['runtime']
    source=archive_identity(archive,commit)
    launch=read_json(RUNS['306']/'launch.json')
    assert role(old['roles']['bc']['path'])==old['roles']['bc']
    assert launch['endpoint']['checkpoint_sha256']==old['roles']['bc']['checkpoint_sha256']
    assert ppo.KL_LIMIT==.02
    boards={}
    for name in MAPS:
        original=old['boards'][name]
        p=Path(original['path'])
        b=read_json(p)
        assert sha256(p)==original['file_sha256'] and board_digest(b['board'])==original['board_sha256']
        boards[name]=b | {k:original[k] for k in ('file_sha256','board_sha256')}
    wesnoth=read_json(OLD/'schedule.json')[0]['wesnoth']
    frozen=dict(source=source,stock_config=launch['config'],endpoint=launch['endpoint'],parent=str(PARENT),
                runtime=old['runtime'],bc=old['roles']['bc'],boards=boards,
                cells=CELLS,order=list(CELLS),seconds=LIMIT,wesnoth=wesnoth,
                rollout_games=320,internal_validation_games=24,panel_games=320,
                eligible_probe_sha256=RESULT_SHA,confirmation_reserve=(
                '/home/tongshu/acceptance/ppo-diagnosis-20261115-Z8O0k3/capture/confirmation-reserve.json'))
    reserve=Path(frozen['confirmation_reserve'])
    frozen['reserve_sha256']=sha256(reserve)
    assert {b['board_sha256'] for b in read_json(reserve).values()}.isdisjoint(b['board_sha256'] for b in boards.values())
    frozen['train_design']=training_template(output,old['runtime']['astra']['path'],wesnoth,old['runtime']['rules']['path'])
    frozen['panel_design']=validate_templates(output,frozen)
    new_seeds={row[4] for row in frozen['panel_design']}
    assert len(new_seeds)==32 and new_seeds.isdisjoint(j['seed'] for j in read_json(OLD/'schedule.json'))
    output.mkdir(exist_ok=False)
    write_new(output/'pilot-launch.json',frozen)
    print(json.dumps(dict(sha256=sha256(output/'pilot-launch.json'),
                          train_slots_per_seed=80,paired_score_slots=64,planned_games=664,
                          games_started=0,optimizer_updates=0),indent=2))


def settle(cell, manifest):
    d=cell/'duel'
    state=read_json(d/'state.json')
    assert state['stage']=='ppo_complete' and not state['error']
    assert state['pending_train'] is None and state['pending_validation'] is None
    budget=read_json(cell/'budget.json')
    history=state['history'][budget['history_start']:]
    assert len(history)==BATCHES and all(h['method']=='ppo' and h['committed_steps']>0 for h in history)
    config=manifest['cells'][cell.name]
    assert all(h['learning_rate']==config['lr'] for h in history)
    assert read_json(cell/'initialization.json')['weights_sha256']==manifest['bc']['weights_sha256']
    receipts={r['id']:r for r in records(d/'jobs.jsonl') if r.get('meta',{}).get('phase') in ('ppo','validation')}
    visited=set()
    for n,entry in enumerate(history):
        schedule=read_json(d/'schedules'/f"ppo-batch-{entry['batch']:06}.json")
        assert [train_identity(j) for j in schedule]==manifest['train_design'][str(config['seed'])][n]
        rows=0
        for j in schedule:
            reply=receipts[j['id']]
            terminal_points(j,reply,j['meta']['seat'])
            assert reply['training_eligible']
            rows+=reply['training_shard']['written']
            visited.add(j['id'])
        assert rows==entry['eligible_decisions']
    vseen=set()
    for p in (d/'schedules').glob('validation-*.json'):
        for job in read_json(p):
            terminal_points(job,receipts[job['id']],job['meta']['policy_sides'][0])
            vseen.add(job['id'])
    assert len(visited)==80 and len(vseen)==6 and set(receipts)==visited|vseen
    scored=role(d/'last_ppo.pt')
    assert scored['weights_sha256']==history[-1]['policy_sha256_after']
    totals={k:sum(h[k] for h in history) for k in ('eligible_decisions','committed_decisions',
               'inspected_decisions','committed_steps','planned_steps','kl_stopped')}
    return dict(endpoint=scored,totals=totals,history=history,
                effective_passes=totals['committed_decisions']/totals['eligible_decisions'])


def run(output, digest):
    started=time.time()
    launch_path=output/'pilot-launch.json'
    assert sha256(launch_path)==digest
    m=read_json(launch_path)
    a=m['source']
    assert archive_identity(Path(a['path']),a['commit'])==a and worker()==m['runtime']
    assert sha256(Path(m['confirmation_reserve']))==m['reserve_sha256']
    assert role(m['bc']['path'])==m['bc'] and validate_templates(output,m)==m['panel_design']
    write_new(output/'pilot-start.json',dict(started=started,launch_sha256=digest))
    empty=output/'human-empty'
    empty.mkdir()
    assert time.time()-started<=LIMIT['preflight']
    audits={}
    for name in m['order']:
        config=m['cells'][name]
        cell=output/'cells'/name
        start=time.time()
        cutoff=min(start+LIMIT['cell'],started+LIMIT['total']-LIMIT['audit']-LIMIT['panel'])
        with patch.object(paired,'resume_arm',resume_arm), patch.object(
             paired,'request_phase',partial(request_phase,ppo_batches=BATCHES)), patch.object(
             paired,'configuration',lambda ignored,seed,hours:m['stock_config']|
                  dict(seed=seed,hours=hours,gae_lambda=.95,human_data=str(empty))):
            status=paired.start_arm(cell,PARENT,empty,m['endpoint'],seed=config['seed'],rollout_games=8,
                                    admission=cutoff-120,deadline=cutoff)
        assert status['status']=='stage_complete' and time.time()<=cutoff
        result=settle(cell,m)
        write_new(output/f'{name}-ledger.json',result | dict(wall_seconds=time.time()-start))
        audits[name]=result
    armed=time.time()
    deadline=min(armed+LIMIT['panel'],started+LIMIT['total']-LIMIT['audit'])
    exported={}
    for name,snapshot in {'bc':m['bc'],**{k:a['endpoint'] for k,a in audits.items()}}.items():
        assert role(snapshot['path'])==snapshot
        model,state=load_model(Path(snapshot['path']),'duel')
        where=output/'policies'/name
        export(model,where,name='DuelPilot',mode='greedy',package=False,version=str(snapshot['version']))
        torch.save(dict(model=model.state_dict(),features=state['features'],
                        architecture=state['architecture'],format='duel'),where/'model.pt')
        exported[name]=dict(addon=str(where/'DuelPilot'),weights=snapshot['weights_sha256'])
    jobs=make_panel(output,m,exported,deadline)
    assert [panel_identity(j) for j in jobs]==m['panel_design']
    write_new(output/'pilot-panel-schedule.json',jobs)
    answers=collect(jobs,8,output/'pilot-panel-results.jsonl')
    finished=time.time()
    assert finished<=deadline and len(answers)==320
    lookup={r['id']:r for r in answers}
    assert lookup.keys()=={j['id'] for j in jobs}
    scored=defaultdict(dict)
    for j in jobs:
        m2=j['meta']
        r=lookup[j['id']]
        assert r['meta']==m2
        s=slot(j)
        assert s not in scored[m2['role']]
        scored[m2['role']][s]=terminal_points(j,r,s[4])
    hand=lambda arm:[scored[f'{arm}-{seed}'] for seed in SEEDS]
    comparison=paired_scores(hand('half'),hand('stock'))
    against_bc=paired_scores(hand('half'),[scored['bc']]*2)
    assert comparison['status']=='paired' and comparison['exact_slots']==64
    impulse=[audits[f'half-{seed}']['effective_passes']-audits[f'stock-{seed}']['effective_passes'] for seed in SEEDS]
    release=all(x>0 for x in impulse+comparison['per_seed'])
    assert time.time()<=min(finished+LIMIT['audit'],started+LIMIT['total'])
    write_new(output/'pilot-result.json',dict(status='complete',launch_sha256=digest,release_confirmation=release,
              passes_delta=impulse,score=comparison,half_vs_bc=against_bc,rollout_games=320,
              internal_validation_games=24,paired_score_games=320,wall_seconds=time.time()-started))


if __name__=='__main__':
    torch.set_num_threads(1)
    action,dirname,*args=sys.argv[1:]
    output=Path(dirname).resolve()
    if action=='prepare':
        prepare(output,Path(args[0]).resolve(),args[1],Path(args[2]).resolve())
    elif action=='run':
        run(output,args[0])
    else:
        raise ValueError('expected prepare or run')
