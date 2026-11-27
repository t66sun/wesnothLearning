"""Re-evaluate the four frozen #359 greedy exports with the approved #369 seeds."""
from collections import defaultdict
from copy import deepcopy
from itertools import product
from pathlib import Path
import sys
import time

import torch

from learning.common import read_json, sha256
from learning.maps import run_family
from learning.sample import collect
from verification.duel_ppo_comparison_20261106.audit import write_new

from audit_archive import terminal_points
from panel import archive_inventory, preflight
from recount import sample_interval

MODE = Path('/home/tongshu/acceptance/ppo-mode-interaction-20261115-sgUXX6/freeze')
TRANSFER = Path('/home/tongshu/acceptance/ppo-transfer-361-20261115-MjHy2d/freeze')
MODE_SHA = 'd50730235e9627d15c2eb11240ba6bd40a4b0c4d678cba8fecccbc1067c4aba5'
MAPS = ('fallenstar_lake', 'the_freelands', 'weldyn_channel')
BLOCKS = (0, 8, 12, 16, 24, 27)
ROLES = ('bc', 'lambda-0.95-202611081', 'lambda-0.95-202611082', 'lambda-0.95-202611083')
FIRST_SEED = 2026112700


def schedule(root, old):
    jobs = []
    for j in old:
        if j['meta']['mode'] != 'greedy':
            continue
        for repeat in range(2):
            job = deepcopy(j)
            meta = job['meta']
            seat, = meta['policy_sides']
            seed = FIRST_SEED + 12 * MAPS.index(meta['map']) + 2 * BLOCKS.index(meta['block']) + repeat
            job['id'] = f"369-{j['id']}-{repeat}"
            job['output'] = str(root / 'games' / (job['id'] + '.json'))
            job['seed'] = seed
            job['game_family'] = run_family(job)
            meta.update(combat_seed=seed, policy_rng_seed=seed + seat * 100003, repeat=repeat)
            jobs.append(job)
    cells = {(j['meta']['map'], j['meta']['block'], j['meta']['role'], j['meta']['policy_sides'][0],
              j['meta']['repeat']) for j in jobs}
    assert cells == set(product(MAPS, BLOCKS, ROLES, (1, 2), (0, 1)))
    assert len(jobs) == len({j['id'] for j in jobs}) == len(cells) == 288
    return jobs


def freeze(root):
    manifest, _, original, _ = preflight(MODE, MODE_SHA)
    jobs = schedule(root, original)
    seeds = {j['seed'] for j in jobs}
    assert seeds == set(range(FIRST_SEED, FIRST_SEED + 36))
    assert seeds.isdisjoint(j['seed'] for j in original + read_json(TRANSFER / 'schedule.json'))
    inventory = archive_inventory([], jobs)
    assert all(row['combat_seed_overlap'] == 0 for row in inventory.values())
    root.mkdir()
    write_new(root / 'schedule.json', jobs)
    write_new(root / 'preflight.json', dict(source_manifest_sha256=MODE_SHA,
              schedule_sha256=sha256(root / 'schedule.json'), roles=manifest['roles'],
              layouts=manifest['layouts'], runtime=manifest['runtime'], archived_panels=len(inventory),
              first_seed=min(seeds), last_seed=max(seeds), fresh_seeds=len(seeds),
              games_started=0, optimizer_updates=0, planned_games=288, workers=8,
              preflight_seconds=300, collection_seconds=2100, audit_seconds=300))


def score(jobs, replies):
    by_id = {r['id']: r for r in replies}
    assert len(by_id) == len(replies) == len(jobs) == 288
    assert by_id.keys() == {j['id'] for j in jobs}
    cells = defaultdict(dict)
    tallies = defaultdict(lambda: dict(win=0, draw=0, loss=0, turn_cap=0, points=0))
    for j in jobs:
        m = j['meta']
        seat, = m['policy_sides']
        role, board, block = m['role'], m['map'], m['block']
        r = by_id[j['id']]
        assert r['meta'] == m and r['engine'] == 'lite'
        p = terminal_points(j, r, seat)
        capped = r['result']['reason'] == 'turn_limit'
        assert not capped or (p == 1 and r['result']['turns'] == 31)
        table = cells[board, block]
        key = role, seat, m['repeat']
        assert key not in table
        table[key] = p
        tally = tallies[f'{board}/{role}']
        tally[{3: 'win', 1: 'draw', 0: 'loss'}[p]] += 1
        tally['points'] += p
        tally['turn_cap'] += int(capped)
    groups = defaultdict(list)
    for board, block in product(MAPS, BLOCKS):
        table = cells[board, block]
        assert table.keys() == set(product(ROLES, (1, 2), (0, 1)))
        points = {r: sum(table[r, s, t] for s, t in product((1, 2), (0, 1))) for r in ROLES}
        groups[board].append([(points[r] - points['bc']) / 12 for r in ROLES[1:]])
    pooled = sample_interval(groups)
    by_map = {name: sample_interval({name: group}) for name, group in groups.items()}
    return dict(games=len(replies), optimizer_updates=0, roles=ROLES, pooled=pooled,
                by_map=by_map, raw_counts=dict(tallies))


def run(root, expected):
    started = time.time()
    assert sha256(root / 'preflight.json') == expected
    plan = read_json(root / 'preflight.json')
    assert sha256(root / 'schedule.json') == plan['schedule_sha256']
    _, _, original, _ = preflight(MODE, MODE_SHA)
    jobs = read_json(root / 'schedule.json')
    assert jobs == schedule(root, original)
    assert not (root / 'replies.jsonl').exists()
    armed = time.time()
    assert armed - started <= plan['preflight_seconds']
    write_new(root / 'start.json', dict(started=started, preflight_sha256=expected))
    deadline = armed + plan['collection_seconds']
    active = [dict(j, deadline=deadline) for j in jobs]
    write_new(root / 'active.json', active)
    replies = collect(active, plan['workers'], root / 'replies.jsonl')
    end = time.time()
    assert end <= deadline
    result = score(jobs, replies)
    assert time.time() <= min(end + plan['audit_seconds'], started + 2700)
    write_new(root / 'score.json', result)
    write_new(root / 'timing.json', dict(collection_seconds=end-armed, total_seconds=time.time()-started,
              replies_sha256=sha256(root / 'replies.jsonl'), score_sha256=sha256(root / 'score.json')))


if __name__ == '__main__':
    torch.set_num_threads(1)
    action, root_arg, *args = sys.argv[1:]
    path = Path(root_arg).resolve()
    if action == 'freeze':
        freeze(path)
    elif action == 'run':
        run(path, *args)
    else:
        raise ValueError(action)
