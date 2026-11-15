"""Audit the completed #352 single-intervention pilot without running any games."""
from collections import Counter, defaultdict
from functools import lru_cache
import json
from pathlib import Path
import sys
import tarfile

import torch

from learning.bc_anchor import weights_sha256
from learning.common import read_json, sha256
from learning.tasks import TASK_ID
from verification.duel_ppo_comparison_20261106.audit import board_digest, write_new

from audit_archive import paired, records, slot, terminal_points

APPROVED = '7f3c9274f4642b0be6dd6b94ab14e08af424dc379401ef4cee010d1ab911cbaa'


@lru_cache(maxsize=None)
def file_sha(path):
    return sha256(Path(path))


def rollout_key(job):
    meta=job['meta']
    seat=meta['seat']
    return [job['scenario_family'],job['game_family'],job['seed'],job['factions'],seat,
            job['learning']['sides'][str(seat)]['sampling_seed'],meta['map'],job['task_id']]


def cell(root, item, launch, frozen):
    cell=root/'cells'/item
    duel=cell/'duel'
    ledger=read_json(root/f'{item}-ledger.json')
    initial=read_json(cell/'initialization.json')
    branch=read_json(cell/'branch.json')
    arm=launch['cells'][item]
    assert initial['weights_sha256']==launch['bc']['weights_sha256'] and initial['optimizer_states']==0
    assert branch['reset_optimizer'] and branch['parent']==launch['parent']
    assert branch['checkpoints']['duel']['bc_endpoint']['sha256']==launch['bc']['checkpoint_sha256']
    settings=read_json(cell/'manifest.json')['config']
    expected=launch['stock_config']|dict(seed=arm['seed'],gae_lambda=.95,human_data=str(root/'human-empty'))
    hours=settings['hours']
    assert 0<hours<=.3
    assert {k:v for k,v in settings.items() if k!='hours'}==expected
    state=read_json(duel/'state.json')
    assert state['stage']=='ppo_complete' and not state['error'] and not state.get('forced_ppo')
    assert state['pending_train'] is None and state['pending_validation'] is None
    cut=read_json(cell/'budget.json')
    history=state['history'][cut['history_start']:]
    assert history==ledger['history'] and len(history)==10
    assert 0<ledger['wall_seconds']<=1080 and cut['admission_deadline']<cut['hard_deadline']
    raw=[r for r in records(duel/'jobs.jsonl') if r.get('meta',{}).get('phase') in ('ppo','validation')]
    replies={r['id']:r for r in raw}
    assert len(replies)==len(raw)==86
    identities=set()
    for i,h in enumerate(history):
        assert h['method']=='ppo' and h['committed_steps']>0 and h['learning_rate']==arm['lr']
        schedule=read_json(duel/'schedules'/f"ppo-batch-{h['batch']:06d}.json")
        assert len(schedule)==8 and [rollout_key(j) for j in schedule]==frozen[i]
        rows=0
        for j in schedule:
            seat=j['meta']['seat']
            assert j['task_id']==TASK_ID and j['max_turns']==30 and j['reward_config']['gae_lambda']==.95
            assert file_sha(j['bots'][2-seat])==launch['runtime']['astra']['teacher_parent_sha256']
            assert j['id'] not in identities
            r=replies[j['id']]
            terminal_points(j,r,seat)
            assert r['training_eligible']
            rows+=r['training_shard']['written']
            identities.add(j['id'])
        assert rows==h['eligible_decisions']
    sums={key:sum(h[key] for h in history) for key in ledger['totals']}
    assert sums==ledger['totals']
    assert len(identities)==80
    valid=read_json(duel/'schedules/validation-000040.json')
    assert len(valid)==6
    for j in valid:
        assert j['meta']['map']=='hamlets' and j['id'] not in identities
        terminal_points(j,replies[j['id']],j['meta']['policy_sides'][0])
        identities.add(j['id'])
    assert identities==replies.keys()
    endpoint_path=duel/'last_ppo.pt'
    endpoint=torch.load(endpoint_path,map_location='cpu',weights_only=False)
    digest=weights_sha256(endpoint['model'])
    assert digest==ledger['endpoint']['weights_sha256']==history[-1]['policy_sha256_after']
    assert file_sha(str(endpoint_path))==ledger['endpoint']['checkpoint_sha256']
    assert {g['lr'] for g in endpoint['optimizer']['param_groups']}=={arm['lr']}
    assert endpoint['runner']['version']==state['version']==48
    return dict(visits=sums['committed_decisions'],fresh=sums['eligible_decisions'],
                steps=sums['committed_steps'],planned=sums['planned_steps'],kl_stops=sums['kl_stopped'],
                rejected_visits=sums['inspected_decisions']-sums['committed_decisions'],
                endpoint=ledger['endpoint'],time=ledger['wall_seconds'])


def panel(root, launch, arms):
    schedule=read_json(root/'pilot-panel-schedule.json')
    raw=records(root/'pilot-panel-results.jsonl')
    answers={r['id']:r for r in raw}
    assert len(answers)==len(raw)==len(schedule)==320 and answers.keys()=={j['id'] for j in schedule}
    results,tallies=defaultdict(dict),defaultdict(Counter)
    for j,frozen in zip(schedule,launch['panel_design'],strict=True):
        m=j['meta']
        seat,=m['policy_sides']
        role=m['role']
        key=slot(j)
        identity=[j['id'],m['map'],m['board_sha256'],j['scenario_family'],j['seed'],
                  j['factions'],m['policy_sides'],role,j['task_id']]
        assert identity==frozen and key not in results[role] and answers[j['id']]['meta']==m
        assert m['board_sha256']==board_digest(j['map_override'])
        assert not j.get('learning') and not j.get('shard') and j['score_only_policy'] and j['score_only_astra']
        assert file_sha(j['bots'][2-seat])==launch['runtime']['astra']['teacher_parent_sha256']
        expected=launch['bc'] if role=='bc' else arms[role]['endpoint']
        model=Path(j['bots'][seat-1]).parent/'model.pt'
        assert m['weights_sha256']==expected['weights_sha256']
        assert model.is_file()
        points=terminal_points(j,answers[j['id']],seat)
        state=answers[j['id']]['result']
        if state['reason']=='turn_limit':
            assert state['turns']==31 and points==1
        results[role][key]=points
        tallies[role,m['map']][points]+=1
        tallies[role,m['map']]['round_cap']+=int(state['reason']=='turn_limit')
    roles={'bc':launch['bc']}|{name:a['endpoint'] for name,a in arms.items()}
    for name,expected in roles.items():
        model=torch.load(root/'policies'/name/'model.pt',map_location='cpu',weights_only=False)
        assert weights_sha256(model['model'])==expected['weights_sha256']
    assert all(len(x)==64 and x.keys()==results['bc'].keys() for x in results.values())
    map_result={board:{role:dict(tallies[role,board]) for role in roles} for board in launch['boards']}
    return results,map_result


def archive(root,destination,launcher):
    with tarfile.open(destination,'x:gz',compresslevel=1) as tar:
        for name in ('pilot-launch.json','pilot-start.json','pilot-result.json',
                     'pilot-panel-schedule.json','pilot-panel-results.jsonl','pilot-panel-results.throughput.jsonl'):
            path=root/name
            tar.add(path,arcname=name)
        for p in sorted(root.glob('*-ledger.json')):
            tar.add(p,arcname=p.name)
        for cell in sorted((root/'cells').iterdir()):
            files=[*cell.glob('*.json'),*cell.glob('*.jsonl'),*(cell/'duel/schedules').glob('*.json'),
                   *(cell/'duel/validation').glob('*.json'),cell/'duel/jobs.jsonl',cell/'duel/state.json']
            for p in sorted(files):
                if p.is_file(): tar.add(p,arcname=str(p.relative_to(root)))
        for name in ('pilot-start.utc','pilot-launcher.exit','pilot-launcher.log','pilot-output.txt',
                     'pilot-recovered-start.utc','pilot-recovered-launcher.exit','pilot-recovered-launcher.log'):
            p=launcher/name
            tar.add(p,arcname=f'launcher/{name}')
    return dict(sha256=sha256(destination), bytes=destination.stat().st_size)


def main(root, launcher, review):
    assert (launcher/'pilot-recovered-launcher.exit').read_text().strip()=='0'
    assert not (launcher/'pilot/cells').exists() and not (launcher/'pilot/pilot-panel-results.jsonl').exists()
    path=root/'pilot-launch.json'
    assert sha256(path)==sha256(launcher/'pilot/pilot-launch.json')==APPROVED
    m=read_json(path)
    result=read_json(root/'pilot-result.json')
    assert result['status']=='complete' and result['launch_sha256']==APPROVED and result['wall_seconds']<=7190
    arms={r:cell(root,r,m,m['train_design'][str(m['cells'][r]['seed'])]) for r in m['order']}
    scores,maps=panel(root,m,arms)
    seeds=sorted(int(k) for k in m['train_design'])
    stock=[scores[f'stock-{s}'] for s in seeds]
    half=[scores[f'half-{s}'] for s in seeds]
    contrast=paired(half,stock)
    assert contrast==result['score'] and paired(half,[scores['bc']]*2)==result['half_vs_bc']
    points={name:sum(data.values()) for name,data in scores.items()}
    differences={}
    for s in seeds:
        a,b=arms[f'half-{s}'],arms[f'stock-{s}']
        exact_visits=a['visits']*b['fresh']-b['visits']*a['fresh']
        exact_points=points[f'half-{s}']-points[f'stock-{s}']
        differences[s]=dict(delta_passes=a['visits']/a['fresh']-b['visits']/b['fresh'],
                            raw_points_delta=exact_points,release=exact_visits>0 and exact_points>0)
    release=all(v['release'] for v in differences.values())
    assert release==result['release_confirmation']
    assert [x['delta_passes'] for x in differences.values()]==result['passes_delta']
    pack=archive(root,review/'raw-metadata.tar.gz',launcher)
    summary=dict(manifest_sha256=APPROVED,review_mode='read-only',archive=pack,arms=arms,
                 points=points,points_max=192,by_map=maps,seed_acceptance=differences,
                 pilot=result,rollout_games=320,internal_validation_games=24,scored_games=320)
    write_new(review/'review.json',summary)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('by_map',)},indent=2))


if __name__=='__main__':
    torch.set_num_threads(1)
    main(*(Path(x).resolve() for x in sys.argv[1:]))
