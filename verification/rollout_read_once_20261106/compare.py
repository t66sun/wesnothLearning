"""Paired frozen-input preparation timing; no games, optimizer, or saves."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import sys
import time

import torch

from learning.data import read_shards
from learning.export import load_model
from learning.ppo import _digest, _target_key
from learning.updates import eligible_rows, prepare, rollout_identity, setup

# Reuse the timing and input-path definitions of the original frozen census.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ppo_efficiency_20261106'))
from probe import Timings, model_path
from census import sha256


def measured_prepare(model, paths, corpus, config, version, mode):
    timing = Timings()
    stats = {}
    with timing.scope('total_prepare'):
        if mode == 'legacy':
            preliminary = timing.call('discarded_preliminary_read', read_shards, paths,
                partition='train', limit=config['bc_records'], format_name=model.format_name)
            assert preliminary
            del preliminary
        else:
            rows = timing.call('full_rollout_read', read_shards, paths, format_name=model.format_name)
        bc = timing.call('rehearsal_read', read_shards, corpus, partition='train',
            limit=config['bc_records'], seed=config['seed'] + version,
            format_name=model.format_name, stats=stats)
        if mode == 'legacy':
            rows = timing.call('full_rollout_read', read_shards, paths, format_name=model.format_name)
        timing.call('eligibility', eligible_rows, rows)
        identity = dict(train=timing.call('rollout_identity', rollout_identity, rows),
                        bc=timing.call('rehearsal_identity', rollout_identity, bc))
        rows = timing.call('prepare_validation', prepare, model, rows, bc)
    _, windows, _, _, _ = setup(model, rows, config['minibatch'])
    return dict(mode=mode, timings=dict(timing.values), identity=identity, reads=stats,
                targets=[_target_key(row) for row in rows], windows=len(windows),
                raw_prefix_lengths=[len(row['_history']) for row in rows])


def inspect(run, fmt, history, state, config, repetitions):
    schedule = run / fmt / 'schedules' / f"ppo-batch-{history['batch']:06}.json"
    jobs = json.loads(schedule.read_text())
    policy = model_path(jobs[0])
    model, _ = load_model(policy, fmt)
    digest = _digest(model)
    assert digest == history['policy_sha256_before']
    version = int(jobs[0]['meta']['version'].removeprefix('v'))
    corpus = []
    for path in state['teacher_shards'] + state['dagger_shards'] + state['policy_shards']:
        batch = re.search(r'rollout-(\d+)-', Path(path).name)
        if batch is None or int(batch.group(1)) <= history['batch']:
            corpus.append(path)
    paths = [job['shard'] for job in jobs]
    measurements = []
    reference = None
    for repetition in range(repetitions):
        order = ('legacy', 'single_read') if repetition % 2 == 0 else ('single_read', 'legacy')
        for mode in order:
            print(fmt, history['batch'], repetition, mode, flush=True)
            result = measured_prepare(model, paths, corpus, config, version, mode)
            assert result['reads'] == history['reads']['bc']
            assert len(result['targets']) == history['eligible_decisions']
            assert result['windows'] == history['sequence_windows']
            matching = {key: result[key] for key in ('identity', 'targets', 'raw_prefix_lengths', 'reads', 'windows')}
            if reference is None:
                reference = matching
            else:
                assert matching == reference
            assert _digest(model) == digest
            result.update(repetition=repetition, target_count=len(result.pop('targets')),
                          raw_prefix_slots=sum(result.pop('raw_prefix_lengths')))
            measurements.append(result)
    corpus_identity = hashlib.sha256(json.dumps(corpus, separators=(',', ':')).encode()).hexdigest()
    return dict(format=fmt, batch=history['batch'], version=version,
                parameters_sha256=digest, corpus_paths=len(corpus), corpus_path_list_sha256=corpus_identity,
                inputs={str(path): sha256(Path(path)) for path in [schedule, policy, *paths]},
                exact_targets_prefixes_identities_read_statistics=True, measurements=measurements)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--repetitions', type=int, default=2)
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error('repetitions must be positive')
    if args.output.exists():
        parser.error('output must be a new evidence file')
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    config = json.loads((args.run / 'manifest.json').read_text())['config']
    result = dict(host=platform.node(), python=platform.python_version(), torch=torch.__version__,
        threads=torch.get_num_threads(), pid=os.getpid(), started_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        scope='Read/eligibility/content identities/prepare only; no optimizer, games, saves, or forward/backward. '
              'Paired order alternates; OS caches are not evicted. Metadata caches warm across calls.',
        run=str(args.run), manifest_sha256=sha256(args.run / 'manifest.json'), batches=[])
    for fmt in ('duel', 'team2v2'):
        state = json.loads((args.run / fmt / 'state.json').read_text())
        completed = [entry for entry in state['history'] if entry['method'] == 'ppo']
        for history in (completed[0], completed[len(completed) // 2], completed[-1]):
            result['batches'].append(inspect(args.run, fmt, history, state, config, args.repetitions))
            args.output.write_text(json.dumps(result, indent=2) + '\n')
    result['finished_utc'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
