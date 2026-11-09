"""Profile the preparation of frozen #306 PPO batches without training."""
from collections import defaultdict
from hashlib import sha256
import json
from pathlib import Path
import resource
import sys
from time import perf_counter, process_time
from unittest.mock import patch

import torch

from learning import sequences
from learning.data import make_bc_sampler, read_shards
from learning.export import load_model
from learning.ppo import _digest
from learning.updates import eligible_rows, prepare, rollout_identity, setup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ppo_efficiency_20261106'))
from probe import Timings


def read(path):
    return json.loads(path.read_text())


def rollout_index(path):
    prefix, index, _ = Path(path).name.split('-', 2)
    assert prefix == 'rollout'
    return int(index)


def rehearsal_pool(cell, state, config, jobs):
    through = max(rollout_index(job['shard']) for job in jobs)
    own_data = cell / 'duel/data'

    def available(path):
        return Path(path).parent != own_data or rollout_index(path) <= through

    human = sorted(str(path) for path in (Path(config['human_data']) / 'duel').glob('*.jsonl.gz'))
    return ([path for path in state['teacher_shards'] + state['dagger_shards'] if available(path)]
            + human + [path for path in state['policy_shards'] if available(path)])


class FamilyTrace:
    def __init__(self):
        self.decoded = []
        self.original = sequences._family_windows
        self.instrumentation = Timings()

    def read(self, files, partition, format_name, turns):
        wall, cpu = perf_counter(), process_time()
        windows, prefix = self.original(files, partition, format_name, turns)
        elapsed, processor = perf_counter() - wall, process_time() - cpu
        with self.instrumentation.scope('estimate'):
            payload_bytes = prefix + sum(sequences._row_bytes(row) for window in windows for row in window)
            self.decoded.append(dict(paths=[str(path) for path, _ in files],
                                     seconds=elapsed, cpu_seconds=processor, payload_bytes=payload_bytes))
        return windows, prefix


def measure(model, cell, state, config, history):
    batch = history['batch']
    schedule = cell / f'duel/schedules/ppo-batch-{batch:06}.json'
    jobs = read(schedule)
    versions = {job['meta']['version'] for job in jobs}
    assert len(versions) == 1 and len(jobs) == 8
    version = int(versions.pop().removeprefix('v'))
    paths = [job['shard'] for job in jobs]
    pool = rehearsal_pool(cell, state, config, jobs)
    task = config['task_id']
    stats = {}
    timer = Timings()
    trace = FamilyTrace()
    rows = timer.call('rollout_read', read_shards, paths, format_name='duel', expected_task=task)
    with patch.object(sequences, '_family_windows', trace.read):
        bc = timer.call('rehearsal_read', read_shards, pool, partition='train', limit=config['bc_records'],
                        seed=config['seed'] + version, format_name='duel', stats=stats, expected_task=task)
    timer.call('eligibility', eligible_rows, rows)
    rollout = timer.call('rollout_identity', rollout_identity, rows)
    rehearsal = timer.call('rehearsal_identity', rollout_identity, bc)
    timer.call('prepare_validation', prepare, model, rows, bc)
    _, windows, _, _, _ = timer.call('window_setup', setup, model, rows, config['minibatch'])

    assert stats == history['reads']['bc'], (batch, stats, history['reads']['bc'])
    assert len(trace.decoded) == stats['families_decoded']
    assert len(rows) == history['eligible_decisions'] and len(windows) == history['sequence_windows']
    assert all(r['value_valid'] and r['source'] == 'policy' and r['version'] == f'v{version}'
               and not r.get('truncated') for r in rows)
    control = config['control_identity']
    sampler = make_bc_sampler(bc, allow_policy=True, exclude_teacher_impl=control['teacher'],
                              exclude_teacher_sha=control['teacher_source_sha256'])
    assert sampler.rows_excluded == history['rehearsal_rows_excluded']
    assert sampler.source_identities == history['rehearsal_sources']

    targets = []
    prefix_counts = defaultdict(int)
    for row in bc:
        sequence = sequences.sequence_key(row)
        prefix_counts[sequence] = max(prefix_counts[sequence], len(row['_history']))
        targets.append([*sequence, row['turn'], row.get('decision', row.get('action_index', 0))])
    return dict(batch=batch, version=version, stats=stats, timings=dict(timer.values),
                instrumentation=dict(trace.instrumentation.values), families=trace.decoded,
                targets=targets, prefixes=[[list(key), count] for key, count in prefix_counts.items()],
                rehearsal_sha256=rehearsal, rollout_sha256=rollout,
                schedule_sha256=sha256(schedule.read_bytes()).hexdigest(),
                peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def main():
    root, seed, output = sys.argv[1:]
    root = Path(root)
    cell = root / 'cells' / f'lambda-0.95-{seed}'
    manifest = read(cell / 'manifest.json')
    config = dict(manifest['config'], control_identity=manifest['teacher'])
    state = read(cell / 'duel/state.json')
    history = [entry for entry in state['history'] if entry['method'] == 'ppo']
    assert config['rollout_games'] == 8 and config['gae_lambda'] == 0.95
    assert config['ppo_aux_target'] == 'historical_action' and config['seed'] == int(seed)
    assert len(history) >= 24
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    model, _ = load_model(cell / 'duel/last_bc.pt', 'duel')
    weights = _digest(model)
    assert weights == history[0]['policy_sha256_before']
    middle = len(history) // 2
    segments = [('early', 0), ('middle', middle - 4), ('late', len(history) - 8)]
    with Path(output).open('x') as stream:
        for segment, first in segments:
            for index in range(first, first + 8):
                prior_hours = history[index - 1]['elapsed_hours'] if index else 0
                observed_seconds = (history[index]['elapsed_hours'] - prior_hours) * 3600
                assert observed_seconds > 0
                result = measure(model, cell, state, config, history[index])
                assert _digest(model) == weights
                result.update(seed=int(seed), segment=segment, recorded_wall_seconds=observed_seconds)
                stream.write(json.dumps(result, separators=(',', ':')) + '\n')
                stream.flush()
                print(seed, segment, result['batch'],
                      round(result['timings']['rehearsal_read']['wall_seconds'], 3),
                      round(result['timings']['rehearsal_identity']['wall_seconds'], 3), flush=True)


if __name__ == '__main__':
    main()
