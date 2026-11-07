"""Summarize settled #227 PPO batches and select complete frozen cost inputs."""
from collections import Counter
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ppo_efficiency_20261106'))
from census import intervals, ledger, sha256, summary


def read(path):
    return json.loads(path.read_text())


def index_cell(root, cell):
    run = root / 'runs' / cell
    manifest_path = run / 'manifest.json'
    state_path = run / 'duel/state.json'
    jobs_path = run / 'duel/jobs.jsonl'
    scheduler_path = run / 'scheduler.jsonl'
    ledger_path = root / f'{cell}-ledger.json'
    manifest = read(manifest_path)
    state = read(state_path)
    saved = read(ledger_path)['ledger']
    jobs = {job['id']: job for job in map(json.loads, jobs_path.read_text().splitlines())}
    spans, _ = intervals(map(json.loads, scheduler_path.read_text().splitlines()))
    spans = {span['id']: span for span in spans}
    inputs = {str(path): sha256(path) for path in
              (manifest_path, state_path, jobs_path, scheduler_path, ledger_path)}
    counts = ledger(state['history'])
    histories = {h['batch']: h for h in saved['history']}
    scenes = Counter()
    maps = Counter()
    families = set()
    endpoints = []
    terminals = Counter()
    for row in counts:
        number = row['batch']
        history = histories[number]
        schedule_path = run / 'duel/schedules' / f'ppo-batch-{number:06}.json'
        schedule = read(schedule_path)
        inputs[str(schedule_path)] = sha256(schedule_path)
        decisions = 0
        for game in schedule:
            job = jobs[game['id']]
            result = job['result']
            assert job['status'] == 'complete' and job['training_eligible'] and not result['faults']
            assert result['task_terminal'] and not job.get('external_cut', False)
            assert game['shard'] in state['policy_shards']
            decisions += job['training_shard']['written']
            scenes[game['scenario_family']] += 1
            maps[game['meta']['map']] += 1
            families.add(game['game_family'])
            terminals[result['reason']] += 1
        assert len(schedule) == manifest['config']['rollout_games'] == row['unique_game_families']
        assert decisions == row['eligible_decisions']
        scheduled = [spans[game['id']] for game in schedule]
        cursor = history['cursor']
        row.update(
            games=len(schedule), distinct_scenarios=len({g['scenario_family'] for g in schedule}),
            committed_windows=history['committed_window_visits'],
            rejected_windows=min(4, row['windows'] - 4 * cursor['step']) if row['rejected_steps'] else 0,
            collection_seconds=max(s['end'] for s in scheduled) - min(s['start'] for s in scheduled),
            worker_seconds=sum(s['end'] - s['start'] for s in scheduled),
        )
        if number in (counts[0]['batch'], counts[-1]['batch']):
            endpoints.append(dict(cell=cell, history=history, games=schedule))
    totals = {key: sum(row[key] for row in counts) for key in (
        'games', 'eligible_decisions', 'windows', 'committed_windows', 'rejected_windows',
        'planned_steps', 'committed_steps', 'rejected_steps', 'never_attempted_steps',
        'inspected_decisions', 'committed_decisions', 'rejected_decisions')}
    assert totals['games'] == saved['policy_games'] == len(families)
    assert totals['eligible_decisions'] == saved['fresh_targets']
    assert totals['rejected_decisions'] == saved['rejected_decision_visits']
    exit_record = read(root / f'{cell}-exit.json')
    return dict(mode=manifest['config']['ppo_aux_target'], batches=len(counts),
                rules_sha256=manifest['rules']['rules_sha256'],
                opponent=manifest['opponents'][0], totals=totals, scenario_counts=dict(scenes),
                map_counts=dict(maps), terminal_counts=dict(terminals),
                batch_fresh_decisions=summary([r['eligible_decisions'] for r in counts]),
                batch_scenario_families=summary([r['distinct_scenarios'] for r in counts]),
                collection_seconds=summary([r['collection_seconds'] for r in counts]),
                worker_seconds=summary([r['worker_seconds'] for r in counts]),
                stage_seconds=exit_record['wall_seconds'], inputs=inputs), endpoints


def paired_sample(cells, endpoints, mc):
    first = endpoints['a1'][0]
    task = first['games'][0]['task_id']
    weights = first['history']['policy_sha256_before']
    opponent = cells['a1']['opponent']['sha256']
    # The independent #227 review already verified these semantic aliases.
    by_shard = {alias['shard']: (key, alias, trajectory['decisions'])
                for key, trajectory in mc['trajectories'].items()
                for alias in trajectory['aliases'] if alias['phase'] == 'first_ppo_bc_behavior'}
    cohort = {}
    for cell, (entry, _) in endpoints.items():
        if cells[cell]['opponent']['sha256'] != opponent:
            continue
        for game in entry['games']:
            identity, alias, decisions = by_shard[game['shard']]
            opponent_path = game['bots'][2 - game['meta']['seat']]
            if (game['task_id'] == task and alias['behavior_weights_sha256'] == weights
                    and entry['history']['policy_sha256_before'] == weights
                    and opponent_path == cells[cell]['opponent']['path']):
                cohort.setdefault(identity, dict(cell=cell, game=game, trajectory=identity,
                                                 decisions=decisions))
    candidates = list(cohort.values())
    pair = (dict(first, games=[row['game'] for row in candidates[:8]], pair=candidates[:8])
            if len(candidates) >= 8 else None)
    return dict(first_batch_references=len(by_shard), eligible_unique=len(candidates),
                pair=pair)


def main():
    root, output = map(Path, sys.argv[1:])
    cells, endpoints = {}, {}
    for cell in ('a1', 'b1', 'b2', 'a2', 'a3', 'b3'):
        cells[cell], endpoints[cell] = index_cell(root, cell)
    ce = [name for name, cell in cells.items() if cell['mode'] == 'historical_action']
    mc_path = root / 'mc-diagnostics.json'
    mc = read(mc_path)
    assert not mc['external_cuts'] and not mc['missing']
    pairing = paired_sample(cells, endpoints, mc)
    pairing['mc_index_sha256'] = sha256(mc_path)
    data = dict(run=str(root), launch=read(root / 'launch.json'), cells=cells,
                pairing=pairing, samples=dict(first=endpoints[ce[0]][0], last=endpoints[ce[-1]][1],
                                              paired8=pairing.pop('pair')))
    with output.open('x') as stream:
        json.dump(data, stream, indent=2)
        stream.write('\n')
    print(f"{sum(c['batches'] for c in cells.values())} settled batches, "
          f"{pairing['eligible_unique']} eligible shared-BC trajectories", flush=True)


if __name__ == '__main__':
    main()
