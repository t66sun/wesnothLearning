"""Prepare or run the frozen #328 Lite duel comparison."""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path
import random
import shutil
from statistics import mean
import time

from learning.common import read_json, sha256
from learning.evaluate import official_score
from learning.export import export, load_model
from learning.manifest import tree_hashes
from learning.sample import collect
from learning.teachers import lineage
from verification.duel_ppo_comparison_20261106.audit import write_new
from verification.ppo_terminal_return_20261108.driver import PARENT, RULES
from .protocol import HERE, ROLES, preflight, schedule

INPUTS_PATH = HERE/'inputs.json'
INPUTS = read_json(INPUTS_PATH)
LIMITS = INPUTS['seconds']
CHECKPOINT = PARENT/'duel/last_bc.pt'


def verify_inputs():
    import _engine_lite

    parent = read_json(PARENT/'manifest.json')
    control = parent['opponents'][0]['path']
    if (sha256(CHECKPOINT) != INPUTS['checkpoint']['checkpoint_sha256']
            or sha256(PARENT/'manifest.json') != INPUTS['checkpoint']['manifest_sha256']
            or sha256(PARENT/'duel/bc_gate.json') != INPUTS['checkpoint']['gate_sha256']
            or lineage() != INPUTS['astra']
            or sha256(control) != INPUTS['astra']['teacher_parent_sha256']
            or sha256(RULES/'rules.json') != INPUTS['rules_sha256']
            or sha256(_engine_lite.__file__) != INPUTS['extension_sha256']):
        raise ValueError('a frozen evaluation input differs')
    return control, parent['baseline']['path']


def prepare(output, commit, archive):
    started = time.monotonic()
    control, wesnoth = verify_inputs()
    output.mkdir()
    model, _ = load_model(CHECKPOINT, 'duel')
    policy_dir = output/'policy'
    addon = export(model, policy_dir, name='FrozenV38', mode='greedy', version='v38', package=False)
    shutil.copyfile(CHECKPOINT, policy_dir/'model.pt')
    jobs = schedule(output, INPUTS, str(addon), control, wesnoth, 0)
    if preflight(jobs, read_json(RULES/'rules.json')) != INPUTS['slots']:
        raise ValueError('planned pairings differ from the frozen design')
    write_new(output/'schedule.json', jobs)
    launch = dict(commit=commit, archive=str(archive), archive_sha256=sha256(archive),
                  inputs_sha256=sha256(INPUTS_PATH), schedule_sha256=sha256(output/'schedule.json'),
                  policy_files=tree_hashes(policy_dir), settings=LIMITS,
                  preparation_seconds=time.monotonic()-started)
    if launch['preparation_seconds'] > LIMITS['prepare']:
        raise ValueError('preparation exceeded its budget')
    write_new(output/'launch.json', launch)
    print(sha256(output/'launch.json'), flush=True)


def audit(jobs, results):
    expected = {job['id']: job for job in jobs}
    replies = {row['id']: row for row in results}
    if len(expected) != 240 or set(replies) != set(expected) or len(results) != 240:
        raise ValueError('evaluation requires all 240 unique scheduled replies')
    cells, counters = defaultdict(dict), defaultdict(Counter)
    for key, row in replies.items():
        job = expected[key]
        meta = job['meta']
        seat, = meta['policy_sides']
        role = job['combat_choice']
        result = row.get('result', {})
        if (row['status'] != 'complete' or row['meta'] != meta or result['faults']
                or result['winner'] not in (0, 1, 2) or result['bots'] != job['bots']
                or result['factions'] != job['factions'] or result['task_id'] != INPUTS['task_id']
                or not result['task_terminal']):
            raise ValueError(f'faulted or mismatched game {key}')
        counts = row['combat_choice']
        if role == 'astra':
            if (counts['queries'] != counts['combat'] or counts['queries'] !=
                    sum(counts[name] for name in ('astra_noncombat', 'absent', 'same', 'changed'))):
                raise ValueError(f'inconsistent combat queries for {key}')
        elif any(count for name, count in counts.items() if name != 'combat'):
            raise ValueError(f'greedy role unexpectedly queried Astra for {key}')
        board = meta['map']
        points = official_score(result, seat)
        cells[board, meta['block'], meta['rotation']][role] = points
        counters[board, role].update(counts)
        counters[board, role].update({'games': 1, 'games_with_change': bool(counts['changed']),
                                     'worker_seconds': row['combat_worker_seconds'],
                                     {3: 'wins', 1: 'draws', 0: 'losses'}[points]: 1})
    by_map, deltas = {}, {}
    for board in INPUTS['maps']:
        scores = {role: [mean(cells[board, block, rotation][role] for rotation in (0, 1))
                         for block in range(30)] for role in ROLES}
        deltas[board] = [(a-b)/3 for a, b in zip(scores['astra'], scores['greedy'])]
        by_map[board] = {role: dict(counters[board, role], score=mean(scores[role])/3) for role in ROLES}
    rng = random.Random(INPUTS['bootstrap_seed'])
    draws = sorted(mean(mean(rng.choices(values, k=len(values))) for values in deltas.values())
                   for _ in range(INPUTS['bootstrap_samples']))
    low, high = [draws[int((len(draws)-1)*quantile)] for quantile in (.025, .975)]
    totals = {role: sum(3*row[role].get('wins', 0) + row[role].get('draws', 0) for row in by_map.values())
              for role in ROLES}
    difference = Fraction(totals['astra']-totals['greedy'], 360)
    return dict(games=len(results), per_map=by_map, per_map_difference={k: mean(v) for k, v in deltas.items()},
                score={role: mean(v[role]['score'] for v in by_map.values()) for role in ROLES},
                difference=float(difference), interval95=[low, high],
                passed=difference >= Fraction(str(INPUTS['minimum_gain'])) and low > 0)


def run(output, expected):
    started = time.monotonic()
    launch_path = output/'launch.json'
    if sha256(launch_path) != expected:
        raise ValueError('launch hash differs')
    launch = read_json(launch_path)
    verify_inputs()
    schedule_path = output/'schedule.json'
    if (launch['schedule_sha256'] != sha256(schedule_path) or launch['inputs_sha256'] != sha256(INPUTS_PATH)
            or launch['archive_sha256'] != sha256(launch['archive']) or launch['settings'] != LIMITS
            or launch['policy_files'] != tree_hashes(output/'policy')):
        raise ValueError('evaluation files differ from the launch manifest')
    preparation = launch['preparation_seconds'] + time.monotonic()-started
    if preparation > LIMITS['prepare']:
        raise ValueError('combined preparation exceeded its budget')
    stage = time.monotonic()
    deadline = time.time() + LIMITS['games']
    write_new(output/'run-start.json', dict(launch_sha256=expected, game_deadline=deadline))
    jobs = read_json(schedule_path)
    for job in jobs:
        job['deadline'] = deadline
    results = collect(jobs, INPUTS['workers'], output/'results.jsonl')
    games = time.monotonic()-stage
    stage = time.monotonic()
    try:
        verdict = audit(jobs, results)
    except ValueError as exc:
        write_new(output/'verdict.json', dict(status='incomplete', passed=False, error=str(exc),
                  replies=len(results), seconds=dict(preparation=preparation, games=games,
                  audit=time.monotonic()-stage, total=preparation+games+time.monotonic()-stage)))
        raise
    audit_seconds = time.monotonic()-stage
    total = preparation + games + audit_seconds
    in_budget = games <= LIMITS['games'] and audit_seconds <= LIMITS['audit'] and total <= LIMITS['total']
    verdict.update(status='complete' if in_budget else 'over_budget',
                   passed=verdict['passed'] and in_budget, in_budget=in_budget,
                   seconds=dict(preparation=preparation, games=games, audit=audit_seconds, total=total))
    write_new(output/'verdict.json', verdict)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run'))
    parser.add_argument('output', type=lambda value: Path(value).resolve())
    parser.add_argument('--commit')
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--launch-sha256')
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.output, args.commit, args.archive)
    else:
        run(args.output, args.launch_sha256)
