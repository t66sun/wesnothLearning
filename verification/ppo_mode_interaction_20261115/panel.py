"""Freeze and score the #359 mode matrix using the pinned Lite collector."""
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
import shutil
import sys
import tarfile
import time

import torch

from learning.bc_anchor import weights_sha256
from learning.common import read_json, sha256
from learning.lite_policy import FrozenPolicies, game_spec
from learning.manifest import tree_hashes
from learning.maps import bind_scenario, run_family
from learning.sample import collect
from learning.tasks import TASK_ID
from verification.duel_ppo_comparison_20261106.audit import board_digest, write_new
from verification.ppo_batch_comparison_20261107.panels import plan_jobs

from actions import sample
from audit_archive import RUNS, paired, records, slot, terminal_points
from capture import BLOCKS
from review import verify_capture

CAPTURE = Path('/home/tongshu/acceptance/ppo-diagnosis-20261115-Z8O0k3/capture')
PILOT = RUNS['306'].parent / 'ppo352-pilot-20261115-7cq5lA'
NEW_BLOCKS = (12, 27)
ROSTERS = {12: ('Loyalists', 'Northerners'), 27: ('Undead', 'Loyalists')}
SEED0 = 2026111870
SECONDS = dict(preflight=300, collection=1200, audit=300, total=1800)
MODES = ('sample', 'greedy')
THRESHOLD = .05


def source_identity(archive, commit):
    with tarfile.open(archive, 'r:') as tar:
        assert tar.pax_headers['comment'] == commit
        for name in ('panel.py', 'actions.py'):
            path = Path(__file__).with_name(name)
            member = f'verification/{path.parent.name}/{name}'
            assert tar.extractfile(member).read() == path.read_bytes()
    return dict(path=str(archive), commit=commit, sha256=sha256(archive))


def archive_inventory(old, new):
    reached = {j['seed'] for j in old + new}
    routes = [
        *sorted(RUNS['227'].glob('evaluation/*/plan.json')),
        *sorted(RUNS['272'].glob('*/plan.json')),
        *sorted(RUNS['306'].glob('*/*/plan.json')),
        *sorted(RUNS['322'].glob('*/*/plan.json')),
        RUNS['349'] / 'schedule.json',
        PILOT / 'pilot-panel-schedule.json',
    ]
    report = {}
    for path in routes:
        plan = read_json(path)
        jobs = plan if isinstance(plan, list) else plan['jobs']
        collisions = [j for j in jobs if j['seed'] in reached]
        exact = [j for j in collisions if 'map_override' in j and
                 any(j['seed'] == k['seed'] and j['factions'] == k['factions']
                     and board_digest(j['map_override']) == board_digest(k['map_override'])
                     and j['meta'].get('policy_sides') == k['meta']['policy_sides']
                     and j.get('task_id') == k['task_id']
                     and j['meta'].get('weights_sha256') == k['meta']['weights_sha256']
                     for k in old + new)]
        assert not exact
        report[str(path)] = dict(sha256=sha256(path), jobs=len(jobs), combat_seed_overlap=len(collisions),
                                 candidate_matches=len(exact))
    for route in ('306', '322'):
        seeds = {j['seed'] for path in (RUNS[route] / 'cells').glob('*/duel/schedules/ppo-batch-*.json')
                 for j in read_json(path)}
        assert {j['seed'] for j in new}.isdisjoint(seeds)
    return report


def greedy_exports(root, capture):
    policies = {}
    for role, p in capture['policies'].items():
        folder = root / 'greedy' / role
        shutil.copytree(p['folder'], folder)
        addon = folder / Path(p['addon']).name
        config = addon / 'lua/config.lua'
        text = config.read_bytes()
        assert text.count(b'["mode"]="sample"') == 1
        config.write_bytes(text.replace(b'["mode"]="sample"', b'["mode"]="greedy"'))
        files = tree_hashes(folder)
        changed = {k for k in files if files[k] != p['files'][k]}
        assert changed == {f'{addon.name}/lua/config.lua'} and files.keys() == p['files'].keys()
        policies[role] = dict(folder=str(folder), addon=str(addon), files=files)
    return policies


def sample_extension(root, manifest, captured):
    template = captured[0]
    runtime = manifest['runtime']
    jobs = []
    for index, (name, board) in enumerate(manifest['boards'].items()):
        for role, checkpoint in manifest['roles'].items():
            for job in plan_jobs(root / 'games', manifest['policies'][role]['addon'],
                                 runtime['astra']['path'], template['wesnoth'], checkpoint['weights_sha256'],
                                 0, runtime['rules']['path'], 'holdout', board):
                meta = job['meta']
                if meta['block'] not in NEW_BLOCKS:
                    continue
                assert tuple(job['factions']) == ROSTERS[meta['block']]
                seat, = meta['policy_sides']
                seed = SEED0 + 2 * index + NEW_BLOCKS.index(meta['block'])
                version = f"v{checkpoint['version']}"
                job['id'] = f"{name}-{role}-{meta['block']}-{seat}"
                job['output'] = str(root / 'games' / f"{job['id']}.json")
                job.update(seed=seed, score_only_policy=False, score_only_astra=False,
                           learning=dict(sides={str(seat): dict(teacher=False, version=version)}))
                meta.update(phase='ppo', corpus='diagnostic_only', board_sha256=board['board_sha256'],
                            role=role, mode='sample', combat_seed=seed, policy_rng_seed=seed + seat * 100003,
                            checkpoint_sha256=checkpoint['checkpoint_sha256'])
                job['game_family'] = run_family(job)
                jobs.append(bind_scenario(job))
    assert len(jobs) == 48
    return jobs


def greedy_job(root, job, policies):
    variant = deepcopy(job)
    meta = variant['meta']
    addon = policies[meta['role']]['addon']
    variant['id'] = job['id'] + '-greedy'
    variant['output'] = str(root / 'games' / f"{variant['id']}.json")
    variant['bots'][meta['policy_sides'][0] - 1] = addon
    variant.pop('shard', None)
    meta.update(mode='greedy', policy=addon)
    return variant


def verify_matrix(jobs, capture, greedy, reused):
    roles = capture['roles']
    assert len(jobs) == len({j['id'] for j in jobs}) == 288
    assert len(reused) == 96
    rule_path = capture['runtime']['rules']['path']
    rules = read_json(Path(rule_path) / 'rules.json')
    cells, designs, seeds = {}, {}, {}
    for j in jobs:
        m = j['meta']
        name, b, role, mode = (m[k] for k in ('map', 'block', 'role', 'mode'))
        seat, = m['policy_sides']
        assert (name, role, mode) in {(n, r, s) for n in capture['boards'] for r in roles for s in MODES}
        assert b in (*BLOCKS, *NEW_BLOCKS) and seat in (1, 2)
        assert j['rules_dir'] == rule_path and j['engine'] == 'lite' and j['max_turns'] == 30
        assert j['task_id'] == TASK_ID and j['deadline'] == 0
        assert not j['score_only_astra'] and not j['score_only_policy']
        assert j['learning'] == dict(sides={str(seat): dict(teacher=False, version=f"v{roles[role]['version']}")})
        assert bool(j.get('shard')) == (j['id'] in reused)
        assert m['checkpoint_sha256'] == roles[role]['checkpoint_sha256']
        assert m['weights_sha256'] == roles[role]['weights_sha256']
        assert m['board_sha256'] == capture['boards'][name]['board_sha256'] == board_digest(j['map_override'])
        assert j['seed'] == m['combat_seed'] and m['policy_rng_seed'] == j['seed'] + seat * 100003
        policies = capture['policies'] if mode == 'sample' else greedy
        assert j['bots'][seat - 1] == m['policy'] == policies[role]['addon']
        assert j['bots'][2 - seat] == capture['runtime']['astra']['path']
        assert len(game_spec(j, rules)['units']) == 2
        identity = (j['scenario_family'], j['game_family'], j['seed'], tuple(j['factions']))
        assert designs.setdefault((name, b), identity) == identity
        assert seeds.setdefault(j['seed'], (name, b)) == (name, b)
        assert (name, b, seat, role, mode) not in cells
        cells[name, b, seat, role, mode] = j
    assert len(designs) == len(seeds) == 18
    return cells


def source_capture(frozen):
    capture, jobs, replies, _, archive = verify_capture(CAPTURE)
    assert capture['runtime'] == frozen['runtime'] and capture['roles'] == frozen['roles']
    assert archive['archive_sha256'] == frozen['reused']['archive_sha256']
    assert archive['replies_sha256'] == frozen['reused']['replies_sha256']
    return capture, [dict(j, deadline=0) for j in jobs], replies


def preflight(root, expected):
    manifest = root / 'mode-launch.json'
    assert sha256(manifest) == expected
    m = read_json(manifest)
    code = m['code']
    assert source_identity(Path(code['path']), code['commit']) == code
    capture, old, replies = source_capture(m)
    for role, p in m['greedy_policies'].items():
        assert tree_hashes(Path(p['folder'])) == p['files']
        old_policy = capture['policies'][role]
        changed = {k for k in p['files'] if p['files'][k] != old_policy['files'][k]}
        assert changed == {f"{Path(p['addon']).name}/lua/config.lua"}
        assert p['files'].keys() == old_policy['files'].keys()
    schedule = root / 'mode-schedule.json'
    assert sha256(schedule) == m['schedule_sha256']
    jobs = read_json(schedule)
    assert {j['id']: j for j in jobs if j['id'] in replies} == {j['id']: j for j in old}
    table = verify_matrix(jobs, capture, m['greedy_policies'], replies)
    assert m['games'] == dict(total=288, reused=96, new=192, new_greedy=144, new_sample=48)
    assert m['workers'] == 8 and m['seconds'] == SECONDS
    return m, table, jobs, replies


def selector_dry_run(table, capture):
    errors = []
    for role in capture['roles']:
        sample_job, greedy = [table['the_freelands', 0, 1, role, m] for m in MODES]
        a, b = (FrozenPolicies(j) for j in (sample_job, greedy))
        row = sample(sample_job)[0]
        replay, deploy = a.choose(row, 1), b.choose(row, 1)
        assert a.modes[1] and not b.modes[1] and replay['choice'] == row['choice']
        assert deploy['log_probability'] >= replay['log_probability'] - 1e-12
        assert abs(replay['log_probability'] - row['log_probability']) <= 1e-5
        error = abs(replay['log_probability'] - row['log_probability'])
        errors.append(error)
    return max(errors)


def freeze(root, archive, commit):
    started = time.monotonic()
    capture, old, replies, _, audit = verify_capture(CAPTURE)
    old = [dict(j, deadline=0) for j in old]
    root.mkdir(exist_ok=False)
    greedy = greedy_exports(root, capture)
    extension = sample_extension(root, capture, old)
    sampled = old + extension
    full = sampled + [greedy_job(root, j, greedy) for j in sampled]
    full.sort(key=lambda j: tuple(j['meta'][k] for k in ('block', 'map', 'rotation', 'role', 'mode')))
    write_new(root / 'mode-schedule.json', full)
    inventory = archive_inventory(old, extension)
    write_new(root / 'archive-join.json', inventory)
    write_new(root / 'mode-launch.json', dict(
        issue=359, runtime=capture['runtime'], roles=capture['roles'],
        layouts={m: r['board_sha256'] for m, r in capture['boards'].items()},
        capture_root=str(CAPTURE), reused=dict(archive_sha256=audit['archive_sha256'],
                                               replies_sha256=audit['replies_sha256'], physical_games=96),
        greedy_policies=greedy, code=source_identity(archive, commit),
        schedule_sha256=sha256(root / 'mode-schedule.json'), inventory_sha256=sha256(root / 'archive-join.json'),
        task=TASK_ID, modes=MODES, games=dict(total=288, reused=96, new=192, new_sample=48, new_greedy=144),
        workers=8, seconds=SECONDS, optimizer_updates=0, actionable_interaction=THRESHOLD,
        support_requires='point >= 0.05, 95% lower > 0, >=2 positive history effects and positive sampled PPO-BC',
        scope='official fixed-Astra mode interaction on three diagnostic layouts'))
    digest = sha256(root / 'mode-launch.json')
    _, table, _, _ = preflight(root, digest)
    error = selector_dry_run(table, capture)
    # The paired interaction is positive when sampling recovers a PPO-specific gain.
    demo = ('one', 'board', 1, ('a', 'b'), 1, 'astra', TASK_ID)
    other = (*demo[:4], 2, *demo[5:])
    fixture = {mode: {r: {demo: a, other: a} for r, a in [('bc', bc), ('ppo', ppo)]}
               for mode, bc, ppo in [('sample', 0, 3), ('greedy', 1, 1)]}
    assert contrasts(fixture, ['ppo'])['interaction']['point'] == 1.
    assert not any((root / x).exists() for x in ('mode-start.json', 'new-results.jsonl', 'games'))
    output = dict(launch_sha256=digest, schedule_sha256=sha256(root / 'mode-schedule.json'),
                  archived_panels=len(inventory), archived_panel_jobs=sum(x['jobs'] for x in inventory.values()),
                  games_in_matrix=288, reused_games=len(replies), new_greedy=144, new_sample=48,
                  verified_sample_choice_replays=4, first_choice_logp_max_error=error, tested_interaction=1.,
                  no_game_preflight=True, games_started=0, optimizer_updates=0,
                  wall_seconds=time.monotonic() - started)
    write_new(root / 'mode-preflight.json', output)
    print(output, flush=True)


def subtract(a, b):
    assert a.keys() == b.keys()
    return {k: a[k] - b[k] for k in a}


def contrasts(scores, histories):
    s, g = (scores[m] for m in MODES)
    sample_gain = [subtract(s[r], s['bc']) for r in histories]
    greedy_gain = [subtract(g[r], g['bc']) for r in histories]
    return dict(interaction=paired(sample_gain, greedy_gain),
                sampled_gain=paired([s[r] for r in histories], [s['bc']] * len(histories)),
                greedy_gain=paired([g[r] for r in histories], [g['bc']] * len(histories)),
                mode_by_role={r: paired([s[r]], [g[r]]) for r in s})


def results(jobs, reused, new, roles):
    assert len(new) == len({r['id'] for r in new}) == 192
    new = {r['id']: r for r in new}
    assert not (new.keys() & reused.keys())
    replies = reused | new
    assert replies.keys() == {j['id'] for j in jobs}
    totals, scores = defaultdict(Counter), {m: defaultdict(dict) for m in MODES}
    for j in jobs:
        m = j['meta']
        r = replies[j['id']]
        seat, = m['policy_sides']
        assert r['meta'] == m and r['engine'] == 'lite'
        points = terminal_points(j, r, seat)
        capped = r['result']['reason'] == 'turn_limit'
        if capped:
            assert points == 1 and r['result']['turns'] == 31
        key = slot(j)
        entries = scores[m['mode']][m['role']]
        assert key not in entries
        entries[key] = points
        tally = totals[m['map'], m['role'], m['mode']]
        tally[{0: 'loss', 1: 'draw', 3: 'win'}[points]] += 1
        tally['turn_cap'] += int(capped)
        tally['points'] += points
    for m in MODES:
        assert set(scores[m]) == set(roles)
        assert all(len(x) == 36 for x in scores[m].values())
    histories = [r for r in roles if r != 'bc']
    stats = contrasts(scores, histories)
    primary = stats['interaction']
    assert primary['exact_slots'] == 36 and sorted(primary['paired_blocks'].values()) == [6] * 3
    point, (lo, hi) = primary['point'], primary['interval95']
    passes = (point >= THRESHOLD and lo > 0 and sum(x > 0 for x in primary['per_seed']) >= 2
              and stats['sampled_gain']['point'] > 0)
    verdict = 'ppo_specific_gap' if passes else (
        'actionable_gap_excluded' if hi < THRESHOLD else 'inconclusive')
    return dict(verdict=verdict, histories=histories, **stats, by_map={
        name: contrasts({m: {r: {k: v for k, v in p.items() if k[0] == name}
                             for r, p in x.items()} for m, x in scores.items()}, histories)
        for name in primary['paired_blocks']},
        raw_counts={'/'.join(k): dict(v) for k, v in sorted(totals.items())})


def run(root, expected):
    start = time.time()
    assert not (root / 'mode-start.json').exists() and not (root / 'new-results.jsonl').exists()
    m, _, jobs, reused = preflight(root, expected)
    write_new(root / 'mode-start.json', dict(started=start, launch_sha256=expected))
    armed = time.time()
    assert armed - start <= m['seconds']['preflight']
    deadline = armed + m['seconds']['collection']
    live = [dict(j, deadline=deadline) for j in jobs if j['id'] not in reused]
    assert len(live) == 192
    write_new(root / 'runtime-new-schedule.json', live)
    new = collect(live, m['workers'], root / 'new-results.jsonl')
    done = time.time()
    assert done <= deadline
    verdict = results(jobs, reused, new, m['roles'])
    assert time.time() <= min(done + m['seconds']['audit'], start + m['seconds']['total'])
    write_new(root / 'mode-result.json', dict(status='complete', launch_sha256=expected,
              games=m['games'], collection_seconds=done - armed, wall_seconds=time.time() - start,
              optimizer_updates=0, **verdict))


if __name__ == '__main__':
    torch.set_num_threads(1)
    action, output, *args = sys.argv[1:]
    output = Path(output).resolve()
    if action == 'freeze':
        freeze(output, Path(args[0]).resolve(), args[1])
    elif action == 'run':
        run(output, args[0])
    else:
        raise ValueError('expected freeze or run')
