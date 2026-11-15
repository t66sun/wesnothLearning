"""Independently recount the authorized #359 mode matrix from official replies."""
from collections import Counter, defaultdict
from pathlib import Path
import json
import random
from statistics import mean
import sys
import tarfile
import time

from learning.common import read_json, sha256
from learning.tasks import TASK_ID
from verification.duel_ppo_comparison_20261106.audit import board_digest, write_new

from audit_archive import records
from review import verify_capture

LAUNCH_SHA = 'd50730235e9627d15c2eb11240ba6bd40a4b0c4d678cba8fecccbc1067c4aba5'
MODES = ('sample', 'greedy')


def collect_evidence(root):
    manifest = root / 'mode-launch.json'
    assert sha256(manifest) == LAUNCH_SHA
    m = read_json(manifest)
    assert (root / 'mode-launcher.exit').read_text().strip() == '0'
    start = read_json(root / 'mode-start.json')
    result = read_json(root / 'mode-result.json')
    assert start['launch_sha256'] == result['launch_sha256'] == LAUNCH_SHA
    assert result['status'] == 'complete' and result['games'] == m['games']
    assert 0 < result['wall_seconds'] <= m['seconds']['total'] and result['optimizer_updates'] == 0
    base = Path(m['capture_root'])
    cap, capture, old, _, archived = verify_capture(base)
    assert cap['runtime'] == m['runtime'] and cap['roles'] == m['roles']
    assert archived['archive_sha256'] == m['reused']['archive_sha256']
    assert archived['replies_sha256'] == m['reused']['replies_sha256']
    schedule = root / 'mode-schedule.json'
    assert sha256(schedule) == m['schedule_sha256']
    jobs = read_json(schedule)
    assert len(jobs) == len({j['id'] for j in jobs}) == 288
    assert {j['id']: j for j in jobs if j['id'] in old} == {j['id']: dict(j, deadline=0) for j in capture}
    runtime = read_json(root / 'runtime-new-schedule.json')
    deadline, = {j['deadline'] for j in runtime}
    assert runtime == [dict(j, deadline=deadline) for j in jobs if j['id'] not in old]
    assert 0 <= deadline - m['seconds']['collection'] - start['started'] <= m['seconds']['preflight']
    throughput, = records(root / 'new-results.throughput.jsonl')
    assert throughput['workers'] == m['workers'] == 8
    assert throughput['games'] == throughput['completed'] == 192
    assert throughput['started'] + throughput['seconds'] <= deadline
    assert 0 < result['collection_seconds'] <= m['seconds']['collection']
    assert abs(result['collection_seconds'] - throughput['seconds']) < 1
    new = records(root / 'new-results.jsonl')
    distinct = {x['id']: x for x in new}
    assert len(new) == len(distinct) == len(runtime) == 192
    assert distinct.keys() == {j['id'] for j in runtime}
    assert not (old.keys() & distinct.keys())
    return m, jobs, old | distinct, result, throughput


def histogram(m, jobs, replies):
    bins = defaultdict(Counter)
    scores, identities = defaultdict(dict), {}
    observed_games = Counter()
    runtime_tags = set()
    for j in jobs:
        r = replies[j['id']]
        meta = j['meta']
        player, = meta['policy_sides']
        role, mode, board = (meta[k] for k in ('role', 'mode', 'map'))
        data = r['result']
        assert r['status'] == 'complete' and r['engine'] == 'lite' and r['meta'] == meta
        assert data['task_id'] == j['task_id'] == TASK_ID and j['max_turns'] == 30
        assert data['task_terminal'] and not data['faults'] and data['winner'] in (0, 1, 2)
        assert data['factions'] == j['factions'] and data['bots'] == j['bots']
        assert meta['combat_seed'] == j['seed'] and meta['policy_rng_seed'] == j['seed'] + player * 100003
        assert meta['weights_sha256'] == m['roles'][role]['weights_sha256']
        assert meta['board_sha256'] == m['layouts'][board] == board_digest(j['map_override'])
        if data['reason'] == 'turn_limit':
            assert data['winner'] == 0 and data['turns'] == 31
        if j.get('shard'):
            assert mode == 'sample' and r['training_shard']['written'] > 0
            observed_games['reused'] += 1
        else:
            assert r.get('training_shard') is None
            observed_games[f'new_{mode}'] += 1
        runtime_tags.add(tuple(data[k] for k in ('engine_id', 'rng_version', 'combat_version')))
        k = board, j['seed']
        shape = (meta['block'], j['scenario_family'], tuple(j['factions']), meta['board_sha256'], j['bots'][2-player])
        assert shape == identities.setdefault(k, shape)
        cell = mode, role, player
        assert cell not in scores[k]
        result = 'draw' if data['winner'] == 0 else 'win' if data['winner'] == player else 'loss'
        v = {'draw': 1, 'win': 3, 'loss': 0}[result]
        scores[k][cell] = v
        a = bins[f'{board}/{role}/{mode}']
        a[result] += 1
        a['points'] += v
        a['turn_cap'] += int(data['reason'] == 'turn_limit')
    assert len(runtime_tags) == 1
    assert observed_games == Counter(reused=96, new_greedy=144, new_sample=48)
    assert len(scores) == 18 and all(len(v) == 16 for v in scores.values())
    return scores, dict(bins), runtime_tags.pop()


def sample_interval(grouped):
    rng = random.Random(2026111753)
    n = len(next(iter(grouped.values()))[0])
    baseline = [mean(mean(row[i] for row in group) for group in grouped.values()) for i in range(n)]
    draws = []
    for _ in range(10000):
        h = rng.choices(range(n), k=n)
        draws.append(mean(mean(row[i] for row in rng.choices(group, k=len(group)) for i in h)
                          for group in grouped.values()))
    draws.sort()
    return dict(point=mean(baseline), per_seed=baseline, interval95=[draws[250], draws[9750]])


def comparison(scores, histories, mode, role=None):
    by_board = defaultdict(list)
    for board, seed in sorted(scores):
        table = scores[board, seed]
        def p(m, r):
            return sum(table[m, r, seat] for seat in (1, 2))
        def gain(z, r):
            return p(z, r) - p(z, 'bc')
        if mode == 'interaction':
            row = [(gain('sample', r) - gain('greedy', r)) / 6 for r in histories]
        elif mode == 'by_role':
            row = [(p('sample', role) - p('greedy', role)) / 6]
        else:
            row = [gain(mode, r) / 6 for r in histories]
        by_board[board].append(row)
    value = sample_interval(by_board)
    return dict(**value, status='paired', exact_slots=len(scores)*2,
                paired_blocks={board: len(rows) for board, rows in by_board.items()})


def recount(scores, roles):
    histories = [r for r in roles if r != 'bc']
    return dict(interaction=comparison(scores, histories, 'interaction'),
                sampled_gain=comparison(scores, histories, 'sample'),
                greedy_gain=comparison(scores, histories, 'greedy'),
                mode_by_role={r: comparison(scores, histories, 'by_role', r) for r in roles})


def pack(root, output, capture):
    destination = output / 'raw-mode-metadata.tar.gz'
    with tarfile.open(destination, 'x:gz', compresslevel=1) as bundle:
        for name in ('mode-launch.json', 'mode-preflight.json', 'mode-schedule.json.gz',
                     'mode-start.json', 'mode-result.json', 'runtime-new-schedule.json',
                     'new-results.jsonl', 'new-results.throughput.jsonl', 'mode-launcher.sh',
                     'mode-launcher.log', 'mode-launcher.exit', 'mode-launcher.utc'):
            bundle.add(root / name, arcname=name)
        for name in ('capture-launch.json', 'capture-ledger.json', 'results.jsonl'):
            bundle.add(capture / name, arcname=f'archived_sample/{name}')
    return dict(sha256=sha256(destination), bytes=destination.stat().st_size)


def main(root, output):
    started = time.monotonic()
    m, jobs, replies, prior, throughput = collect_evidence(root)
    scores, counts, runtime = histogram(m, jobs, replies)
    computed = recount(scores, m['roles'])
    maps = {name: recount({k: v for k, v in scores.items() if k[0] == name}, m['roles']) for name in m['layouts']}
    assert computed == {k: prior[k] for k in computed}
    assert counts == prior['raw_counts'] and maps == prior['by_map']
    primary = computed['interaction']
    point, (lo, hi) = primary['point'], primary['interval95']
    floor = m['actionable_interaction']
    assert floor == .05
    passed = point >= floor and lo > 0 and sum(v > 0 for v in primary['per_seed']) >= 2
    passed = passed and computed['sampled_gain']['point'] > 0
    label = 'ppo_specific_gap' if passed else 'actionable_gap_excluded' if hi < floor else 'inconclusive'
    assert label == prior['verdict']
    bundle = pack(root, output, Path(m['capture_root']))
    summary = dict(launch_sha256=LAUNCH_SHA, verdict=label, **computed, by_map=maps, raw_counts=counts,
                   runtime_tags=runtime, games=m['games'], throughput=throughput, collection_seconds=prior['collection_seconds'],
                   wall_seconds=prior['wall_seconds'], recount_seconds=time.monotonic()-started,
                   archive=bundle, optimizer_updates=0)
    write_new(output / 'recount.json', summary)
    print(json.dumps({k:v for k,v in summary.items() if k != 'raw_counts'}, indent=2))


if __name__ == '__main__':
    main(*(Path(x).resolve() for x in sys.argv[1:]))
