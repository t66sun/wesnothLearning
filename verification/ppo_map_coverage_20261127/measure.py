"""Audit the paired rollout prefix and score all eight roles on the held-out maps."""
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
import sys
import time

import torch

from learning.bc_anchor import weights_sha256
from learning.common import read_json, sha256
from learning.export import export, load_model
from learning.lite_policy import game_spec
from learning.maps import bind_scenario, run_family
from learning.sample import collect
from verification.duel_ppo_comparison_20261106.audit import board_digest, write_new
from verification.duel_ppo_comparison_20261106.panels import role
from verification.ppo_batch_comparison_20261107.panels import plan_jobs, roster
from audit_archive import paired, records, slot, terminal_points
from trial import GAMES, GROUP, ORDER, PARENT, SEEDS, RESERVE_SHA, worker

DIGEST='6f7f7a2c355abe5bc3a9856e30ccacf0d84f1573fe7e8287832f4f084a8dfea0'
PANEL_SECONDS=12600


def audit_cell(root, name, games, m):
    cell=root/'cells'/name
    directory=cell/'duel'
    checkpoint=directory/f'paired-{games:04}.pt'
    state=torch.load(checkpoint,map_location='cpu',weights_only=False)['runner']
    budget=read_json(cell/'budget.json')
    history=state['history'][budget['history_start']:]
    assert len(history)*8==games and all(h['method']=='ppo' and h['committed_steps']>0 for h in history)
    assert read_json(cell/'initialization.json')['weights_sha256']==m['references']['v38']['weights_sha256']
    logs={r['id']:r for r in records(directory/'jobs.jsonl')}
    counts=Counter()
    stream=[]
    arm=name.split('-')[0]
    for h in history:
        batch=read_json(directory/'schedules'/f"ppo-batch-{h['batch']:06}.json")
        assert len(batch)==8
        rows=0
        for j in batch:
            meta=j['meta']
            n=len(stream)
            row=m['design'][n]
            seat=meta['seat']
            assert j['training_scenario']['index']==n
            assert (meta['map'],j['scenario_family'],j['factions'],seat)==(
                row[arm],row[arm+'_family'],row['factions'],row['seat'])
            assert j['reward_config']['gae_lambda']==.95 and j['max_turns']==30
            assert meta['teacher_parent_sha256']==m['runtime']['astra']['teacher_parent_sha256']
            assert sha256_control_cached(j['bots'][2-seat])==meta['teacher_parent_sha256']
            if meta['map'] in m['training_boards']:
                assert board_digest(j['map_override'])==m['training_boards'][meta['map']]['board_sha256']
            r=logs[j['id']]
            terminal_points(j,r,seat)
            assert r['training_eligible'] and r['meta']==meta
            rows+=r['training_shard']['written']
            counts[meta['map']]+=1
            stream.append([n,j['seed'],j['factions'],seat,j['learning']['sides'][str(seat)]['sampling_seed']])
        assert rows==h['eligible_decisions']
    assert counts['arena2']==games*(2 if arm=='cover' else 5)//10
    stamp=checkpoint.stat().st_mtime
    timing=read_json(root/f'{name}-exit.json')
    assert stamp<=timing['deadline'] and timing['start']<=stamp
    result=role(checkpoint)
    assert result['weights_sha256']==history[-1]['policy_sha256_after']
    work={k:sum(h[k] for h in history) for k in ('eligible_decisions','committed_decisions','committed_steps','kl_stopped')}
    return result,dict(maps=counts,prefix_games=games,prefix_seconds=stamp-timing['start'],
                       total_seconds=timing['end']-timing['start'],**work),stream


@lru_cache(maxsize=32)
def sha256_control_cached(path):
    return sha256(Path(path))


def endpoints(root,m):
    assert read_json(root/'train-finished.json')['cells']==ORDER
    levels=[{int(p.stem.split('-')[1]) for p in (root/'cells'/cell/'duel').glob('paired-*.pt')}
            for cell in ORDER]
    games=max(set.intersection(*levels))
    assert 0<games<=GAMES and games%GROUP==0
    specs=dict(m['references'])
    ledgers={}
    streams={}
    for cell in ORDER:
        specs[cell],ledgers[cell],stream=audit_cell(root,cell,games,m)
        seed=int(cell.split('-')[1])
        assert streams.setdefault(seed,stream)==stream
    return specs,dict(common_games=games,target_games=GAMES,complete_target=games==GAMES,cells=ledgers)


def exports(folder,specs):
    policies={}
    for name,record in specs.items():
        assert role(record['path'])==record
        model,state=load_model(Path(record['path']),'duel')
        destination=folder/'policies'/name
        export({'duel':model},destination,name='CoveragePolicy',mode='greedy',package=False,
               version=str(record['version']))
        torch.save(dict(model=model.state_dict(),features=state['features'],architecture=state['architecture'],
                        format='duel'),destination/'model.pt')
        reloaded,_=load_model(destination/'model.pt','duel')
        assert weights_sha256(reloaded.state_dict())==record['weights_sha256']
        policies[name]=str(destination/'CoveragePolicy')
    return policies


def jobs_for(folder,m,specs,policies):
    jobs=[]
    rules=m['runtime']['rules']['path']
    data=read_json(Path(rules)/'rules.json')
    control=m['runtime']['astra']['path']
    wesnoth=read_json(PARENT/'manifest.json')['baseline']['path']
    rosters=roster('holdout')
    cells=set()
    for idx,(name,info) in enumerate(sorted(m['holdout'].items())):
        board=dict(name=name,board=info['board'],file_sha256=RESERVE_SHA)
        assert board_digest(board['board'])==info['board_sha256']
        for key,policy in policies.items():
            for j in plan_jobs(folder/'games',policy,control,wesnoth,specs[key]['weights_sha256'],
                               0,rules,'holdout',board):
                meta=j['meta']
                block=meta['block']
                seat,=meta['policy_sides']
                seed=m['score_seed']+30*idx+block
                j['id']=f'{name}-{block}-{seat}-{key}'
                j.update(seed=seed,output=str(folder/'games'/(j['id']+'.json')))
                j['game_family']=run_family(j)
                bind_scenario(j)
                meta.update(role=key,combat_seed=seed,board_sha256=info['board_sha256'],
                            checkpoint_sha256=specs[key]['checkpoint_sha256'])
                assert j['factions']==rosters[block]['factions'] and j['bots'][seat-1]==policy
                assert j['bots'][2-seat]==control and j['score_only_astra'] and j['score_only_policy']
                if key=='v38':
                    assert len(game_spec(j,data)['units'])==2
                k=(name,block,seat,key)
                assert k not in cells
                cells.add(k)
                jobs.append(j)
    assert len(jobs)==len(cells)==1440
    return sorted(jobs,key=lambda j:(j['meta']['block'],j['meta']['map'],j['meta']['rotation'],j['meta']['role']))


def score(jobs,replies):
    lookup={r['id']:r for r in replies}
    assert len(jobs)==len(replies)==len(lookup)==1440
    values=defaultdict(dict)
    tallies=defaultdict(Counter)
    for j in jobs:
        meta=j['meta']
        r=lookup[j['id']]
        assert r['meta']==meta
        key=slot(j)
        p=terminal_points(j,r,key[4])
        assert key not in values[meta['role']]
        values[meta['role']][key]=p
        t=tallies[meta['map']+'/'+meta['role']]
        t[{0:'loss',1:'draw',3:'win'}[p]]+=1
        t['caps']+=int(r['result']['reason']=='turn_limit')
        t['points']+=p
    common=values['v38'].keys()
    assert len(common)==180 and all(rows.keys()==common for rows in values.values())

    def stats(rows):
        c=[rows[f'cover-{s}'] for s in SEEDS]
        b=[rows[f'stock-{s}'] for s in SEEDS]
        v=[rows['v38']]*3
        best=[rows['083']]*3
        return {name:paired(left,right) for name,left,right in [
            ('cover-stock',c,b),('cover-083',c,best),('cover-v38',c,v),('stock-v38',b,v),('083-v38',best,v)]}
    pooled=stats(values)
    maps={name:stats({r:{k:v for k,v in vals.items() if k[0]==name} for r,vals in values.items()})
          for name in sorted({k[0] for k in common})}
    return dict(games=len(replies),pooled=pooled,by_map=maps,counts=tallies,
                role_scores={r:sum(v.values())/(3*len(v)) for r,v in values.items()})


def run(root,folder):
    assert sha256(root/'launch.json')==DIGEST
    m=read_json(root/'launch.json')
    assert worker()==m['runtime']
    specs,ledger=endpoints(root,m)
    folder.mkdir()
    write_new(folder/'endpoints.json',specs)
    write_new(folder/'training.json',ledger)
    policies=exports(folder,specs)
    jobs=jobs_for(folder,m,specs,policies)
    write_new(folder/'schedule.json',jobs)
    start=time.time()
    deadline=start+PANEL_SECONDS
    active=[dict(j,deadline=deadline) for j in jobs]
    write_new(folder/'active.json',active)
    replies=collect(active,8,folder/'results.jsonl')
    end=time.time()
    assert end<=deadline
    result=score(jobs,replies)
    write_new(folder/'score.json',result)
    write_new(folder/'timing.json',dict(start=start,end=end,collection_seconds=end-start,
              results_sha256=sha256(folder/'results.jsonl'),score_sha256=sha256(folder/'score.json')))


if __name__=='__main__':
    torch.set_num_threads(1)
    run(*(Path(x).resolve() for x in sys.argv[1:]))
