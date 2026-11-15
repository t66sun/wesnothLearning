"""Freeze the proposed 96-game shared #352 data capture without playing."""
from collections import Counter
import gzip
import json
from pathlib import Path
import random
import sys
import tarfile
import time

import torch

from audit_archive import RUNS, terminal_points
from learning.bc_anchor import weights_sha256
from learning.common import read_json, sha256
from learning.export import export, load_model
from learning.lite_policy import game_spec
from learning.manifest import tree_hashes
from learning.maps import bind_scenario, frozen_map, run_family
from learning.rowpack import row_meta
from learning.sample import collect
from learning.tasks import TASK_ID
from verification.duel_ppo_comparison_20261106.audit import board_digest, write_new
from verification.ppo_batch_comparison_20261107.panels import plan_jobs

FROZEN_349 = RUNS['349']
ADAPTER_349 = FROZEN_349.parent/'adapter/verification/ppo_vs_bc_20261115'
sys.path.append(str(ADAPTER_349))
from lineage import worker

BLOCKS = (0, 8, 16, 24)
LIMITS = dict(preflight=300, collection=1200, audit=300, total=1800)
GUESS = (
    ('reserve_hills', 2026111751, 29, 21, ('Hh','Hh','Gs','Gg^Fet')),
    ('reserve_woods', 2026111752, 33, 23, ('Gg^Fet','Gs^Fp','Gs^Fp','Hh')),
    ('reserve_fords', 2026111753, 37, 25, ('Wwf','Wwf','Gs','Hh')),
)


def reserve(rules, excluded):
    """Predeclared symmetric Lite layouts chosen from topology and terrain only."""
    terrains=rules['terrains']
    boards={}
    for name,seed,w,h,palette in GUESS:
        rng=random.Random(seed)
        grid=[['Gg']*w for _ in range(h)]
        mid=w//2
        for y,row in enumerate(grid):
            for x in range(mid+1):
                varied = abs(x-mid) <= w//3 and rng.random() < .26
                code=rng.choice(palette) if varied else 'Gg'
                row[x]=row[w-x-1]=code
        villages=[(x,y) for y in range(2,h-2) for x in range(2,mid)
                  if not (x<=5 and abs(y-h//2)<=2)]
        for x,y in rng.sample(villages,10):
            grid[y][x]=grid[y][w-x-1]='Gg^Vh'
        y=h//2
        for x in (3,w-4):
            grid[y][x]='Kh'
            for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                grid[y+dy][x+dx]='Ch'
        board=dict(width=w,height=h,terrain=grid,starts=[[4,y+1],[w-3,y+1]])
        digest=board_digest(board)
        assert digest not in excluded and digest not in {x['board_sha256'] for x in boards.values()}
        cells=[tile for row in grid for tile in row]
        assert all(tile in terrains for tile in cells)
        assert all(terrains[grid[yy-1][xx-1]]['keep'] for xx,yy in board['starts'])
        assert sum(terrains[t]['village'] for t in cells)==20
        boards[name]=dict(seed=seed, board=board, board_sha256=digest, villages=20)
    return boards


def archive_identity(archive, commit):
    with tarfile.open(archive,'r:') as tar:
        assert tar.pax_headers['comment']==commit
        names=('capture.py','audit_archive.py')
        for name in names:
            path=Path(__file__).with_name(name)
            expected=tar.extractfile(f'verification/ppo_diagnosis_20261115/{name}').read()
            assert path.read_bytes()==expected
    return dict(path=str(archive),commit=commit,sha256=sha256(archive))


def export_sample(output, cohort):
    exports={}
    for name,role in cohort.items():
        model,state=load_model(Path(role['path']),'duel')
        folder=output/'policies'/name
        export(model,folder,name='DiagnosticPolicy',mode='sample',package=False,version=f"v{role['version']}")
        torch.save(dict(model=model.state_dict(),features=state['features'],
                        architecture=state['architecture'],format='duel'),folder/'model.pt')
        reload,_=load_model(folder/'model.pt','duel')
        assert weights_sha256(reload.state_dict())==role['weights_sha256']
        addon=folder/'DiagnosticPolicy'
        assert '["mode"]="sample"' in (addon/'lua/config.lua').read_text() or '["mode"] = "sample"' in (addon/'lua/config.lua').read_text()
        exports[name]=dict(folder=str(folder),addon=str(addon),files=tree_hashes(folder))
    return exports


def make_schedule(output, runtime, boards, cohort, exports):
    astra, rules = runtime['astra']['path'], runtime['rules']['path']
    historical=read_json(FROZEN_349/'schedule.json')
    wesnoth=historical[0]['wesnoth']
    roster=set()
    jobs=[]
    for map_index,(name,record) in enumerate(boards.items()):
        for role_id,role in cohort.items():
            long=plan_jobs(output/'games'/name, exports[role_id]['addon'], astra, wesnoth,
                           role['weights_sha256'], 0, rules, 'holdout', record)
            for job in long:
                meta=job['meta']
                if meta['block'] not in BLOCKS:
                    continue
                seat,=meta['policy_sides']
                seed=2026111740+4*map_index+BLOCKS.index(meta['block'])
                job['id']=f'{name}-{role_id}-{meta["block"]}-{seat}'
                job['output']=str(output/'games'/f"{job['id']}.json")
                job['seed']=seed
                job['shard']=str(output/'trajectory'/f"{job['id']}.jsonl.gz")
                job['learning']=dict(sides={str(seat):dict(teacher=False,version=f"v{role['version']}")})
                job['score_only_policy']=False
                job['score_only_astra']=False
                meta.update(phase='ppo',corpus='diagnostic_only',board_sha256=record['board_sha256'],
                            role=role_id,mode='sample',combat_seed=seed,policy_rng_seed=seed+seat*100003,
                            checkpoint_sha256=role['checkpoint_sha256'])
                job['game_family']=run_family(job)
                bind_scenario(job)
                roster.add(tuple(job['factions']))
                jobs.append(job)
    assert len(roster)==4
    return sorted(jobs,key=lambda j:(j['meta']['block'],j['meta']['map'],j['meta']['rotation'],j['meta']['role']))


def check_schedule(jobs, manifest):
    assert len(jobs)==len({j['id'] for j in jobs})==96
    counts=Counter()
    ids={}
    for j in jobs:
        m=j['meta']
        seat,=m['policy_sides']
        cohort=manifest['roles'][m['role']]
        assert seat in (1,2) and set(j['learning']['sides'])=={str(seat)} and j['shard']
        assert j['engine']=='lite' and j['task_id']==TASK_ID and j['max_turns']==30 and j['rules_dir']==manifest['runtime']['rules']['path']
        assert not j['score_only_policy'] and not j['score_only_astra'] and m['mode']=='sample'
        assert cohort['checkpoint_sha256']==m['checkpoint_sha256'] and cohort['weights_sha256']==m['weights_sha256']
        assert j['bots'][seat-1]==manifest['policies'][m['role']]['addon'] and j['bots'][2-seat]==manifest['runtime']['astra']['path']
        assert m['board_sha256']==manifest['boards'][m['map']]['board_sha256']==board_digest(j['map_override'])
        assert j['seed']==m['combat_seed'] and m['policy_rng_seed']==j['seed']+seat*100003
        assert j['deadline']==0 and 'dagger_teacher' not in j['learning']
        key = (m['map'],m['block'],seat)
        ident = (j['scenario_family'],j['seed'],tuple(j['factions']))
        assert ids.setdefault(key,ident)==ident
        counts[key,m['role']]+=1
    assert len(ids)==24 and len(counts)==96 and set(counts.values())=={1}
    assert all(ids[name,block,1]==ids[name,block,2] for name in manifest['boards'] for block in BLOCKS)


def prepare(output, archive, commit, evidence):
    code=archive_identity(archive,commit)
    runtime=worker()
    assert runtime==read_json(FROZEN_349/'launch.json')['runtime']
    cohort=read_json(evidence)['cohort']
    assert cohort==read_json(FROZEN_349/'launch.json')['roles']
    for role in cohort.values():
        assert sha256(Path(role['path']))==role['checkpoint_sha256']
    roots=read_json(evidence)
    prior=read_json(FROZEN_349/'lineage.json')
    excluded=set(prior['exposure']['excluded_boards'])
    excluded.update(row['board_sha256'] for row in read_json(FROZEN_349/'launch.json')['boards'].values())
    for row in roots['panel_inventory'].values():
        excluded.update(row['physical_boards'].values())
    for row in roots['corroboration_322'].values():
        excluded.update(row['physical_boards'].values())
    r=read_json(Path(runtime['rules']['path'])/'rules.json')
    reserved=reserve(r,excluded)
    output.mkdir(exist_ok=False)
    write_new(output/'confirmation-reserve.json',reserved)
    boards={}
    for name in ('the_freelands','weldyn_channel'):
        board,digest=frozen_map(name)
        boards[name]=dict(name=name, board=board, file_sha256=digest, board_sha256=board_digest(board))
    lake=Path(read_json(FROZEN_349/'launch.json')['boards']['fallenstar_lake']['path'])
    b=read_json(lake)['board']
    boards['fallenstar_lake']=dict(name='fallenstar_lake',board=b,file_sha256=sha256(lake), board_sha256=board_digest(b))
    assert {v['board_sha256'] for v in reserved.values()}.isdisjoint(v['board_sha256'] for v in boards.values())
    policies=export_sample(output,cohort)
    schedule=make_schedule(output,runtime,boards,cohort,policies)
    prior_combat={j['seed'] for j in read_json(FROZEN_349/'schedule.json')}
    for d in (RUNS['306']/'cells').glob('*/duel/schedules/ppo-batch-*.json'):
        prior_combat.update(j['seed'] for j in read_json(d))
    assert {j['seed'] for j in schedule}.isdisjoint(prior_combat)
    for job in schedule:
        spec=game_spec(job,r)
        assert len(spec['units'])==2 and all(unit['leader'] for unit in spec['units'])
        for board in reserved.values():
            candidate=game_spec(dict(job,map_override=board['board']),r)
            assert len(candidate['units'])==2 and all(unit['leader'] for unit in candidate['units'])
    write_new(output/'capture-schedule.json', schedule)
    manifest=dict(issue=355,shared_with=[354,356,357,358,359,360],runtime=runtime,adapter=code,
                  archive_inventory_sha256=sha256(evidence),boards=boards,roles=cohort,policies=policies,
                  task=TASK_ID,games=96,workers=8,seconds=LIMITS,optimizer_updates=0,
                  capture_schedule_sha256=sha256(output/'capture-schedule.json'),
                  confirmation_reserve_sha256=sha256(output/'confirmation-reserve.json'))
    check_schedule(schedule,manifest)
    write_new(output/'capture-launch.json',manifest)
    print(json.dumps(dict(games=96,game_spec_checks=96,confirmation_reserve_boards=3,games_started=0,
                          launch_sha256=sha256(output/'capture-launch.json'),
                          schedule_sha256=manifest['capture_schedule_sha256'],
                          confirmation_reserve_sha256=manifest['confirmation_reserve_sha256']),indent=2))


def preflight(output, expected):
    assert sha256(output/'capture-launch.json')==expected
    m=read_json(output/'capture-launch.json')
    a=m['adapter']
    assert archive_identity(Path(a['path']),a['commit'])==a and worker()==m['runtime']
    assert sha256(output/'capture-schedule.json')==m['capture_schedule_sha256']
    assert sha256(output/'confirmation-reserve.json')==m['confirmation_reserve_sha256']
    for name,role in m['roles'].items():
        assert sha256(Path(role['path']))==role['checkpoint_sha256']
        p=m['policies'][name]
        assert tree_hashes(Path(p['folder']))==p['files']
    schedule=read_json(output/'capture-schedule.json')
    check_schedule(schedule,m)
    return m,schedule


def recount(output, jobs, replies):
    lookup={reply['id']:reply for reply in replies}
    assert len(jobs)==len(lookup)==len(replies)==96
    games=[]
    for job in jobs:
        meta=job['meta']
        reply=lookup[job['id']]
        seat=meta['policy_sides'][0]
        points=terminal_points(job,reply,seat)
        assert reply['meta']==meta and reply['training_eligible'] and reply['engine']=='lite'
        p=Path(job['shard'])
        with gzip.open(p,'rt',encoding='utf-8') as stream:
            n=0
            for line in stream:
                record=row_meta(line)
                assert record['game_id']==job['id'] and record['side']==seat and record['source']=='policy'
                assert record['task_id']==TASK_ID and record['value_valid'] and not record['truncated']
                assert record['terminal_reward']==2*points/3-1 and record['version']==job['learning']['sides'][str(seat)]['version']
                n+=int(record['choice']>=0)
        assert n>0 and n==reply['training_shard']['written']
        games.append(dict(id=job['id'],role=meta['role'],records=n,score=points,trajectory_sha256=sha256(p)))
    write_new(output/'capture-ledger.json',dict(games=games,total=len(games),optimizer_updates=0))
    with tarfile.open(output/'capture-metadata.tar.gz','x:gz',compresslevel=1) as bundle:
        for name in ('capture-launch.json','capture-schedule.json','confirmation-reserve.json',
                     'runtime-schedule.json','results.jsonl','results.throughput.jsonl','capture-ledger.json'):
            bundle.add(output/name,arcname=name)


def run(output, expected):
    started=time.time()
    write_new(output/'capture-start.json',dict(started=started,launch_sha256=expected))
    end='incomplete'
    try:
        m,jobs=preflight(output,expected)
        admitted=time.time()
        assert admitted-started<=LIMITS['preflight']
        deadline=admitted+LIMITS['collection']
        runtime=[dict(j,deadline=deadline) for j in jobs]
        write_new(output/'runtime-schedule.json',runtime)
        replies=collect(runtime,m['workers'],output/'results.jsonl')
        collected=time.time()
        assert collected<=deadline
        recount(output,runtime,replies)
        assert time.time()<=min(collected+LIMITS['audit'],started+LIMITS['total'])
        end='complete'
    finally:
        write_new(output/'capture-exit.json',dict(status=end,wall_seconds=time.time()-started))


if __name__=='__main__':
    torch.set_num_threads(1)
    action, folder, *args=sys.argv[1:]
    output=Path(folder).resolve()
    if action=='prepare':
        prepare(output,Path(args[0]).resolve(),args[1],Path(args[2]).resolve())
    elif action=='preflight':
        preflight(output,args[0])
        assert not (output/'capture-start.json').exists() and not (output/'results.jsonl').exists()
        print('Frozen capture validated. Zero games and zero optimizer updates.')
    elif action=='run':
        run(output,args[0])
    else:
        raise ValueError('expected prepare, preflight or run')
