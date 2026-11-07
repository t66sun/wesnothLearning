"""Time one frozen PPO case in a fresh, single-threaded Ubuntu process."""
import json
from pathlib import Path
import platform
import re
import resource
import sys

import torch

from learning.data import read_shards
from learning.export import load_model
from learning.ppo import _digest
from learning.sequences import sequence_key
from learning.updates import eligible_rows, prepare, rollout_identity, setup

from inventory import read
from probe import Timings, model_path, one_pass
from census import sha256, summary


def namespace_added_games(rows, added_cells):
    # Different runs reuse the same schedule IDs. GAE and PPO target IDs use
    # game_id and side, while raw histories were attached by sequence_key.
    for row in rows:
        if row['game_family'] in added_cells:
            row['game_id'] = row['game_id']  # removed: f"{added_cells[row['game_family']]}/{row['game_id']}"


def measure(model, sample, config, corpus, version):
    history = sample['history']
    games = sample['games']
    paths = [game['shard'] for game in games]
    task = config['task_id']
    stats = {}
    timing = Timings()
    with timing.scope('total_fixed_weight_batch'):
        with timing.scope('total_prepare'):
            rows = timing.call('full_rollout_read', read_shards, paths, format_name='duel', expected_task=task)
            if 'pair' in sample:
                added_cells = {ref['game']['game_family']: ref['cell'] for ref in sample['pair'][4:]}
                namespace_added_games(rows, added_cells)
            bc = timing.call('rehearsal_read', read_shards, corpus, partition='train',
                             limit=config['bc_records'], seed=config['seed'] + version,
                             format_name='duel', stats=stats, expected_task=task)
            timing.call('eligibility', eligible_rows, rows)
            identities = dict(rollout=timing.call('rollout_identity', rollout_identity, rows),
                              rehearsal=timing.call('rehearsal_identity', rollout_identity, bc))
            rows = timing.call('prepare_validation', prepare, model, rows, bc)
            _, windows, sequence_count, micro, _ = timing.call('window_setup', setup, model, rows,
                                                               config['minibatch'])
        work = timing.call('fixed_weight_pass', one_pass, model, rows, bc, windows, micro, sequence_count,
                           games[0]['reward_config'], 20261106, timing)
    assert stats == history['reads']['bc']
    assert work['rehearsal_identities'] == history['rehearsal_sources']
    assert work['excluded_rehearsal_rows'] == history['rehearsal_rows_excluded']
    assert len({sequence_key(r) for r in rows}) == len(games)
    assert all(r['value_valid'] and r['source'] == 'policy' and not r.get('truncated')
               and r['version'] == f'v{version}' for r in rows)
    if 'pair' in sample:
        assert len(rows) == sum(ref['decisions'] for ref in sample['pair'])
    else:
        assert len(rows) == history['eligible_decisions']
        assert len(windows) == history['sequence_windows']
    return dict(timings=dict(timing.values), reads=stats, identities=identities, work=work,
                fresh_decisions=len(rows), independent_games=len(games), windows=len(windows),
                windows_rows=summary([len(window) for window in windows]),
                raw_prefix_turns=summary([len(r['_history']) for r in rows]))


def main():
    inventory_path, case, output = sys.argv[1:]
    index = read(Path(inventory_path))
    sample = index['samples'][case]
    if sample is None:
        print('Paired case omitted because fewer than eight trajectories qualified.')
        return
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    run = Path(index['run']) / 'runs' / sample['cell']
    config = read(run / 'manifest.json')['config']
    state = read(run / 'duel/state.json')
    history = sample['history']
    games = sample['games']
    version = int(games[0]['meta']['version'].removeprefix('v'))
    assert config['ppo_aux_target'] == 'historical_action'
    assert all(g['reward_config'] == games[0]['reward_config'] for g in games)

    corpus = []
    human = sorted(str(p) for p in (Path(config['human_data']) / 'duel').glob('*.jsonl.gz'))
    for path in state['teacher_shards'] + state['dagger_shards'] + human + state['policy_shards']:
        batch = re.search(r'rollout-(\d+)-', Path(path).name)
        if batch is None or int(batch[1]) <= history['batch']:
            corpus.append(path)

    model, _ = load_model(model_path(games[0]), 'duel')
    weights = history['policy_sha256_before']
    assert _digest(model) == weights
    for policy in {model_path(game) for game in games} - {model_path(games[0])}:
        other, _ = load_model(policy, 'duel')
        assert _digest(other) == weights
        del other

    measurements = []
    for label in ('warmup', 'measure-1', 'measure-2'):
        result = measure(model, sample, config, corpus, version)
        assert _digest(model) == weights
        if measurements:
            assert result['identities'] == measurements[0]['identities']
        measurements.append(dict(label=label, **result))
        wall = result['timings']['total_fixed_weight_batch']['wall_seconds']
        print(f"{case} {label}: {wall:.3f}s", flush=True)

    data = dict(case=case, cell=sample['cell'], batch=history['batch'], version=version,
                python=platform.python_version(), torch=torch.__version__,
                threads=torch.get_num_threads(), peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                weights_sha256=weights, shards={g['shard']: sha256(g['shard']) for g in games},
                scenarios=len({g['scenario_family'] for g in games}), measurements=measurements)
    with Path(output).open('x') as stream:
        json.dump(data, stream, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
