"""Recount #306 from frozen schedules, stage logs, checkpoints and game replies."""
from collections import defaultdict
import json
from pathlib import Path
from statistics import mean
import sys
import tarfile

import torch

from learning.common import ROOT, read_json, sha256
from learning.schedule import starting_factions
from learning.tasks import reward_config
from verification.duel_ppo_comparison_20261106.audit import board_digest, write_new
from verification.duel_ppo_comparison_20261106.contract import crossed_statistics
from verification.duel_ppo_comparison_20261106.panels import role


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def check_cell(root, name, lam, seed, launch, endpoint):
    cell = root/'cells'/name
    manifest = read_json(cell/'manifest.json')
    config = dict(manifest['config'])
    assert config.pop('gae_lambda') == lam and config.pop('seed') == seed, name
    assert 0 < config.pop('hours') <= 4 and config == launch['config'], name
    assert manifest['rules']['rules_sha256'] == launch['rules']['sha256'], name
    assert manifest['teacher'] == launch['worker']['teacher'], name
    assert [row['sha256'] for row in manifest['opponents']] == [launch['astra']['teacher_parent_sha256']], name
    init = read_json(cell/'initialization.json')
    assert init['optimizer_states'] == 0 and init['weights_sha256'] == launch['endpoint']['weights_sha256'], name
    branch = read_json(cell/'branch.json')
    assert branch['reset_optimizer'] and branch['checkpoints']['duel']['bc_endpoint']['sha256'] == launch['endpoint']['checkpoint_sha256'], name

    stage = read_json(root/f'{name}-exit.json')
    budget = read_json(cell/'budget.json')
    request = read_json(root/f'{name}-request.json')
    hard, admission = budget['hard_deadline'], budget['admission_deadline']
    assert stage['exit_code'] == 0 and not stage['timed_out'], name
    assert request['deadline'] == stage['deadline'] == hard, name
    assert request['lambda'] == lam and request['seed'] == seed, name
    assert 0 < hard-stage['started'] <= launch['seconds']['cell'], name
    assert hard-admission == launch['seconds']['cell']-launch['seconds']['admission'], name
    assert stage['started'] < admission <= stage['finished'] <= hard, name
    assert stage['finished']-stage['started'] == stage['wall_seconds'], name

    wall = cell/'duel/wall.pt'
    assert role(wall) == endpoint, name
    state = torch.load(wall, map_location='cpu', weights_only=False)['runner']
    history = state['history'][budget['history_start']:]
    assert history and all(row['method'] == 'ppo' for row in history), name
    assert state['pending_train'] is None, name
    latest = read_json(cell/'duel/state.json')
    assert latest['history'] == json.loads(json.dumps(state['history'])) and latest['pending_train'] is None, name
    assert latest['pending_validation'] is None and not latest['error'], name
    assert history[-1]['policy_sha256_after'] == endpoint['weights_sha256'], name

    replies = {row['id']: row for row in lines(cell/'duel/jobs.jsonl') if row.get('meta', {}).get('phase') == 'ppo'}
    finish = {row['id']: row['time'] for row in lines(cell/'scheduler.jsonl') if row['event'] == 'finish'}
    stream = []
    trained_boards = set()
    seen = set()
    for offset, entry in enumerate(history):
        batch = budget['first_batch']+offset
        assert entry['batch'] == batch, (name, batch)
        path = cell/'duel/schedules'/f'ppo-batch-{batch:06}.json'
        jobs = read_json(path)
        assert len(jobs) == 8 and len({job['meta']['version'] for job in jobs}) == 1, (name, batch)
        counts = []
        for job in jobs:
            key = job['id']
            assert key not in seen and finish[key] <= hard, key
            seen.add(key)
            assert job['task_id'] == 'official-score-30-v1' and job['max_turns'] == 30, key
            assert job['reward_config'] == reward_config(mode='fixed', gae_lambda=lam), key
            seat = job['meta']['seat']
            assert job['bots'][2-seat] == manifest['opponents'][0]['path'], key
            reply = replies[key]
            assert reply['status'] == 'complete' and reply['training_eligible'], key
            assert reply['result']['task_terminal'] and not reply['result']['faults'], key
            counts.append(reply['training_shard']['written'])
            ordinal = job['training_scenario']['index']
            assert ordinal == len(stream), key
            stream.append((job['scenario_family'], job['game_family'], job['seed'],
                           job['factions'], seat, job['learning']['sides'][str(seat)]['sampling_seed']))
            trained_boards.add(board_digest(job['map_override']))
        assert sum(counts) == entry['planned_targets'], (name, batch)

    first = read_json(cell/'first-online.json')
    first_schedule = cell/'duel/schedules'/f"ppo-batch-{budget['first_batch']:06}.json"
    assert first['games'] == 8 and first['gae_lambda'] == lam and first['settled_at'] <= hard, name
    assert first['rows'] == history[0]['planned_targets'] and first['schedule_sha256'] == sha256(first_schedule), name
    assert first['committed_steps'] == history[0]['committed_steps'] > 0, name
    assert first['complete_returns_checked'] == (lam == 1.), name
    assert seen == set(replies), name
    for path in (cell/'duel/schedules').glob('validation-*.json'):
        trained_boards.update(board_digest(job['map_override']) for job in read_json(path))

    totals = {key: sum(row[key] for row in history)
              for key in ('committed_steps', 'inspected_decisions', 'committed_decisions')}
    totals.update(settled_batches=len(history), fresh_targets=sum(row['planned_targets'] for row in history),
                  rejected_steps=sum(bool(row.get('kl_stopped')) for row in history))
    totals['rejected_decision_visits'] = totals['inspected_decisions'] - totals['committed_decisions']
    totals['fresh_per_hour'] = totals['fresh_targets']*3600/stage['wall_seconds']
    recorded = read_json(root/f'{name}-ledger.json')
    assert totals == {key: recorded[key] for key in totals}, name
    return dict(totals, games=len(seen), endpoint=endpoint, first=first,
                wall_seconds=stage['wall_seconds']), stream, trained_boards


def score_panel(folder, name, blocks, endpoints, board):
    plan = read_json(folder/'plan.json')
    replies = lines(folder/'results.jsonl')
    by_id = {row['id']: row for row in replies}
    assert len(by_id) == len(replies) == len(plan['jobs']), name
    assert set(by_id) == {job['id'] for job in plan['jobs']}, name
    aliases = {key: row['weights_sha256'] for key, row in endpoints.items()}
    assert aliases == plan['aliases'] and plan['roles'] == endpoints and plan['blocks'] == blocks, name
    groups = defaultdict(dict)
    design = defaultdict(set)
    for job in plan['jobs']:
        row = by_id[job['id']]
        result = row['result']
        meta = job['meta']
        assert meta['map'] == name and meta['map_sha256'] == board['file_sha256'], job['id']
        assert board_digest(job['map_override']) == board['board_sha256'], job['id']
        assert row['status'] == 'complete' and not result['faults'] and result['task_terminal'], job['id']
        assert len(result['bots']) == 2 and result['winner'] in (0, 1, 2), job['id']
        assert row['meta']['weights_sha256'] == meta['weights_sha256'], job['id']
        key, scene, rotation = meta['weights_sha256'], job['scenario_family'], meta['rotation']
        seat, = meta['policy_sides']
        assert rotation not in groups[key, scene] and seat in (1, 2), job['id']
        points = 1 if result['winner'] == 0 else 3 if result['winner'] == seat else 0
        groups[key, scene][rotation] = (seat, points/3)
        design[key].add((scene, rotation, seat, job['seed'], tuple(job['factions'])))
    first = next(iter(design.values()))
    assert len(first) == 2*blocks and all(value == first for value in design.values()), name
    assert set(design) == set(aliases.values()), name
    if plan['partition'] == 'holdout':
        factions = {faction for pair in starting_factions(2, 'duel') for faction in pair}
        assert {r[4] for r in first} == {(a, b) for a in factions for b in factions if a != b}, name
    scores = defaultdict(dict)
    for (key, scene), rotations in groups.items():
        assert set(rotations) == {0, 1} and {pair[0] for pair in rotations.values()} == {1, 2}, name
        scores[key][scene] = mean(pair[1] for pair in rotations.values())
    assert all(len(value) == blocks for value in scores.values()), name
    output = dict(roles={key: scores[value] for key, value in aliases.items()},
                  scenario_maps={scene: name for scene, _, _, _, _ in first},
                  planned_games=len(plan['jobs']), actual_games=len(replies), missing=[], complete=True)
    assert output == read_json(folder/'summary.json'), name
    return output


def compare(panels, launch):
    seeds = sorted({seed for _, seed in launch['order']})
    options = launch['evaluation']

    def statistics(items):
        maps = {scene: board for panel in items for scene, board in panel['scenario_maps'].items()}
        assert len(maps) == sum(len(panel['scenario_maps']) for panel in items)
        def score(role_name):
            return {scene: value for panel in items for scene, value in panel['roles'][role_name].items()}
        return crossed_statistics({seed: score(f'lambda-0.95-{seed}') for seed in seeds},
                                  {seed: score(f'lambda-1.0-{seed}') for seed in seeds},
                                  score('bc'), maps, seed=options['bootstrap_seed'],
                                  samples=options['bootstrap_samples'])

    overall = statistics(list(panels.values()))
    return dict(status='observed', overall=overall,
                per_map={name: statistics([data]) for name, data in panels.items()},
                games={name: dict(planned=data['planned_games'], actual=data['actual_games'], missing=[])
                       for name, data in panels.items()},
                candidate=all(overall['interval95'][key][0] > 0 for key in ('b_minus_a', 'b_minus_bc')))


def score_means(panels, launch):
    seeds = sorted({seed for _, seed in launch['order']})
    by_map = {}
    for name, panel in panels.items():
        roles = {key: mean(scores.values()) for key, scores in panel['roles'].items()}
        by_map[name] = dict(bc=roles['bc'], **{
            f'lambda-{lam}': mean(roles[f'lambda-{lam}-{seed}'] for seed in seeds) for lam in (.95, 1.)})
    return dict(by_map, overall={key: mean(row[key] for row in by_map.values())
                                 for key in next(iter(by_map.values()))})


def archive(base, root, out):
    paths = list(root.glob('*.json')) + list(root.glob('*.log')) + list((root/'boards').glob('*.json'))
    for partition in ('validation', 'holdout'):
        paths.extend((root/partition).glob('*/plan.json'))
        paths.extend((root/partition).glob('*/results.jsonl'))
        paths.extend((root/partition).glob('*/summary.json'))
    for cell in (root/'cells').iterdir():
        paths.extend(cell.glob('*.json'))
        paths.append(cell/'scheduler.jsonl')
        paths.extend(cell/'duel'/name for name in ('jobs.jsonl', 'state.json'))
        paths.extend((cell/'duel/schedules').glob('*.json'))
    paths.extend(base/name for name in ('SOURCE_COMMIT', 'prepare.log', 'driver.log', 'driver.exit'))
    with tarfile.open(out, 'x:gz', compresslevel=6) as bundle:
        for path in sorted(set(paths)):
            bundle.add(path, arcname=path.relative_to(base), recursive=False)
    return dict(sha256=sha256(out), files=len(set(paths)), bytes=out.stat().st_size)


def main(base, output):
    root = base/'source/runs/ppo306'
    assert (base/'driver.exit').read_text().strip() == '0'
    launch = read_json(root/'launch.json')
    assert sha256(root/'launch.json') == '5ac6d19cab756ce8dade4c739c5f2127e86bb9ea34cec033934625fbd03bf02c'
    source = launch['source']
    assert ROOT == base/'source' and (base/'SOURCE_COMMIT').read_text().strip() == source['commit']
    assert sha256(source['archive']) == source['archive_sha256']
    assert sha256(source['extension']) == source['extension_sha256']
    assert sha256(Path(launch['rules']['path'])/'rules.json') == launch['rules']['sha256']
    assert sha256(launch['astra']['path']) == launch['astra']['teacher_parent_sha256']
    assert launch['disk']['free_bytes'] >= launch['disk']['minimum_bytes']

    endpoints = read_json(root/'endpoints.json')
    assert role(Path(endpoints['bc']['path'])) == endpoints['bc']
    assert endpoints['bc']['checkpoint_sha256'] == launch['endpoint']['checkpoint_sha256']
    cells, streams = {}, {}
    labels = [f'lambda-{lam}-{seed}' for lam, seed in launch['order']]
    assert len(set(labels)) == len(labels) == 6 and len(endpoints) == 7
    holdout = {record['board_sha256'] for record in launch['holdout'].values()}
    exposed = {record['board_sha256'] for record in launch['training_and_prior_boards'].values()}
    for record in (launch['initializer'], launch['endpoint']):
        exposed.update(board for boards in record['exposure']['boards'].values() for board in boards)
    assert len(holdout) == 2 and not holdout & exposed
    for name, (lam, seed) in zip(labels, launch['order']):
        cells[name], streams[lam, seed], actual_boards = check_cell(root, name, lam, seed, launch, endpoints[name])
        assert not actual_boards & holdout, name

    pairs = {}
    for seed in sorted({seed for _, seed in launch['order']}):
        a, b = streams[.95, seed], streams[1., seed]
        shared = min(len(a), len(b))
        assert a[:shared] == b[:shared], seed
        pairs[str(seed)] = dict(paired_games=shared, baseline_games=len(a), terminal_return_games=len(b))
    assert pairs == read_json(root/'training-pairs.json')

    budgets = launch['seconds']
    phases = [read_json(root/f'{name}-exit.json') for name in labels+['validation', 'holdout', 'report']]
    start = read_json(root/'run-start.json')
    assert start['deadline'] == launch['hard_deadline'] == launch['preparation_started']+budgets['total']
    assert launch['preparation_started'] <= launch['prepared'] <= start['started'] <= phases[0]['started']
    assert all(a['finished'] <= b['started'] for a, b in zip(phases, phases[1:]))
    actual = dict(preparation=start['started']-launch['preparation_started'],
                  ppo=sum(row['wall_seconds'] for row in phases[:6]),
                  total=phases[-1]['finished']-launch['preparation_started'])
    for name, stage in zip(('validation', 'holdout', 'report'), phases[6:]):
        assert stage['exit_code'] == 0 and not stage['timed_out']
        assert stage['finished'] <= stage['deadline'] <= start['deadline']
        actual[name] = stage['finished']-stage['started']
        assert actual[name] == stage['wall_seconds']
    actual['report'] += read_json(root/'settlement-accounting.json')['report_seconds']
    assert all(0 < elapsed <= budgets[name] for name, elapsed in actual.items())
    actual['unassigned'] = actual['total'] - sum(elapsed for name, elapsed in actual.items() if name != 'total')

    validation = {'hamlets': score_panel(root/'validation/hamlets', 'hamlets',
                                         launch['evaluation']['validation_blocks'], endpoints,
                                         launch['training_and_prior_boards']['hamlets'])}
    held_out = {name: score_panel(root/'holdout'/name, name, launch['evaluation']['holdout_blocks_per_map'],
                                  endpoints, board) for name, board in launch['holdout'].items()}
    assert validation == read_json(root/'validation-result.json')
    assert held_out == read_json(root/'holdout-result.json')
    report = compare(held_out, launch) | dict(validation=compare(validation, launch))
    assert report == read_json(root/'report-result.json')

    record = archive(base, root, output/'raw-metadata.tar.gz')
    write_new(output/'audit.json', dict(source=source, started=start['started'], finished=phases[-1]['finished'],
              budgets=budgets, actual_seconds=actual, cells=cells, training_pairs=pairs, report=report,
              normalized_scores=score_means(held_out, launch), archive=record))
    print(json.dumps(dict(actual_seconds=actual, games=report['games'], overall=report['overall'],
                          candidate=report['candidate'], archive=record), indent=2))


if __name__ == '__main__':
    main(*(Path(value).resolve() for value in sys.argv[1:]))
