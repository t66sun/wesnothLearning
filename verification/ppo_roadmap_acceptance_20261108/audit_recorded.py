"""Reconcile the completed #269 experiment from its recorded metadata only."""
from collections import defaultdict
from hashlib import sha256
from itertools import accumulate
import json
from math import ceil
from pathlib import Path
from statistics import mean
import sys

from verification.duel_ppo_comparison_20261106.audit import board_digest
from verification.ppo_batch_comparison_20261107 import panels


INPUTS = panels.INPUTS
CONTRACTS = ('base', 'b', 'c')
TASK = INPUTS['task_id']
HOLDOUT = INPUTS['holdout']['board_sha256']


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def job_rows(path, phase):
    with path.open(encoding='utf-8') as stream:
        rows = [json.loads(line) for line in stream]
    selected = [row for row in rows if row['meta'].get('phase') == phase]
    indexed = {row['id']: row for row in selected}
    assert len(indexed) == len(selected), path
    return indexed


def terminal(row):
    result = row['result']
    return (row['status'] == 'complete' and not result['faults']
            and result['task_id'] == TASK and result['task_terminal'])


def qualify(path, endpoint):
    manifest, branch = (read(path/name) for name in ('manifest.json', 'branch.json'))
    gate = read(path/'duel/bc_gate.json')
    teacher = job_rows(path/'duel/jobs.jsonl', 'teacher')
    assert gate['passed'] and digest(path/'duel/bc_gate.json') == endpoint['gate_sha256'], path
    assert digest(path/'manifest.json') == endpoint['manifest_sha256'], path
    assert manifest['teacher'] == INPUTS['astra'] and manifest['task_id'] == TASK, path
    assert manifest['rules']['rules_sha256'] == INPUTS['rules_sha256'], path
    assert manifest['config']['seed'] == INPUTS['bc_seed'] and branch['weights_only'], path
    assert branch['checkpoints']['duel']['sha256'] == INPUTS['actor_initializer_sha256'], path
    assert len(teacher) == INPUTS['bc_games'] and all(
        terminal(row) and row['training_eligible'] for row in teacher.values()), path
    exposure = endpoint['exposure']
    assert exposure['matched'] == exposure['shards'] and not exposure['holdout_overlap'], path
    assert all(HOLDOUT not in hashes for hashes in exposure['boards'].values()), path
    return {'teacher_games': len(teacher), 'weights_sha256': endpoint['weights_sha256'],
            'exposure': exposure, 'coverage': gate['coverage']['actions']['all']}


def cell_record(root, cell, endpoint, common_config):
    name = cell['name']
    duel = root/'duel'
    budget, branch, init, manifest = (
        read(root/file) for file in ('budget.json', 'branch.json', 'initialization.json', 'manifest.json'))
    state = read(duel/'state.json')
    config = manifest['config'].copy()
    size = config.pop('rollout_games')
    assert size == (8 if cell['route'] == 'a' else 4) and config.pop('seed') == cell['seed'], name
    config.pop('hours')
    assert config == common_config, name
    assert manifest['teacher'] == INPUTS['astra'] and manifest['task_id'] == TASK, name
    assert manifest['rules']['rules_sha256'] == INPUTS['rules_sha256'], name
    assert manifest['rehearsal_policy']['ppo'] == 'exclude_evaluation_control', name
    assert branch['reset_optimizer'] and init['optimizer_states'] == 0, name
    assert init['weights_sha256'] == endpoint['weights_sha256'], name
    assert branch['checkpoints']['duel']['bc_endpoint']['sha256'] == endpoint['checkpoint_sha256'], name

    ledger = cell['ledger']
    history = ledger['history']
    assert state['history'][budget['history_start']:] == history and history, name
    assert not (state['pending_train'] or state['pending_validation'] or state.get('error')), name
    assert budget['hard_deadline'] - budget['admission_deadline'] == 300, name
    raw = job_rows(duel/'jobs.jsonl', 'ppo')
    stream, used, boards = [], set(), set()
    last_weights = init['weights_sha256']
    for entry in history:
        batch = entry['batch']
        schedule = duel/'schedules'/f'ppo-batch-{batch:06}.json'
        jobs = read(schedule)
        assert len(jobs) == size and len({j['meta']['version'] for j in jobs}) == 1, schedule
        assert entry['method'] == 'ppo' and entry['ppo_aux_target'] == 'historical_action', schedule
        assert entry['policy_sha256_before'] == last_weights, schedule
        last_weights = entry['policy_sha256_after']
        fresh = 0
        for job in jobs:
            row = raw[job['id']]
            meta = job['meta']
            assert job['id'] not in used and row['meta'] == meta and terminal(row), schedule
            assert row['training_eligible'] and job['max_turns'] == 30, schedule
            assert meta['teacher_source_sha256'] == INPUTS['astra']['teacher_source_sha256'], schedule
            used.add(job['id'])
            fresh += row['training_shard']['written']
            boards.add(board_digest(job['map_override']))
            seat = meta['seat']
            stream.append((job['training_scenario']['index'], job['scenario_family'], job['game_family'],
                           job['seed'], seat, job['factions'], job['learning']['sides'][str(seat)]['sampling_seed']))
        assert fresh == entry['planned_targets'], schedule
    assert used == raw.keys() and len(stream) == ledger['policy_games'], name
    assert HOLDOUT not in boards, name
    assert [row[0] for row in stream] == list(range(len(stream))), name
    assert sum(row['committed_decisions'] for row in history) == ledger['committed_decisions'], name
    assert sum(row['inspected_decisions'] - row['committed_decisions'] for row in history) == ledger['rejected_decision_visits'], name
    assert not ledger['unsettled_history_entries'] and not ledger['unsettled_eligible_decisions'], name

    starts, updates = {}, {}
    for timing in (duel/'times').glob('*.json'):
        if timing.name.startswith('ppo-batch-'):
            _, _, batch, epoch = timing.stem.split('-')
            assert int(batch) not in starts, timing
            starts[int(batch)] = int(epoch)/1e9 - read(timing)['wall_seconds']
        elif timing.name.startswith('update-'):
            batch = int(timing.stem.split('-')[1])
            assert batch not in updates, timing
            record = read(timing)
            assert record['settled'], timing
            updates[batch] = record['finished_at']
    assert set(starts) == set(updates) == {row['batch'] for row in history}, name
    assert max(starts.values()) < budget['admission_deadline'], name
    assert max(updates.values()) <= budget['hard_deadline'], name

    cumulative = list(accumulate(row['planned_targets'] for row in history))
    assert cumulative[-1] == ledger['fresh_targets'] == ledger['sampled_eligible_decisions'], name
    for threshold in INPUTS['fresh_endpoints'] + [None]:
        index = next(i for i, value in enumerate(cumulative) if value >= threshold) if threshold else len(history)-1
        role = cell['roles'][str(threshold) if threshold else 'wall']
        entry = history[index]
        assert (role['fresh_targets'], role['settled_batches'], role['batch'], role['weights_sha256']) == (
            cumulative[index], index+1, entry['batch'], entry['policy_sha256_after']), name
    result = dict(games=len(stream), fresh=cumulative[-1], batches=len(history),
                  tail_updates=sum(finish > budget['admission_deadline'] for finish in updates.values()),
                  last_finish_slack_seconds=budget['hard_deadline']-max(updates.values()),
                  board_sha256=sorted(boards), stage_seconds=cell['stage']['wall_seconds'])
    return result, stream


def panel_record(root, label, expected, board_file_sha):
    plan, results, summary = (read(root/file) for file in ('plan.json', 'results.json', 'summary.json'))
    jobs, aliases = plan['jobs'], plan['aliases']
    assert aliases == expected, label
    by_id = {row['id']: row for row in results}
    assert len(jobs) == len(results) == len(by_id) == len({job['id'] for job in jobs}), label
    assert set(by_id) == {job['id'] for job in jobs} and all(map(terminal, results)), label
    holdout = plan['partition'] == 'holdout'
    grouped, timing = defaultdict(dict), defaultdict(list)
    for job in jobs:
        row, meta = by_id[job['id']], job['meta']
        side, = meta['policy_sides']
        rot, key, scene = meta['rotation'], meta['weights_sha256'], job['scenario_family']
        assert side == rot+1 and meta['control_sides'] == [3-side], label
        assert row['meta'] == meta and row['result']['factions'] == job['factions'], label
        assert row['result']['bots'] == job['bots'] and job['max_turns'] == 30, label
        assert meta['rules_sha256'] == INPUTS['rules_sha256'], label
        if holdout:
            assert meta['map_sha256'] == board_file_sha and board_digest(job['map_override']) == HOLDOUT, label
            ns = row['learner_decision_ns']
            assert ns and all(value > 0 for value in ns), label
            timing[key].extend(ns)
        winner = row['result']['winner']
        assert winner in (0, 1, 2) and (scene, rot) not in grouped[key], label
        grouped[key][scene, rot] = (
            meta['block'], job['seed'], side, meta['map'], tuple(job['factions']),
            1/3 if winner == 0 else float(winner == side))
    assert grouped.keys() == set(aliases.values()), label
    assert len(results) == summary['planned_games'] == summary['actual_games'], label
    for view in ('full',) if holdout else ('full', 'small'):
        blocks = 30 if holdout else (15 if view == 'full' else INPUTS['small_validation_blocks'])
        names = [name for name in aliases if name.endswith('/bc') or (name.endswith('/10000') == (view == 'small'))]
        reference, scores = None, {}
        for key in {aliases[name] for name in names}:
            rows = {k: v for k, v in grouped[key].items() if v[0] < blocks}
            design = {k: v[:-1] for k, v in rows.items()}
            if reference is None:
                reference = design
            assert len(rows) == 2*blocks and design == reference, label
            scores[key] = {scene: mean((row[-1], rows[scene, 1][-1]))
                           for (scene, rot), row in rows.items() if rot == 0}
        stored = summary[view]
        assert stored['complete'] and not stored['missing'], label
        assert stored['roles'] == {name: scores[aliases[name]] for name in names}, label
        assert stored['design'] == [list(item) for item in sorted(
            (scene, row[1], rot, [row[2]]) for (scene, rot), row in reference.items())], label
        assert stored['scenario_maps'] == {scene: row[3] for (scene, _), row in reference.items()}, label
        if holdout:
            pairs = {row[4] for (scene, rot), row in reference.items() if rot == 0}
            assert len(pairs) == 30 and all(left != right and (right, left) in pairs for left, right in pairs), label
    if holdout:
        stats = {key: dict(count=len(ns), p95_ms=sorted(ns)[ceil(.95*len(ns))-1]/1_000_000)
                 for key, ns in timing.items()}
        assert summary['learner_decision_timing'] == dict(weights=stats, aliases=aliases), label
    return summary


def audit(root):
    exp = root/'experiment'
    manifest = read(root/'launch-manifest.json')
    launch = read(exp/'launch.json')
    cells = read(exp/'cells.json')
    official = read(exp/'result.json')
    seconds = manifest['seconds']
    assert (root/'driver.exit').read_text().strip() == '0'
    assert official['status'] == 'observed' and not official['bc_shortfalls']
    assert launch['launch'] == manifest and launch['source_manifest_sha256'] == digest(root/'launch-manifest.json')
    source = root/'driver/source/verification/ppo_batch_comparison_20261107'
    assert launch['inputs_sha256'] == digest(source/'inputs.json') and read(source/'inputs.json') == INPUTS
    assert launch['protocol_sha256'] == digest(source/'PROTOCOL.md')
    assert (root/'driver/SOURCE_COMMIT').read_text().strip() == manifest['evidence_commit']
    assert launch['hard_deadline']-launch['started'] == seconds['total']
    assert official['wall_seconds'] <= seconds['total']
    assert manifest['preparation_wall_seconds'] <= manifest['preparation_ceiling_seconds']
    assert seconds['total'] + manifest['preparation_ceiling_seconds'] == manifest['execution_ceiling_seconds_including_preparation']
    assert [[cell['route'], cell['seed']] for cell in cells] == INPUTS['cell_order']

    records, endpoints, stages = {}, {}, {}
    original = Path(manifest['contracts']['base']['source']).parents[1]
    stage_names = [f'preflight-{key}' for key in CONTRACTS] + ['bc-b', 'bc-c'] + [cell['name'] for cell in cells]
    stage_names += [f'{part}-{key}' for part in ('validation', 'holdout', 'mc') for key in CONTRACTS]
    previous = launch['started']
    for name in stage_names:
        process, outcome = (read(exp/f'{name}-{suffix}.json') for suffix in ('process', 'exit'))
        assert outcome['exit_code'] == 0 and not outcome['timed_out'], name
        assert previous <= process['started'] == outcome['started'] <= outcome['finished'] <= process['deadline'], name
        assert process['deadline'] <= official['hard_deadline']-seconds['native'], name
        previous = outcome['finished']
        stages[name] = outcome['wall_seconds']
    for key in CONTRACTS:
        contract = manifest['contracts'][key]
        actual = read(exp/f'preflight-{key}-result')['result']
        assert actual['teacher'] == INPUTS['astra'], key
        # The worker resolves the extension symlink before recording its path.
        assert all(actual[field] == contract[field] for field in ('commit', 'source', 'extension_sha256')), key
        assert (root/key/'SOURCE_COMMIT').read_text().strip() == contract['commit'], key
        bc = actual['bc'] if key == 'base' else read(exp/f'bc-{key}-qualification.json')
        endpoints[key] = endpoint = bc['endpoint']
        if key == 'base':
            assert all(endpoint[k] == v for k, v in INPUTS['base_bc'].items())
            parent = root/'external/base-bc' if (root/'external/base-bc').exists() else Path(manifest['base_bc_parent'])
        else:
            assert bc['status'] == 'qualified' and stages[f'bc-{key}'] <= INPUTS['seconds']['bc_per_contract'], key
            parent = root/Path(bc['parent']).relative_to(original)
        records[key] = qualify(parent, endpoint)

    config = read(root/Path(cells[0]['run']).relative_to(original)/'manifest.json')['config']
    assert config['workers'] == INPUTS['workers'] and config['trainer_threads'] == INPUTS['trainer_threads']
    assert config['ppo_aux_target'] == 'historical_action' and config['reward_mode'] == 'fixed'
    for key in ('rollout_games', 'hours', 'seed'):
        del config[key]
    ledgers, streams = {}, {}
    for cell in cells:
        name = cell['name']
        assert cell == read(exp/f'{name}-ledger.json'), name
        path = root/Path(cell['run']).relative_to(original)
        request, budget = read(exp/f'{name}-request.json'), read(path/'budget.json')
        assert request['contract'] == manifest['contracts'][cell['contract']], name
        assert request['admission'] == budget['admission_deadline'] and request['deadline'] == budget['hard_deadline'], name
        assert stages[name] <= INPUTS['seconds']['ppo_hard'], name
        ledgers[name], streams[name] = cell_record(path, cell, endpoints[cell['contract']], config)
        if cell['route'] == 'a':
            first = read(exp/f"first-online-a8-{cell['seed']}.json")
            first_batch = path/'duel/schedules'/f"ppo-batch-{budget['first_batch']:06}.json"
            assert first == cell['ledger']['first_online_batch'] and first['schedule_sha256'] == digest(first_batch), name
    paired_ordinals = {}
    for seed in INPUTS['seeds']:
        base = streams[f'base-{seed}']
        for route in panels.ROUTES:
            other = streams[f'{route}-{seed}']
            count = min(len(base), len(other))
            assert base[:count] == other[:count], (seed, route)
            paired_ordinals[f'{route}-{seed}'] = count

    board_path = exp/'frozen/silverhead_crossing.json'
    board = read(board_path)
    assert board['source_sha256'] == INPUTS['holdout']['source_sha256'] and board_digest(board['board']) == HOLDOUT
    panels_seen = {}
    for partition in ('validation', 'holdout'):
        reports = {}
        for key in CONTRACTS:
            label = f'{partition}-{key}'
            path = exp/f'{label}-result'
            expected = {f'{key}/bc': endpoints[key]['weights_sha256']}
            for cell in (cell for cell in cells if cell['contract'] == key):
                for role, record in cell['roles'].items():
                    if partition == 'validation' or role == 'wall':
                        expected[f"{cell['name']}/{role}"] = record['weights_sha256']
                if partition == 'validation':
                    selected = read(path/'plan.json')['roles'][f"{cell['name']}/selected"]
                    assert selected['version'] <= cell['roles']['wall']['version']
                    expected[f"{cell['name']}/selected"] = selected['weights_sha256']
            reports[key] = panel_record(path, label, expected, digest(board_path))
        score = panels.summarize(reports.values(), partition)
        if partition == 'holdout':
            score['learner_decision_timing'] = {key: row['learner_decision_timing'] for key, row in reports.items()}
        # JSON roundtrip makes the bootstrap's training-seed keys comparable to the records.
        assert json.loads(json.dumps(score)) == read(exp/f'{partition}.json') == official[partition], partition
        panels_seen[partition] = {key: row['actual_games'] for key, row in reports.items()}
    nomination = read(exp/'deployment.json')
    assert nomination['route'] == panels.deployment_choice(official['validation']) == official['deployment_candidate']
    assert nomination['frozen_before_holdout'] and nomination['validation_sha256'] == digest(exp/'validation.json')
    assert (exp/'deployment.json').stat().st_mtime <= read(exp/'holdout-base-process.json')['started']
    return dict(launch_sha256=launch['source_manifest_sha256'], driver_seconds=official['wall_seconds'],
                prep_seconds=manifest['preparation_wall_seconds'], stage_seconds=stages, ppo=ledgers,
                common_stream_games=paired_ordinals, bc=records, games=panels_seen,
                deployment_candidate=nomination['route'])


if __name__ == '__main__':
    result = audit(Path(sys.argv[1]).resolve())
    with Path(sys.argv[2]).open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
