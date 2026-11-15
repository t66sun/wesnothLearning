"""Build one fixed roster and independently score the official paired results."""
from collections import Counter, defaultdict
from pathlib import Path
import math
import random
from statistics import mean

import torch

from learning.bc_anchor import weights_sha256
from learning.common import read_json
from learning.export import export, load_model
from learning.lite_policy import game_spec
from learning.manifest import tree_hashes
from learning.maps import bind_scenario, run_family
from learning.tasks import TASK_ID
from verification.duel_ppo_comparison_20261106.panels import panel_scores, role
from verification.ppo_batch_comparison_20261107.panels import plan_jobs, roster

from lineage import INPUTS, require


MAPS = tuple(INPUTS['boards'])
ROLES = tuple(INPUTS['roles'])
PPO = ROLES[1:]
BLOCKS = 30
NUM_JOBS = len(ROLES) * len(MAPS) * BLOCKS * 2


def export_policies(output):
    records = {}
    for name, expected in INPUTS['roles'].items():
        model, state = load_model(Path(expected['path']), 'duel')
        require(role(expected['path']) == expected, f'endpoint changed before export: {name}')
        dest = output / 'policies' / name
        export({'duel': model}, dest, name='DuelComparison', mode='greedy', package=False,
               version=str(expected['version']))
        torch.save(dict(model=model.state_dict(), features=state['features'],
                        architecture=state['architecture'], format='duel'), dest / 'model.pt')
        reloaded, _ = load_model(dest / 'model.pt', 'duel')
        require(weights_sha256(reloaded.state_dict()) == expected['weights_sha256'],
                f'exported weights differ: {name}')
        records[name] = dict(folder=str(dest), addon=str(dest/'DuelComparison'), files=tree_hashes(dest))
    return records


def build_schedule(output, worker_info, boards, policies, wesnoth):
    control, rules = worker_info['astra']['path'], worker_info['rules']['path']
    jobs = []
    for map_index, (board_name, record) in enumerate(boards.items()):
        board = read_json(Path(record['path'])) | dict(name=board_name, file_sha256=record['file_sha256'])
        for role_name, policy in policies.items():
            key = INPUTS['roles'][role_name]['weights_sha256']
            planned = plan_jobs(output / 'games' / board_name, policy['addon'], control,
                                wesnoth, key, 0, rules, 'holdout', board)
            for job in planned:
                meta = job['meta']
                seed = INPUTS['seed'] + BLOCKS*map_index + meta['block']
                job['id'] = board_name + '-' + job['id']
                job['output'] = str(Path(job['output']).with_name(job['id']+'.json'))
                job['seed'] = seed
                job['game_family'] = run_family(job)
                bind_scenario(job)
                meta.update(role=role_name, combat_seed=seed,
                            checkpoint_sha256=INPUTS['roles'][role_name]['checkpoint_sha256'],
                            opponent_sha256=worker_info['astra']['teacher_parent_sha256'])
            jobs.extend(planned)
    jobs.sort(key=lambda j: (j['meta']['block'], j['meta']['map'], j['meta']['rotation'],
                             j['meta']['role']))
    verify_schedule(jobs)
    # Exercise the actual initial state construction without opening a game.
    rules_object = read_json(Path(rules) / 'rules.json')
    for job in jobs:
        if job['meta']['role'] == 'bc':
            spec = game_spec(job, rules_object)
            require(len(spec['units']) == 2 and all(unit['leader'] for unit in spec['units']),
                    f'incorrect starting leaders: {job["id"]}')
    return jobs


def verify_schedule(jobs):
    require(len(jobs) == len({j['id'] for j in jobs}) == NUM_JOBS,
            'schedule job identities are incomplete or duplicated')
    factions = [entry['factions'] for entry in roster('holdout')]
    require(len(factions) == BLOCKS, 'unexpected ordered faction roster')
    groups, seen = defaultdict(set), set()
    for job in jobs:
        meta = job['meta']
        board, block, rotation, name = (meta[k] for k in ('map', 'block', 'rotation', 'role'))
        role_info = INPUTS['roles'][name]
        seat, = meta['policy_sides']
        cell = (board, block, rotation, name)
        require(cell not in seen and 0 <= block < BLOCKS and rotation in (0, 1)
                and seat == rotation + 1 and job['factions'] == factions[block]
                and job['seed'] == meta['combat_seed'] == INPUTS['seed'] + BLOCKS*MAPS.index(board) + block
                and meta['checkpoint_sha256'] == role_info['checkpoint_sha256']
                and meta['weights_sha256'] == role_info['weights_sha256']
                and job['task_id'] == TASK_ID and job['max_turns'] == 30 and job['engine'] == 'lite'
                and job['score_only_astra'] and job['score_only_policy']
                and 'shard' not in job and 'learning' not in job
                and job['bots'][seat-1] == meta['policy'] and job['bots'][2-seat] == meta['control'],
                f'unpaired schedule entry: {job["id"]}')
        seen.add(cell)
        groups[board, block].add(job['scenario_family'])
    require(len(groups) == len(MAPS)*BLOCKS and all(len(scenes) == 1 for scenes in groups.values())
            and len(set().union(*groups.values())) == len(groups), 'scenario blocks do not pair')


def verdict(raw, bounds, maximum):
    gain = INPUTS['minimum_gain_pp']
    if 100*raw >= gain*maximum and bounds[0] > 0:
        return 'passed'
    if 100*bounds[1] < gain*maximum:
        return 'five_point_gain_excluded'
    return 'inconclusive'


def crossed(deltas, groups):
    maximum = 6*len(PPO)*sum(map(len, groups.values()))
    point = sum(deltas[role][scene] for role in PPO for group in groups.values() for scene in group)
    rng = random.Random(INPUTS['bootstrap_seed'])
    size = INPUTS['bootstrap_samples']
    draws = []
    for _ in range(size):
        roles = rng.choices(PPO, k=len(PPO))
        scenes = [scene for group in groups.values() for scene in rng.choices(group, k=len(group))]
        draws.append(sum(deltas[role][scene] for role in roles for scene in scenes))
    draws.sort()
    bounds = draws[int(size*.025)], draws[min(size-1, int(size*.975))]
    return dict(point=point/maximum, interval95=[bound/maximum for bound in bounds],
                raw_difference=point, raw_interval95=list(bounds), raw_max=maximum,
                verdict=verdict(point, bounds, maximum))


def recount(jobs, replies):
    verify_schedule(jobs)
    lookup = {row['id']: row for row in replies}
    require(len(lookup) == len(replies) == NUM_JOBS and lookup.keys() == {job['id'] for job in jobs},
            'missing, duplicate or unexpected reply')
    official = panel_scores(dict(jobs=jobs, blocks=BLOCKS*len(MAPS),
                                 aliases={name: info['weights_sha256'] for name, info in INPUTS['roles'].items()}),
                            replies)
    require(official['complete'], 'official panel scoring found missing or faulted games')
    points, by_map, tallies = defaultdict(Counter), defaultdict(set), defaultdict(Counter)
    for job in jobs:
        row = lookup[job['id']]
        result, meta = row['result'], job['meta']
        name, board = meta['role'], meta['map']
        scene, seat = job['scenario_family'], meta['policy_sides'][0]
        winner = result['winner']
        capped = result['reason'] == 'turn_limit'
        require(row['status'] == 'complete' and row['engine'] == 'lite' and row['meta'] == meta
                and result['task_id'] == TASK_ID and result['task_terminal'] and not result['faults']
                and result['bots'] == job['bots'] and result['factions'] == job['factions']
                and not result.get('teams') and winner in (0, 1, 2)
                and (not capped or (winner == 0 and result['turns'] == 31)),
                f'invalid or mispaired reply: {job["id"]}')
        points[name][scene] += 3 if winner == seat else 1 if winner == 0 else 0
        by_map[board].add(scene)
        tallies[board, name]['win' if winner == seat else 'draw' if winner == 0 else 'loss'] += 1
        tallies[board, name]['round_cap'] += int(capped)
    groups = {board: sorted(by_map[board]) for board in sorted(by_map)}
    deltas = {name: {scene: score - points['bc'][scene] for scene, score in points[name].items()}
              for name in PPO}
    for name in ROLES:
        require(all(math.isclose(official['roles'][name][scene], raw/6, abs_tol=1e-12)
                    for scene, raw in points[name].items()), f'official and integer scores disagree: {name}')
    result = crossed(deltas, groups)
    per_map = {}
    for board, scenes in groups.items():
        table = {name: dict(tallies[board, name], score=sum(points[name][s] for s in scenes)/(6*BLOCKS))
                 for name in ROLES}
        per_map[board] = dict(roles=table, difference=mean(table[name]['score'] for name in PPO)-table['bc']['score'])
    result.update(games=NUM_JOBS, paired_slots=NUM_JOBS//len(ROLES), faults=0,
                  per_map=per_map, per_role={name: mean(row['roles'][name]['score'] for row in per_map.values())
                                            for name in ROLES},
                  per_seed={name.rsplit('-', 1)[1]: sum(scores.values())/(6*BLOCKS*len(MAPS))
                            for name, scores in deltas.items()})
    return result
