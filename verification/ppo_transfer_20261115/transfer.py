"""Prepare and recount #361 on the pinned #306 Lite worker."""
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path
import random
import shutil
from statistics import mean
import sys
import tarfile
import time

import torch

from learning.bc_anchor import weights_sha256
from learning.common import read_json, sha256
from learning.export import load_model
from learning.lite_policy import FrozenPolicies, game_spec
from learning.manifest import tree_hashes
from learning.maps import SPLITS, bind_scenario, frozen_map, run_family
from learning.sample import collect
from learning.tasks import TASK_ID
from verification.duel_ppo_comparison_20261106.audit import board_digest, write_new

from audit_archive import RUNS, WALL, records, sha256_control, terminal_points

sys.path.append(str(RUNS['349'].parent / 'adapter/verification/ppo_vs_bc_20261115'))
from lineage import worker

BASE = Path('/home/tongshu/acceptance')
MODE = BASE / 'ppo-mode-interaction-20261115-sgUXX6/freeze'
MODE_ARCHIVE = BASE / 'ppo-mode-result-20261115-mtIEDU/raw-mode-metadata.tar.gz'
CAPTURE = BASE / 'ppo-diagnosis-20261115-Z8O0k3/capture'
MODE_ARCHIVE_SHA = '5367303ce5efd98040b476eb1b6ebf9cdc317e09bafcd0602d603f7cb27b8012'
HOLDOUT_SHA = '3ff17a173aa6af898aead3564d8d466e5ffa7dcdec9481125c01e47130c7da50'
RESERVE_SHA = '57043fb6c9de3a68d14d36c5ce315927cab5741a31de2e319a0faf06d6e1dbb4'
SEEN = ('the_freelands', 'weldyn_channel')
PRIOR_HOLDOUT = ('fallenstar_lake', 'sullas_ruins')
MAPS = SEEN + PRIOR_HOLDOUT
BLOCKS = {0: ('Drakes', 'Knalgan Alliance'), 12: ('Loyalists', 'Northerners'),
          24: ('Rebels', 'Undead')}
SULLA_SEEDS = {b: 2026111900 + i for i, b in enumerate(BLOCKS)}
OPPONENTS = ('astra', 'v38')
LIMITS = dict(preflight=300, collection=1200, audit=300, total=1800)
BOOTSTRAP_SEED = 2026111961
SAMPLES = 10000
ROLES = ('bc', *WALL)


def source_identity(path, commit):
    with tarfile.open(path, 'r:') as bundle:
        assert bundle.pax_headers['comment'] == commit
        member = f'verification/ppo_transfer_20261115/{Path(__file__).name}'
        assert bundle.extractfile(member).read() == Path(__file__).read_bytes()
    return dict(path=str(path), commit=commit, sha256=sha256(path))


def mode_archive():
    assert sha256(MODE_ARCHIVE) == MODE_ARCHIVE_SHA
    launch = read_json(MODE / 'mode-launch.json')
    assert sha256(MODE / 'mode-schedule.json') == launch['schedule_sha256']
    jobs = read_json(MODE / 'mode-schedule.json')
    replies_path = MODE / 'new-results.jsonl'
    with tarfile.open(MODE_ARCHIVE, 'r:gz') as bundle:
        for name in ('mode-launch.json', 'mode-result.json', 'mode-start.json', 'new-results.jsonl',
                     'runtime-new-schedule.json', 'mode-launcher.exit'):
            assert bundle.extractfile(name).read() == (MODE / name).read_bytes()
    assert (MODE / 'mode-launcher.exit').read_text().strip() == '0'
    assert read_json(MODE / 'mode-result.json')['status'] == 'complete'
    runtime = read_json(MODE / 'runtime-new-schedule.json')
    deadline, = {job['deadline'] for job in runtime}
    assert runtime == [dict(job, deadline=deadline) for job in jobs if job['id'] in
                       {entry['id'] for entry in runtime}]
    all_replies = records(replies_path)
    replies = {row['id']: row for row in all_replies}
    assert len(replies) == len(all_replies) == 192
    assert replies.keys() == {job['id'] for job in runtime}
    chosen = [job for job in jobs if job['meta']['mode'] == 'greedy' and
              job['meta']['block'] in BLOCKS and job['meta']['map'] in MAPS]
    assert len(chosen) == 72
    return launch, jobs, chosen, {job['id']: replies[job['id']] for job in chosen}


def census(source, reference, mode_jobs):
    layouts = {}
    exposures = Counter()
    seen_train_seeds = set()
    periodic_validation = defaultdict(set)
    tracked = {}
    for history in WALL:
        cell = RUNS['306'] / 'cells' / history / 'duel'
        state = read_json(cell / 'state.json')
        log = {row['id']: row for row in records(cell / 'jobs.jsonl')
               if row.get('meta', {}).get('phase') == 'ppo'}
        schedules = []
        claimed = set()
        for epoch in state['history']:
            if epoch['method'] != 'ppo':
                continue
            path = cell / 'schedules' / f"ppo-batch-{epoch['batch']:06d}.json"
            jobs = read_json(path)
            schedules.append((path.name, sha256(path)))
            assert len(jobs) == 8
            assert sum(log[job['id']]['training_shard']['written'] for job in jobs) == epoch['eligible_decisions']
            for job in jobs:
                meta = job['meta']
                seat = meta['seat']
                reply = log[job['id']]
                terminal_points(job, reply, seat)
                assert reply['training_eligible'] and job['id'] not in claimed
                claimed.add(job['id'])
                digest = board_digest(job['map_override'])
                assert layouts.setdefault(meta['map'], digest) == digest
                opponent = job['bots'][2 - seat]
                assert sha256_control(opponent) == source['astra']['teacher_parent_sha256']
                exposures[history, meta['map'], digest, tuple(job['factions']), seat] += 1
                seen_train_seeds.add(job['seed'])
        assert set(log) == claimed
        plans = sorted((cell / 'schedules').glob('validation-*.json'))
        for path in plans:
            for job in read_json(path):
                periodic_validation[job['meta']['map']].add(board_digest(job['map_override']))
        tracked[history] = dict(state_sha256=sha256(cell / 'state.json'), log_sha256=sha256(cell / 'jobs.jsonl'),
                                matched=len(claimed), schedules=schedules, validation_plans=len(plans))
    assert sum(exposures.values()) == 4368
    production = {name: board_digest(frozen_map(name)[0]) for name in SPLITS['duel']['validation']}
    panels = {
        '227 qualification': RUNS['227'] / 'evaluation/validation/plan.json',
        '227 holdout': RUNS['227'] / 'evaluation/holdout/plan.json',
        '272 validation': RUNS['272'] / 'validation-base-result/plan.json',
        '272 holdout': RUNS['272'] / 'holdout-base-result/plan.json',
        '306 validation': RUNS['306'] / 'validation/hamlets/plan.json',
        '306 Road to Weldyn': RUNS['306'] / 'holdout/road_to_weldyn/plan.json',
        '306 Summer of Storms': RUNS['306'] / 'holdout/summer_of_storms/plan.json',
        '349 holdout': RUNS['349'] / 'schedule.json',
        '355 sampled': CAPTURE / 'capture-schedule.json',
        '359 matched mode': MODE / 'mode-schedule.json',
    }
    overlaps = {}
    used_seeds = set(seen_train_seeds)
    for label, path in panels.items():
        plan = read_json(path)
        jobs = plan if isinstance(plan, list) else plan['jobs']
        hashes = {job['meta']['map']: board_digest(job['map_override']) for job in jobs}
        overlaps[label] = dict(jobs=len(jobs), schedule_sha256=sha256(path), layouts=hashes,
                               seen_overlap=sorted(set(layouts.values()) & set(hashes.values())))
        used_seeds.update(job['seed'] for job in jobs)
    pilot = RUNS['306'].parent / 'ppo352-pilot-20261115-7cq5lA/pilot-panel-schedule.json'
    used_seeds.update(job['seed'] for job in read_json(pilot))
    for route in ('306', '322'):
        for path in (RUNS[route] / 'cells').glob('*/duel/schedules/*.json'):
            used_seeds.update(j['seed'] for j in read_json(path))
    assert not set(SULLA_SEEDS.values()) & used_seeds
    reserve_path = CAPTURE / 'confirmation-reserve.json'
    assert sha256(reserve_path) == RESERVE_SHA
    reserve = {row['board_sha256'] for row in read_json(reserve_path).values()}
    prior = reference['boards']
    boards = {}
    for name in MAPS:
        if name in SEEN:
            board, file_digest = frozen_map(name)
            digest = board_digest(board)
            assert digest == layouts[name]
            assert digest == board_digest(next(j['map_override'] for j in mode_jobs
                                               if j['meta']['map'] == name))
            path = Path(source['source']['source']) / 'data/rules/1.18.8/maps' / f'{name}.json'
            data = read_json(path)
            boards[name] = dict(group='seen', board_sha256=digest, file_sha256=file_digest,
                                kind='native export', asset=data.get('source', name), edits=[])
        else:
            meta = prior[name]
            path = Path(meta['path'])
            assert sha256(path) == meta['file_sha256']
            digest = board_digest(read_json(path)['board'])
            lineage = read_json(RUNS['349'] / 'lineage.json')
            assert sha256(RUNS['349'] / 'lineage.json') == reference['lineage_sha256']
            assert digest == meta['board_sha256'] and digest not in layouts.values()
            assert digest not in lineage['exposure']['excluded_boards']
            boards[name] = dict(group='prior holdout', board_sha256=digest, file_sha256=meta['file_sha256'],
                                kind='native-derived', asset=meta['native_asset'], edits=meta['edits'])
    assert not reserve & {row['board_sha256'] for row in boards.values()}
    rows = [dict(history=h, map=name, board_sha256=digest, factions=factions, learner_seat=seat,
                 opponent_sha256=source['astra']['teacher_parent_sha256'], games=count)
            for (h, name, digest, factions, seat), count in sorted(exposures.items())]
    return dict(layouts=layouts, games=rows, settled=tracked, fixed_astra=source['astra']['teacher_parent_sha256'],
                layout_kind={name: 'synthetic' if name == 'arena2' else 'native export' for name in layouts},
                production_validation=production,
                production_overlap=sorted(set(production.values()) & set(layouts.values())),
                periodic_validation={name: sorted(digests) for name, digests in periodic_validation.items()},
                prior_panels=overlaps, design_layouts=boards,
                reserve_sha256=RESERVE_SHA, confirmation_boards=sorted(reserve))


def make_jobs(root, archived, reference, alias, boards):
    source = [job for job in archived if job['meta']['map'] == 'fallenstar_lake']
    board = read_json(Path(reference['boards']['sullas_ruins']['path']))['board']
    astra = list(archived)
    for old in source:
        job = deepcopy(old)
        meta = job['meta']
        job['id'] = 'transfer-' + old['id'].replace('fallenstar_lake', 'sullas_ruins')
        job['output'] = str(root / 'games' / f"{job['id']}.json")
        job['map_override'] = board
        job['seed'] = seed = SULLA_SEEDS[meta['block']]
        seat, = meta['policy_sides']
        meta.update(map='sullas_ruins', map_sha256=boards['sullas_ruins']['file_sha256'],
                    board_sha256=boards['sullas_ruins']['board_sha256'], combat_seed=seed,
                    policy_rng_seed=seed + seat * 100003)
        job['game_family'] = run_family(job)
        astra.append(bind_scenario(job))
    second = []
    for old in astra:
        job = deepcopy(old)
        job['id'] = f"v38-{old['id']}"
        job['output'] = str(root / 'games' / f"{job['id']}.json")
        meta = job['meta']
        seat, = meta['policy_sides']
        job['bots'][2-seat] = meta['control'] = alias
        second.append(job)
    return sorted(astra + second, key=lambda job: (
        job['meta']['block'], MAPS.index(job['meta']['map']), job['meta']['rotation'],
        job['id'].startswith('v38-'), ROLES.index(job['meta']['role'])))


def opponent(job):
    return 'v38' if job['id'].startswith('v38-') else 'astra'


def verify_jobs(jobs, m, reused, root):
    assert len(jobs) == len({job['id'] for job in jobs}) == 192
    assert len(reused) == 72
    rules = m['runtime']['rules']
    catalog = read_json(Path(rules['path']) / 'rules.json')
    cells, blocks = set(), {}
    for job in jobs:
        meta = job['meta']
        name, block, role = (meta[k] for k in ('map', 'block', 'role'))
        seat, = meta['policy_sides']
        control = opponent(job)
        assert name in MAPS and block in BLOCKS and role in ROLES and seat in (1, 2)
        key = name, block, seat, role, control
        assert key not in cells
        cells.add(key)
        assert seat == meta['rotation'] + 1 and meta['control_sides'] == [3-seat]
        assert job['factions'] == list(BLOCKS[block])
        assert job['deadline'] == 0 and job['engine'] == 'lite'
        assert job['rules_dir'] == rules['path'] and meta['rules_sha256'] == rules['sha256']
        assert job['task_id'] == TASK_ID and job['max_turns'] == 30 and job['teams'] is None
        assert job['score_only_astra'] is False and job['score_only_policy'] is False
        assert meta['mode'] == 'greedy' and meta['phase'] == 'ppo'
        assert 'shard' not in job and 'policy' not in job
        expected = m['roles'][role]
        assert job['learning'] == {'sides': {str(seat): {'teacher': False, 'version': f"v{expected['version']}"}}}
        assert meta['checkpoint_sha256'] == expected['checkpoint_sha256']
        assert meta['weights_sha256'] == expected['weights_sha256']
        assert job['bots'][seat-1] == meta['policy'] == m['policies'][role]['addon']
        assert job['bots'][2-seat] == meta['control'] == m['opponents'][control]['path']
        assert len(set(job['bots'])) == 2
        assert meta['board_sha256'] == m['design_layouts'][name]['board_sha256'] == board_digest(job['map_override'])
        assert job['seed'] == meta['combat_seed']
        assert meta['policy_rng_seed'] == job['seed'] + seat * 100003
        if job['id'] not in reused:
            assert Path(job['output']).parent == root / 'games'
        spec = game_spec(job, catalog)
        assert len(spec['units']) == 2 and all(unit['leader'] for unit in spec['units'])
        identity = (job['seed'], job['scenario_family'], job['game_family'])
        assert blocks.setdefault((name, block), identity) == identity
    assert len(blocks) == 12 and len({v[0] for v in blocks.values()}) == 12
    assert {job['id'] for job in jobs if job['id'] in reused} == set(reused)


def verify_artifacts(m):
    for role, p in m['policies'].items():
        expected = m['roles'][role]
        assert sha256(Path(expected['path'])) == expected['checkpoint_sha256']
        assert tree_hashes(Path(p['folder'])) == p['files']
        model, _ = load_model(Path(p['folder']) / 'model.pt', 'duel')
        assert weights_sha256(model.state_dict()) == expected['weights_sha256']
        assert b'["mode"]="greedy"' in (Path(p['addon']) / 'lua/config.lua').read_bytes()
    alias = m['opponents']['v38']
    assert tree_hashes(Path(alias['path']).parent) == m['policies']['bc']['files']
    assert alias['weights_sha256'] == m['roles']['bc']['weights_sha256']


def preflight(root, digest):
    assert sha256(root / 'launch.json') == digest
    m = read_json(root / 'launch.json')
    assert m['runtime'] == worker()
    source = m['adapter']
    assert source_identity(Path(source['path']), source['commit']) == source
    for name, field in [('schedule.json', 'schedule_sha256'), ('exposure.json', 'exposure_sha256')]:
        assert sha256(root / name) == m[field]
    assert m['mode_archive_sha256'] == MODE_ARCHIVE_SHA
    origin, _, archived, reused = mode_archive()
    assert m['roles'] == origin['roles'] and m['runtime'] == origin['runtime']
    assert m['policies'] == origin['greedy_policies']
    verify_artifacts(m)
    jobs = read_json(root / 'schedule.json')
    assert {job['id']: job for job in jobs if job['id'] in reused} == {job['id']: job for job in archived}
    verify_jobs(jobs, m, reused, root)
    for job in archived:
        terminal_points(job, reused[job['id']], job['meta']['policy_sides'][0])
    assert m['games'] == dict(matrix=192, reused=72, new=120, new_astra=24, new_v38=96)
    assert m['workers'] == 8 and m['seconds'] == LIMITS
    return m, jobs, reused


def freeze(root, archive, commit):
    started = time.monotonic()
    m, mode_jobs, archived, reused = mode_archive()
    assert m['runtime'] == worker()
    assert sha256(RUNS['349'] / 'launch.json') == HOLDOUT_SHA
    reference = read_json(RUNS['349'] / 'launch.json')
    assert m['roles'] == reference['roles'] and m['runtime'] == reference['runtime']
    exposure = census(m['runtime'], reference, mode_jobs)
    root.mkdir(exist_ok=False)
    old_alias = m['greedy_policies']['bc']
    alias_folder = root / 'v38-opponent'
    shutil.copytree(old_alias['folder'], alias_folder)
    alias = str(alias_folder / Path(old_alias['addon']).name)
    jobs = make_jobs(root, archived, reference, alias, exposure['design_layouts'])
    write_new(root / 'exposure.json', exposure)
    write_new(root / 'schedule.json', jobs)
    launch = dict(issue=361, runtime=m['runtime'], roles=m['roles'], policies=m['greedy_policies'],
                  adapter=source_identity(archive, commit), mode_archive_sha256=MODE_ARCHIVE_SHA,
                  design_layouts=exposure['design_layouts'], exposure_sha256=sha256(root / 'exposure.json'),
                  schedule_sha256=sha256(root / 'schedule.json'), task=TASK_ID, mode='greedy',
                  opponents=dict(astra={'path': m['runtime']['astra']['path'],
                                        'file_sha256': exposure['fixed_astra']},
                                 v38={'path': alias, 'weights_sha256': m['roles']['bc']['weights_sha256']}),
                  games=dict(matrix=192, reused=72, new=120, new_astra=24, new_v38=96),
                  workers=8, seconds=LIMITS, optimizer_updates=0,
                  bootstrap={'seed': BOOTSTRAP_SEED, 'samples': SAMPLES},
                  acceptance='192 unique terminal official scores with zero faults and updates within cap')
    write_new(root / 'launch.json', launch)
    digest = sha256(root / 'launch.json')
    preflight(root, digest)
    pairs = {}
    for job in jobs:
        seat, = job['meta']['policy_sides']
        pairs.setdefault((opponent(job), job['meta']['role'], seat), job)
    assert len(pairs) == 16
    for (name, _, seat), job in pairs.items():
        policies = FrozenPolicies(job)
        assert policies.modes == ({seat: False} if name == 'astra' else {1: False, 2: False})
        assert set(policies.models) == set(policies.modes)
    assert not (root / 'results.jsonl').exists()
    evidence = dict(launch_sha256=digest, schedule_sha256=launch['schedule_sha256'],
                    exposure_sha256=launch['exposure_sha256'], games=launch['games'],
                    model_path_pairs=len(pairs), games_started=0, optimizer_updates=0,
                    preflight_seconds=time.monotonic()-started)
    write_new(root / 'preflight.json', evidence)
    print(json.dumps(evidence, indent=2), flush=True)


def estimate(blocks):
    def deltas(sampled, histories):
        return {(name, control): mean(
            (block[control, h] - block[control, 'bc']) / 6
            for block in sampled[name] for h in histories)
                for name in MAPS for control in OPPONENTS}

    def contrasts(d):
        result = {f'{name}/{control}': score for (name, control), score in d.items()}
        for control in OPPONENTS:
            for group, names in [('seen', SEEN), ('prior_holdout', PRIOR_HOLDOUT)]:
                result[f'{group}/{control}'] = mean(d[name, control] for name in names)
            result[f'transfer/{control}'] = result[f'prior_holdout/{control}'] - result[f'seen/{control}']
        for group in (*MAPS, 'seen', 'prior_holdout'):
            result[f'opponent/{group}'] = result[f'{group}/v38'] - result[f'{group}/astra']
        result['opponent/all'] = mean(result[f'opponent/{name}'] for name in MAPS)
        result['transfer_x_opponent'] = result['transfer/v38'] - result['transfer/astra']
        return result

    point = contrasts(deltas(blocks, WALL))
    histories = {h: contrasts(deltas(blocks, [h])) for h in WALL}
    draws = {name: [] for name in point}
    rng = random.Random(BOOTSTRAP_SEED)
    for _ in range(SAMPLES):
        sample = {name: rng.choices(blocks[name], k=3) for name in MAPS}
        h = rng.choices(WALL, k=3)
        for key, value in contrasts(deltas(sample, h)).items():
            draws[key].append(value)
    report = {}
    for key, value in point.items():
        values = sorted(draws[key])
        report[key] = dict(point=value, interval95=[values[250], values[9750]],
                           per_history={h: histories[h][key] for h in WALL})
    return report


def recount(root, m, jobs, reused):
    runtime = read_json(root / 'runtime-schedule.json')
    deadline, = {job['deadline'] for job in runtime}
    assert runtime == [dict(job, deadline=deadline) for job in jobs if job['id'] not in reused]
    raw = records(root / 'results.jsonl')
    new = {row['id']: row for row in raw}
    assert len(raw) == len(new) == 120 and not new.keys() & reused.keys()
    replies = new | reused
    assert replies.keys() == {job['id'] for job in jobs}
    stats, = records(root / 'results.throughput.jsonl')
    assert stats['workers'] == 8 and stats['games'] == stats['completed'] == 120
    assert stats['started'] + stats['seconds'] <= deadline
    counts = defaultdict(Counter)
    grouped = defaultdict(Counter)
    for job in jobs:
        row = replies[job['id']]
        meta = job['meta']
        seat, = meta['policy_sides']
        assert row['meta'] == meta and row['engine'] == 'lite'
        points = terminal_points(job, row, seat)
        cap = row['result']['reason'] == 'turn_limit'
        if cap:
            assert points == 1 and row['result']['turns'] == 31
        control = opponent(job)
        key = meta['map'], control, meta['role']
        counts[key][{3: 'wins', 1: 'draws', 0: 'losses'}[points]] += 1
        counts[key]['turn_cap'] += cap
        counts[key]['points'] += points
        grouped[meta['map'], meta['block']][control, meta['role']] += points
    blocks = {name: [grouped[name, b] for b in BLOCKS] for name in MAPS}
    return dict(status='complete', games=m['games'], scores={'/'.join(k): dict(c) for k, c in counts.items()},
                inference=estimate(blocks), launch_sha256=sha256(root / 'launch.json'),
                new_replies_sha256=sha256(root / 'results.jsonl'), collection_seconds=stats['seconds'],
                optimizer_updates=0)


def run(root, digest):
    started = time.time()
    assert not (root / 'start.json').exists() and not (root / 'results.jsonl').exists()
    m, jobs, reused = preflight(root, digest)
    preflight_done = time.time()
    assert preflight_done - started <= LIMITS['preflight']
    deadline = min(preflight_done + LIMITS['collection'], started + LIMITS['total'] - LIMITS['audit'])
    active = [dict(job, deadline=deadline) for job in jobs if job['id'] not in reused]
    assert len(active) == 120
    write_new(root / 'start.json', dict(started=started, deadline=deadline, launch_sha256=digest))
    write_new(root / 'runtime-schedule.json', active)
    collect(active, m['workers'], root / 'results.jsonl')
    finished = time.time()
    print(f'Collection exited. Raw replies are preserved at {root}', flush=True)
    assert finished <= deadline
    result = recount(root, m, jobs, reused)
    assert time.time() <= min(finished + LIMITS['audit'], started + LIMITS['total'])
    write_new(root / 'result.json', result | {'wall_seconds': time.time()-started})


if __name__ == '__main__':
    torch.set_num_threads(1)
    mode, output, *args = sys.argv[1:]
    root = Path(output).resolve()
    if mode == 'freeze':
        freeze(root, Path(args[0]).resolve(), args[1])
    elif mode == 'run':
        run(root, args[0])
    elif mode == 'recount':
        manifest, jobs, reused = preflight(root, args[0])
        print(json.dumps(recount(root, manifest, jobs, reused), indent=2))
    else:
        raise ValueError('expected freeze, run or recount')
