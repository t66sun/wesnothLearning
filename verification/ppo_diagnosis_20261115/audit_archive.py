"""Read-only #353 archive inventory, score contrasts and realized PPO work."""
from collections import Counter, defaultdict
from itertools import combinations
import json
from pathlib import Path
import random
from statistics import mean
import sys

import torch

from learning.bc_anchor import weights_sha256
from learning.common import read_json, sha256
from learning.tasks import TASK_ID
from verification.duel_ppo_comparison_20261106.audit import board_digest
from verification.duel_ppo_comparison_20261106.panels import role

BASE = Path('/home/tongshu/acceptance')
RUNS = {
    '227': BASE/'duel_comparison_20261106_43325b3/source/runs/duel_ppo_comparison_20261106',
    '272': BASE/'ppo269_shared_20261107_gzzXd6/experiment',
    '306': BASE/'ppo306_20261108_Miwoyq/source/runs/ppo306',
    '312': BASE/'ppo312_20261110_lNyy9W',
    '322': BASE/'ppo322-formal-20261114-wGKDQ4/source/runs/ppo322',
    '349': BASE/'ppo-v38-20261115-8dIsba/formal',
}
WALL = ('lambda-0.95-202611081', 'lambda-0.95-202611082', 'lambda-0.95-202611083')
A = ('a-202611071', 'a-202611072', 'a-202611073')
ALIASES = ['base/bc', *(f'{name}/{stage}' for name in A for stage in (10000, 30000, 'wall', 'selected'))]
CONTRASTS = (('10000','bc'), ('30000','bc'), ('wall','bc'), ('selected','bc'),
             ('30000','10000'), ('wall','10000'), ('wall','30000'), ('wall','selected'))


def records(path):
    with path.open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def terminal_points(job, reply, seat):
    result = reply['result']
    assert reply['id'] == job['id'] and reply['status'] == 'complete'
    assert job['task_id'] == result['task_id'] == TASK_ID and result['task_terminal']
    assert not result['faults'] and result['winner'] in (0, 1, 2)
    assert result['factions'] == job['factions'] and result['bots'] == job['bots']
    return 3 if result['winner'] == seat else 1 if result['winner'] == 0 else 0


def slot(job):
    meta = job['meta']
    return (meta['map'], board_digest(job['map_override']), job['seed'], tuple(job['factions']),
            meta['policy_sides'][0], sha256_control(meta['control']), job['task_id'])


def sha256_control(control, cache={}):
    if control not in cache:
        cache[control] = sha256(Path(control))
    return cache[control]


def panel(path, aliases=None):
    launch_path = path/('schedule.json' if aliases else 'plan.json')
    plan = read_json(launch_path)
    jobs, lookup = (plan, aliases) if aliases else (plan['jobs'], plan['aliases'])
    result = {r['id']:r for r in records(path/'results.jsonl')}
    assert set(result) == {j['id'] for j in jobs} and len(result)==len(jobs)
    scores = defaultdict(dict)
    for job in jobs:
        row = result[job['id']]
        meta = job['meta']
        weight = meta['weights_sha256']
        key = slot(job)
        assert key not in scores[weight]
        scores[weight][key] = terminal_points(job, row, key[4])
    aliases = {name:scores[w] for name,w in lookup.items()}
    info = dict(jobs=len(jobs), plan_sha256=sha256(launch_path), replies_sha256=sha256(path/'results.jsonl'),
                weights=dict(lookup), board_slots=Counter(k[0] for k in set().union(*scores.values())),
                physical_boards={k[0]:k[1] for k in set().union(*scores.values())})
    return aliases, info


def paired(left, right):
    if not all(left) or not all(right):
        return dict(status='missing_role')
    slots = set.intersection(*(set(x) for x in left+right))
    blocks = defaultdict(dict)
    for key in sorted(slots):
        blocks[key[:4]+key[5:]][key[4]] = key
    groups = defaultdict(list)
    for k, pair in sorted(blocks.items()):
        if set(pair)=={1,2}:
            groups[k[0]].append([sum(left[i][s]-right[i][s] for s in pair.values())/6
                                 for i in range(len(left))])
    if not groups:
        return dict(status='no_matching_pair', exact_slots=len(slots))
    rng = random.Random(2026111753)
    draws = []
    for _ in range(10000):
        ids = rng.choices(range(len(left)), k=len(left))
        draws.append(mean(mean(data[i] for data in rng.choices(rows,k=len(rows)) for i in ids)
                          for rows in groups.values()))
    draws.sort()
    per_seed = [mean(mean(data[i] for data in rows) for rows in groups.values()) for i in range(len(left))]
    return dict(status='paired', exact_slots=len(slots), paired_blocks={k:len(v) for k,v in groups.items()},
                point=mean(per_seed), per_seed=per_seed, interval95=[draws[250],draws[9750]])


def frame(aliases, arm, stage):
    return [aliases.get('base/bc' if stage=='bc' else f'{name}/{stage}') for name in arm]


def weights(path):
    state = torch.load(path, map_location='cpu', weights_only=False)
    runner = state.get('runner', {})
    return dict(file_sha256=sha256(path), weights_sha256=weights_sha256(state['model']),
                version=runner.get('version'), optimizer=bool(state.get('optimizer', {}).get('state')))


def cell(duel):
    state = read_json(duel/'state.json')
    all_history = [row for row in state['history'] if row['method']=='ppo']
    log = {row['id']:row for row in records(duel/'jobs.jsonl') if row.get('meta',{}).get('phase')=='ppo'}
    shards, exports, seen = set(), set(), set()
    maps, opponent_digests, rosters, seats = Counter(), Counter(), defaultdict(set), Counter()
    by_occurrence = defaultdict(set)
    physical = {}
    versions = {}
    history = []
    for entry in all_history:
        jobs = read_json(duel/'schedules'/f"ppo-batch-{entry['batch']:06d}.json")
        assert len(jobs)==8
        visited = [log[j['id']] for j in jobs]
        assert len({j['meta']['version'] for j in jobs}) == 1
        totals = sum(row['training_shard']['written'] for row in visited)
        assert totals == entry['eligible_decisions'] == entry['planned_targets']
        versions[jobs[0]['meta']['version']] = entry['policy_sha256_before']
        history.append({k:entry[k] for k in ('batch','eligible_decisions','committed_decisions','inspected_decisions',
                        'committed_steps','planned_steps','stopped_by_kl_steps','kl_stopped','sequence_windows',
                        'policy_sha256_before','policy_sha256_after','approx_kl')})
        for job, row in zip(jobs, visited):
            meta=job['meta']
            seat, name = meta['seat'], meta['map']
            terminal_points(job, row, seat)
            assert row['training_eligible'] and job['id'] not in seen
            seen.add(job['id'])
            shards.add(Path(job['shard']))
            exports.add(Path(job['bots'][seat-1]).parent/'model.pt')
            maps[name]+=1
            seats[seat]+=1
            physical[name]=board_digest(job['map_override'])
            rosters[name].add(tuple(job['factions']))
            opponent_digests[sha256_control(job['bots'][2-seat])]+=1
            by_occurrence[name].add((tuple(job['factions']),seat))
    assert set(log)==seen
    checkpoints = {p.name:weights(p) for p in sorted(duel.glob('*.pt'))}
    trend = {}
    for path in sorted((duel/'schedules').glob('validation-*.json')):
        jobs=read_json(path)
        trend[path.stem] = dict(plan_sha256=sha256(path), slots=sorted(slot(j) for j in jobs))
    overlap = max((len({tuple(s) for s in a['slots']} & {tuple(s) for s in b['slots']})
                   for a,b in combinations(trend.values(),2)), default=0)
    validation_versions = sorted(int(k[len('validation-'):]) for k in trend if k[len('validation-'):].isdigit())
    return dict(checkpoints=checkpoints, settlement_sha256=sha256(duel/'state.json'), version=state['version'],
                training_games=sum(maps.values()), physical_boards=physical, from_one_opponent=opponent_digests,
                map_counts=maps, rosters={k:len(v) for k,v in rosters.items()}, seats=seats,
                map_roster_seats={k:len(v) for k,v in by_occurrence.items()},
                policy_shards=dict(present=sum(x.is_file() for x in shards), referenced=len(shards)),
                behavior_tensor_files=dict(present=sum(x.is_file() for x in exports), referenced=len(exports)),
                exact_behavior_versions=versions, batches=history,
                validation=dict(plans=len(trend), versions=validation_versions,
                    max_overlap_between_plans=overlap, slots_by_plan=trend))


def main():
    p349=RUNS['349']
    launch=read_json(p349/'launch.json')
    assert sha256(p349/'launch.json')=='3ff17a173aa6af898aead3564d8d466e5ffa7dcdec9481125c01e47130c7da50'
    assert sha256(RUNS['306']/'launch.json')=='5ac6d19cab756ce8dade4c739c5f2127e86bb9ea34cec033934625fbd03bf02c'
    for identity in launch['roles'].values():
        assert role(identity['path']) == identity
    ledger = {name:cell(RUNS['306']/'cells'/name/'duel') for name in WALL}
    corroboration = {path.name:cell(path/'duel') for path in sorted((RUNS['322']/'cells').glob('astra-*'))}
    scored = {}
    for label,path in (
        ('227/validation',RUNS['227']/'evaluation/validation'),
        ('227/holdout',RUNS['227']/'evaluation/holdout'),
        ('272/validation',RUNS['272']/'validation-base-result'),
        ('272/holdout',RUNS['272']/'holdout-base-result'),
        ('306/validation',RUNS['306']/'validation/hamlets'),
        ('306/road',RUNS['306']/'holdout/road_to_weldyn'),
        ('306/summer',RUNS['306']/'holdout/summer_of_storms'),
        ('349/holdout',p349)):
        aliases={name:v['weights_sha256'] for name,v in launch['roles'].items()} if path == p349 else None
        scored[label]=panel(path,aliases)
    first=scored['272/validation'][0]
    milestones={f'{left}-{right}':paired(frame(first,A,left),frame(first,A,right)) for left,right in CONTRASTS}
    settled={}
    for name,(rows,info) in scored.items():
        if not name.startswith(('306/','349/')): continue
        settled[name]=paired([rows[x] for x in WALL],[rows['bc']]*3)
    info={name:details for name,(_,details) in scored.items()}
    boards={name:details['physical_boards'] for name,details in info.items()}
    overlap={f'{a} vs {b}':sorted(set(boards[a].values())&set(boards[b].values()))
             for a,b in combinations(boards,2) if a.split('/')[0]!=b.split('/')[0]}
    print(json.dumps(dict(cohort=launch['roles'], inventory_306=ledger, corroboration_322=corroboration,
                          panel_inventory=info, physical_overlap=overlap, milestones_272=milestones,
                          settled_306=settled, games_started=0, optimizer_updates=0), indent=2))


if __name__ == '__main__':
    torch.set_num_threads(1)
    main()
