"""Recount #336 independently using integer game points and frozen schedule slots."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import random
from zoneinfo import ZoneInfo

import torch

from learning.bc_anchor import weights_sha256

POINTS = {'wins': 3, 'draws': 1, 'losses': 0}
KEYS = ('b_minus_a', 'a_minus_bc', 'b_minus_bc')
SHANGHAI = ZoneInfo('Asia/Shanghai')


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def local(stamp):
    return datetime.fromtimestamp(stamp, SHANGHAI).isoformat()


def stage_times(run, inputs, start, end):
    names = [f'{role}-{seed}' for role, seed in inputs['order']] + ['panel', 'audit']
    limits = inputs['limits']
    finishes, stages = start['started'], {}
    for label in names:
        row = read(run/f'{label}-exit.json')
        require(row['exit_code'] == 0 and not row['timed_out'], f'process failed: {label}')
        limit = limits['games'] if label == 'panel' else limits['audit'] if label == 'audit' else limits['cell']
        require(finishes <= row['started'] <= row['finished'] <= row['deadline']
                and row['deadline'] <= start['deadline'] and row['wall_seconds'] <= limit,
                f'out-of-budget stage: {label}')
        finishes = row['finished']
        stages[label] = row['wall_seconds']
    preparation = read(run/f'{names[0]}-exit.json')['started'] - start['started']
    audit_and_archive = end['finished'] - read(run/'audit-exit.json')['started']
    elapsed = end['finished'] - start['started']
    require(preparation <= limits['preflight'] and audit_and_archive <= limits['audit']
            and elapsed <= limits['total'] and end['deadline'] == start['deadline']
            and start['deadline'] - start['started'] == limits['total'], 'total or phase deadline missed')
    return dict(started=local(start['started']), finished=local(end['finished']), deadline=local(start['deadline']),
                preflight_seconds=preparation, active_seconds=elapsed, audit_and_archive_seconds=audit_and_archive,
                training_seconds=sum(stages[n] for n in names[:-2]), stages=stages)


def endpoints_audit(run, inputs, roles):
    endpoints = read(run/'endpoints.json')
    require(set(endpoints) == set(roles), 'unexpected checkpoint roles')
    root = read(run/'launch.json')
    require(digest(Path(root['archive'])) == root['archive_sha256'], 'source archive changed')
    identities = {}
    original_value = None
    for role in roles:
        record = endpoints[role]
        path = Path(record['path'])
        require(digest(path) == record['sha256'], f'checkpoint bytes differ: {role}')
        state = torch.load(path, map_location='cpu', weights_only=False)
        params = state['model']
        got = weights_sha256(params)
        require(got == record['weights_sha256'], f'checkpoint weights differ: {role}')
        value = weights_sha256({k.removeprefix('value.'): tensor for k, tensor in params.items()
                                if k.startswith('value.')})
        if role == 'bc':
            require(got == inputs['checkpoint']['weights_sha256']
                    and record['sha256'] == inputs['checkpoint']['checkpoint_sha256'], 'unexpected initializer')
            original_value = value
            steps = visits = 0
        else:
            arm, seed = role.split('-', 1)
            steps, visits = state['optimizer_steps'], state['target_visits']
            adam = state['optimizer']
            ticks = {int(slot['step']) for slot in adam['state'].values()}
            optimized = sum(len(group['params']) for group in adam['param_groups'])
            require((steps, visits) == (inputs['steps'], inputs['steps'] *
                                       (inputs['shared_per_step']+inputs['swapped_per_step']))
                    and (steps, visits) == (record['steps'], record['visits'])
                    and state['role'] == arm and state['seed'] == int(seed) and state['task_id'] == inputs['task']
                    and ticks == {steps} and optimized == sum(not k.startswith('value.') for k in params)
                    and all(group['lr'] == inputs['learning_rate'] for group in adam['param_groups'])
                    and state['initial_weights_sha256'] == inputs['checkpoint']['weights_sha256']
                    and value == original_value == record['value_sha256'],
                    f'endpoint optimizer or value identity differs: {role}')
        export_dir = run/'policies'/role
        require(digest(export_dir/'model.pt') == record['sha256']
                and read(export_dir/'export.json')['models']['duel']['version'] == role,
                f'export differs: {role}')
        identities[role] = dict(checkpoint_sha256=record['sha256'], weights_sha256=got, value_sha256=value,
                                steps=steps, visits=visits)
    return identities


def match_results(run, inputs, roles):
    jobs = read(run/'schedule.json')
    raw = [json.loads(line) for line in (run/'results.jsonl').read_text(encoding='utf-8').splitlines()]
    replies = {r['id']: r for r in raw}
    ids = {job['id'] for job in jobs}
    require(len(jobs) == len(raw) == len(ids) == 1260 and replies.keys() == ids,
            'scheduled jobs or replies are incomplete or duplicated')
    slots = {(x['map'], x['block'], x['rotation']): x for x in inputs['slots']}
    scenes, points, counts, placements = defaultdict(set), defaultdict(Counter), defaultdict(Counter), set()
    for job in jobs:
        meta = job['meta']
        board, block, rotation, role = (meta[k] for k in ('map', 'block', 'rotation', 'role'))
        slot = slots[board, block, rotation]
        seat, = meta['policy_sides']
        key = (board, block, rotation, role)
        require(role in roles and key not in placements and slot['seat'] == seat
                and slot['seed'] == job['seed'] and slot['scenario'] == job['scenario_family']
                and slot['factions'] == job['factions'], f"paired slot differs: {job['id']}")
        placements.add(key)
        row = replies[job['id']]
        result = row['result']
        require(row['status'] == 'complete' and row['engine'] == 'lite' and row['meta'] == meta
                and result['task_id'] == inputs['task'] and result['task_terminal']
                and not result['faults'] and not result.get('teams') and result['bots'] == job['bots']
                and result['factions'] == job['factions'] and result['winner'] in (0, 1, 2),
                f"mismatched or faulted reply: {job['id']}")
        outcome = 'draws' if not result['winner'] else 'wins' if result['winner'] == seat else 'losses'
        scenes[board].add(slot['scenario'])
        points[role][slot['scenario']] += POINTS[outcome]
        counts[board, role].update({outcome: 1, 'games': 1,
                                     'round_cap': int(result['reason'] == 'turn_limit')})
    groups = {b: sorted(scenes[b]) for b in sorted(inputs['maps'])}
    require(len(slots) == 180 and all(len(group) == 30 for group in groups.values()),
            'unexpected scenario count')
    require(all(counts[b, r]['games'] == 60 for b in groups for r in roles), 'incomplete role/board')
    return groups, points, counts


def intervals(inputs, groups, points):
    seeds = sorted({seed for _, seed in inputs['order']})
    all_scenes = [scene for group in groups.values() for scene in group]
    scale = 6 * len(seeds) * len(all_scenes)

    def contrast(sample_seeds, scenes):
        a = sum(points[f'teacher-{seed}'][scene] for seed in sample_seeds for scene in scenes)
        b = sum(points[f'learner-{seed}'][scene] for seed in sample_seeds for scene in scenes)
        bc = len(sample_seeds) * sum(points['bc'][scene] for scene in scenes)
        return b-a, a-bc, b-bc

    point = contrast(seeds, all_scenes)
    rng = random.Random(inputs['bootstrap_seed'])
    draws = []
    size = inputs['bootstrap_samples']
    for _ in range(size):
        chosen = rng.choices(seeds, k=len(seeds))
        scenes = [scene for group in groups.values() for scene in rng.choices(group, k=len(group))]
        draws.append(contrast(chosen, scenes))
    bounds = []
    for draw in zip(*draws):
        ordered = sorted(draw)
        bounds.append((ordered[int(size*.025)], ordered[min(size-1, int(size*.975))]))
    minimum = Fraction(str(inputs['minimum_gain'])) * scale
    passed = all(point[i] >= minimum and bounds[i][0] > 0 for i in (0, 2))
    return dict(differences=dict(zip(KEYS, (p/scale for p in point))),
                interval95=dict(zip(KEYS, ([lo/scale, hi/scale] for lo, hi in bounds))),
                raw_differences=dict(zip(KEYS, point)), raw_max=scale, passed=passed)


def recount(run, inputs_path):
    torch.set_num_threads(1)
    inputs, launch = read(inputs_path), read(run/'launch.json')
    start, end = read(run/'run-start.json'), read(run/'run-exit.json')
    require(end['status'] == 'complete' and start['launch_sha256'] == digest(run/'launch.json')
            and launch['inputs_sha256'] == digest(inputs_path)
            and launch['schedule_sha256'] == digest(run/'schedule.json'), 'run or launcher identity differs')
    time = stage_times(run, inputs, start, end)
    roles = launch['roles']
    checkpoint = endpoints_audit(run, inputs, roles)
    groups, points, counts = match_results(run, inputs, roles)
    result = intervals(inputs, groups, points)
    per_map = {}
    driver = read(run/'audit-result.json')
    for board, group in groups.items():
        per_map[board] = {}
        for role in roles:
            score = sum(points[role][scene] for scene in group) / 180
            tally = counts[board, role]
            reported = driver['per_map'][board][role]
            require(math.isclose(score, reported['score'], abs_tol=1e-12)
                    and all(tally[k] == reported.get(k, 0) for k in POINTS), 'official score breakdown differs')
            per_map[board][role] = dict(tally, score=score)
    require(all(math.isclose(result['differences'][k], driver['differences'][k], abs_tol=1e-12)
                and all(math.isclose(a, b, abs_tol=1e-12) for a, b in zip(result['interval95'][k], driver['interval95'][k]))
                for k in KEYS), 'driver point estimates or interval differ')
    require(result['passed'] == driver['passed'] == end['passed'], 'adoption verdict differs')
    return dict(result, games=1260, paired_slots=180, per_map=per_map,
                scores={role: sum(points[role].values()) / 540 for role in roles},
                times=time, endpoints=checkpoint,
                file_sha256={k: digest(run/k) for k in ('launch.json', 'schedule.json', 'results.jsonl',
                                                        'raw-metadata.tar.gz', 'run-exit.json')})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('inputs', type=Path)
    args = parser.parse_args()
    print(json.dumps(recount(args.run, args.inputs), indent=2))
