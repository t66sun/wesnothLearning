"""Audit a #369 evidence tarball using Python's standard library."""
from collections import Counter, defaultdict
from hashlib import sha256
import json
import math
from pathlib import Path
import random
import sys
import tarfile

MAPS = ('fallenstar_lake', 'the_freelands', 'weldyn_channel')
BLOCKS = (0, 8, 12, 16, 24, 27)
ROSTERS = (('Drakes', 'Knalgan Alliance'), ('Knalgan Alliance', 'Rebels'),
           ('Loyalists', 'Northerners'), ('Northerners', 'Knalgan Alliance'),
           ('Rebels', 'Undead'), ('Undead', 'Loyalists'))
PREFLIGHT = '704bce2ad1381eb1ae2d77a8fa9bacf96770f9275b50c388026bb5295f627ff9'


def bytes_hash(data):
    return sha256(data).hexdigest()


def check_interval(rows, reported):
    # Each integer is the difference in official points over four matched games.
    rng = random.Random(2026111753)
    draws = []
    for _ in range(10000):
        histories = rng.choices(range(3), k=3)
        total = 0
        for board in rows:
            for cluster in rng.choices(board, k=6):
                total += sum(cluster[h] for h in histories)
        draws.append(total)
    denominator = 12 * 6 * len(rows)
    means = [sum(row[h] for board in rows for row in board) / denominator for h in range(3)]
    draws.sort()
    expected = [*means, sum(means) / 3, draws[250] / (3 * denominator), draws[9750] / (3 * denominator)]
    observed = [*reported['per_seed'], reported['point'], *reported['interval95']]
    assert all(math.isclose(x, y, abs_tol=1e-12) for x, y in zip(expected, observed, strict=True))


def audit(archive):
    with tarfile.open(archive, 'r:gz') as bundle:
        raw = {member.name: bundle.extractfile(member).read() for member in bundle if member.isfile()}
    plan = json.loads(raw['preflight.json'])
    start = json.loads(raw['start.json'])
    timing = json.loads(raw['timing.json'])
    assert raw['launcher.exit'].strip() == b'0'
    assert bytes_hash(raw['preflight.json']) == start['preflight_sha256'] == PREFLIGHT
    assert bytes_hash(raw['schedule.json']) == plan['schedule_sha256']
    assert bytes_hash(raw['replies.jsonl']) == timing['replies_sha256']
    assert bytes_hash(raw['score.json']) == timing['score_sha256']
    throughput = json.loads(raw['replies.throughput.jsonl'])
    assert throughput['games'] == throughput['completed'] == 288 and throughput['workers'] == 8
    assert 0 < timing['collection_seconds'] <= 2100 and 0 < timing['total_seconds'] <= 2700
    jobs = json.loads(raw['schedule.json'])
    active = json.loads(raw['active.json'])
    deadline, = {j['deadline'] for j in active}
    assert 0 <= deadline - 2100 - start['started'] <= 300
    assert throughput['started'] + throughput['seconds'] <= deadline
    assert active == [dict(j, deadline=deadline) for j in jobs]
    replies = [json.loads(line) for line in raw['replies.jsonl'].splitlines()]
    by_id = {r['id']: r for r in replies}
    assert len(jobs) == len(by_id) == len(replies) == 288
    assert by_id.keys() == {j['id'] for j in jobs}
    score = json.loads(raw['score.json'])
    roles = ['bc', *[f'lambda-0.95-20261108{i}' for i in (1, 2, 3)]]
    assert score['roles'] == roles and score['optimizer_updates'] == 0
    matrix = {}
    counts = defaultdict(Counter)
    for j in jobs:
        reply = by_id[j['id']]
        m = j['meta']
        r = reply['result']
        assert r['task_id'] == 'official-score-30-v1' and r['task_terminal'] and not r['faults']
        assert reply['status'] == 'complete' and reply['meta'] == m and reply['engine'] == 'lite'
        assert r['factions'] == j['factions'] and r['bots'] == j['bots']
        name, b, t, role = m['map'], m['block'], m['repeat'], m['role']
        seat, = m['policy_sides']
        assert m['mode'] == 'greedy' and m['board_sha256'] == plan['layouts'][name]
        assert tuple(r['factions']) == ROSTERS[BLOCKS.index(b)]
        assert j['seed'] == m['combat_seed'] == 2026112700 + 12*MAPS.index(name) + 2*BLOCKS.index(b) + t
        assert m['weights_sha256'] == plan['roles'][role]['weights_sha256']
        assert j['bots'][2-seat] == plan['runtime']['astra']['path'] and j['max_turns'] == 30
        assert r['winner'] in (0, 1, 2)
        outcome = 'draw' if r['winner'] == 0 else 'win' if r['winner'] == seat else 'loss'
        capped = r['reason'] == 'turn_limit'
        assert not capped or (r['winner'] == 0 and r['turns'] == 31)
        points = {'draw': 1, 'win': 3, 'loss': 0}[outcome]
        key = (name, b, t, seat, role)
        assert key not in matrix
        matrix[key] = points
        tally = counts[f'{name}/{role}']
        tally[outcome] += 1
        tally['points'] += points
        tally['turn_cap'] += capped
    assert set(counts) == set(score['raw_counts'])
    assert all(Counter(score['raw_counts'][k]) == v for k, v in counts.items())
    grouped = []
    for name in MAPS:
        board = []
        for b in BLOCKS:
            sums = [sum(matrix[name, b, t, seat, role] for t in (0, 1) for seat in (1, 2)) for role in roles]
            board.append([ppo - sums[0] for ppo in sums[1:]])
        check_interval([board], score['by_map'][name])
        grouped.append(board)
    check_interval(grouped, score['pooled'])
    print(json.dumps(dict(archive_sha256=bytes_hash(archive.read_bytes()), verified_games=len(matrix),
                          verified_map_role_tallies=len(counts), verified_crossed_intervals=4,
                          pooled=score['pooled'], timing=timing), indent=2))


if __name__ == '__main__':
    audit(Path(sys.argv[1]))
