"""Recount the #328 games from the frozen schedule and worker replies."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
from fractions import Fraction
import gzip
import hashlib
import json
import math
from pathlib import Path
import random
from zoneinfo import ZoneInfo

ROLES = ('greedy', 'astra')
POINTS = {'wins': 3, 'draws': 1, 'losses': 0}
QUERY_OUTCOMES = ('astra_noncombat', 'absent', 'same', 'changed')


def read_bytes(directory, name):
    plain = directory / name
    return plain.read_bytes() if plain.exists() else gzip.decompress((directory / (name + '.gz')).read_bytes())


def digest(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, error):
    if not condition:
        raise ValueError(error)


def unique(records, key):
    result = {row[key]: row for row in records}
    require(len(result) == len(records), f'duplicate {key} values')
    return result


def recount(directory, inputs_path):
    files = {name: read_bytes(directory, name) for name in ('launch.json', 'schedule.json', 'results.jsonl')}
    inputs_bytes = inputs_path.read_bytes()
    inputs = json.loads(inputs_bytes)
    launch = json.loads(files['launch.json'])
    start = json.loads(read_bytes(directory, 'run-start.json'))
    verdict = json.loads(read_bytes(directory, 'verdict.json'))
    throughput = json.loads(read_bytes(directory, 'results.throughput.jsonl'))
    digests = {name: digest(data) for name, data in files.items()}
    require(digest(inputs_bytes) == launch['inputs_sha256'], 'protocol digest differs')
    require(digests['launch.json'] == start['launch_sha256'], 'launch digest differs')
    require(digests['schedule.json'] == launch['schedule_sha256'], 'schedule digest differs')

    jobs = unique(json.loads(files['schedule.json']), 'id')
    replies = unique([json.loads(line) for line in files['results.jsonl'].splitlines()], 'id')
    require(len(jobs) == 240 and jobs.keys() == replies.keys(), '240 unique matching replies required')
    slots = {(row['map'], row['block'], row['rotation']): row for row in inputs['slots']}
    score = {}
    totals = defaultdict(Counter)
    minutes = defaultdict(float)
    for job_id, job in jobs.items():
        row = replies[job_id]
        result, meta = row['result'], job['meta']
        name, block, rotation = (meta[key] for key in ('map', 'block', 'rotation'))
        seat, = meta['policy_sides']
        role = job['combat_choice']
        key = name, block, rotation, role
        slot = slots[name, block, rotation]
        require(key not in score and role in ROLES
                and (job['scenario_family'], seat, job['seed'], job['factions'])
                == (slot['scenario'], slot['learner_seat'], slot['seed'], slot['factions']),
                f'job differs from the frozen slot: {job_id}')
        require(row['status'] == 'complete' and row['meta'] == meta and row['engine'] == 'lite'
                and result['task_terminal'] and not result['faults'] and result['task_id'] == inputs['task_id']
                and result['bots'] == job['bots'] and result['factions'] == job['factions']
                and result['winner'] in (0, 1, 2) and not result.get('teams'),
                f'faulted or mismatched reply: {job_id}')
        counts = row['combat_choice']
        expected_queries = counts['combat'] if role == 'astra' else 0
        require(counts['queries'] == expected_queries == sum(counts[k] for k in QUERY_OUTCOMES),
                f'query totals disagree: {job_id}')
        outcome = 'draws' if result['winner'] == 0 else 'wins' if result['winner'] == seat else 'losses'
        score[key] = POINTS[outcome]
        totals[name, role].update(counts)
        totals[name, role].update({outcome: 1, 'games': 1, 'games_with_change': int(counts['changed'] > 0),
                                   'round_cap': int(result['reason'] == 'turn_limit')})
        minutes[name, role] += row['combat_worker_seconds'] / 60

    require(len(slots) == 120 and len(score) == 240, 'incomplete paired slots')
    by_map, deltas = {}, {}
    for name in inputs['maps']:
        by_map[name] = {}
        for role in ROLES:
            counts = totals[name, role]
            points = sum(counts[outcome] * value for outcome, value in POINTS.items())
            require(counts['games'] == 60, f'incomplete role on {name}')
            by_map[name][role] = dict(counts, points=points, score=points / 180, worker_minutes=minutes[name, role])
            require(math.isclose(points / 180, verdict['per_map'][name][role]['score'], abs_tol=1e-12),
                    f'driver score disagreement on {name} for {role}')
        deltas[name] = [sum(score[name, block, rotation, 'astra'] - score[name, block, rotation, 'greedy']
                            for rotation in (0, 1)) for block in range(30)]
    rng = random.Random(inputs['bootstrap_seed'])
    draws = sorted(sum(sum(rng.choices(values, k=30)) for values in deltas.values())
                   for _ in range(inputs['bootstrap_samples']))
    interval = [draws[int((len(draws)-1) * q)] / 360 for q in (.025, .975)]
    effect = Fraction(sum(map(sum, deltas.values())), 360)
    require(math.isclose(verdict['difference'], float(effect), abs_tol=1e-12)
            and all(math.isclose(a, b, abs_tol=1e-12) for a, b in zip(interval, verdict['interval95'])),
            'driver effect or interval disagrees with raw result recount')
    seconds = verdict['seconds']
    measured = dict(seconds, prepare=seconds['preparation'])
    within_budget = all(measured[key] <= limit for key, limit in launch['settings'].items())
    passed = within_budget and effect >= Fraction(str(inputs['minimum_gain'])) and interval[0] > 0
    require(verdict['in_budget'] == within_budget and verdict['passed'] == passed, 'verdict disagrees')
    require(throughput['workers'] == inputs['workers'] and throughput['completed'] == 240,
            'throughput record disagrees with the panel')
    local = ZoneInfo('Asia/Shanghai')
    return dict(games=len(score), paired_slots=len(slots), per_map=by_map,
                score={role: sum(row[role]['points'] for row in by_map.values()) / 360 for role in ROLES},
                difference=float(effect), interval95=interval, in_budget=within_budget, passed=passed,
                seconds=seconds, worker_pool_seconds=throughput['seconds'], file_sha256=digests,
                game_start=datetime.fromtimestamp(throughput['started'], local).isoformat(),
                game_finish=datetime.fromtimestamp(throughput['started'] + throughput['seconds'], local).isoformat())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('inputs', type=Path)
    args = parser.parse_args()
    print(json.dumps(recount(args.directory, args.inputs), indent=2))
