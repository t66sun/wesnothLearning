"""Attribute the costs around frozen #306 games and PPO batches."""
from collections import defaultdict
from contextlib import ExitStack
from copy import deepcopy
from hashlib import sha256
import gzip
import json
from pathlib import Path
import sys
from time import time
from unittest.mock import patch

import torch

from learning import common, data, features, lite_host, lite_policy, rules_catalog, sequences, updates
from learning.experiment import FormatExperiment, read_log
from learning.export import load_model
from learning.sample import play_job
from learning.schedule import compose_training_scenario

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ppo_rehearsal_cost_20261110'))
from measure_rehearsal import Timings, measure, read


def timed(stack, timer, label, owner, name):
    function = getattr(owner, name)

    def invoke(*args, **kwargs):
        return timer.call(label, function, *args, **kwargs)

    stack.enter_context(patch.object(owner, name, invoke))


def trainer(cell, config, history, state, output):
    model, _ = load_model(cell / 'duel/last_bc.pt', 'duel')
    samples = []
    for item in (history[0], history[len(history) // 2], history[-1]):
        timer = Timings()
        with ExitStack() as stack:
            for owner, label in ((data, 'data'), (updates, 'prepare')):
                timed(stack, timer, f'{label}_validation', owner, 'validate_record')
            timed(stack, timer, 'unpack', sequences, 'unpack_line')
            sample = measure(model, cell, state, config, item)
        sample['details'] = dict(timer.values)
        sample.pop('targets')
        sample.pop('prefixes')
        sample.pop('families')
        samples.append(sample)
        print('PREPARATION', item['batch'], json.dumps(sample['details']), flush=True)

    timer = Timings()
    replica = FormatExperiment.__new__(FormatExperiment)
    replica.directory = output / 'exports'
    replica.identity = lambda: config['control_identity']
    for _ in range(3):
        index = str(_)
        timer.call('fresh_sample_export', replica.ensure_export, model, 'sample-' + index, 'Sample',
                   mode='sample', version='v38')
        timer.call('fresh_greedy_export', replica.ensure_export, model, 'greedy-' + index, 'Greedy',
                   version='v38')
        timer.call('resumed_export_check', replica.ensure_export, model, 'sample-' + index, 'Sample',
                   mode='sample', version='v38')
    checkpoint = torch.load(cell / 'duel/wall.pt', map_location='cpu', weights_only=False)
    for i in range(3):
        timer.call('write_checkpoint_payload', torch.save, checkpoint, output / f'checkpoint-{i}.pt')
        timer.call('write_checkpoint_state', common.write_json, output / 'state.json', state)
        timer.call('read_job_log', read_log, cell / 'duel/jobs.jsonl')
    del checkpoint
    for item in (history[0], history[len(history) // 2], history[-1]):
        for job in read(cell / f"duel/schedules/ppo-batch-{item['batch']:06}.json"):
            timer.call('compose_training_scenario', compose_training_scenario, deepcopy(job),
                       max_turns=job['max_turns'])
    return dict(preparation=samples, boundary=dict(timer.values))


def shard_digest(path):
    digest = sha256()
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            metadata = row['m'] if row.get('v') == 2 else row
            if 'timing' in metadata:
                metadata['timing'].pop('ms', None)
            digest.update(json.dumps(row, sort_keys=True, separators=(',', ':')).encode() + b'\n')
    return digest.hexdigest()


def game(job, expected, output):
    work = output / job['id']
    work.mkdir()
    original_shard = Path(job['shard'])
    job = dict(job, output=str(work / Path(job['output']).name),
               shard=str(work / original_shard.name), deadline=time() + 180)
    timer = Timings()
    with ExitStack() as stack:
        for label, owner, name in (
            ('worker_host', lite_host.LiteHost, '__init__'),
            ('worker_rules_catalog', rules_catalog, 'load'),
            ('worker_rules_provenance', rules_catalog, 'provenance'),
            ('worker_lua_modules', lite_host, 'host_modules'),
            ('worker_policy_load', lite_policy.FrozenPolicies, '__init__'),
            ('worker_policy_sha', common, 'sha256'),
            ('worker_schema_rules', features, '_rules_sha256'),
            ('worker_decision', lite_host.LiteHost, 'decision'),
            ('worker_execution', lite_host.LiteHost, 'execute'),
            ('worker_policy_inference', lite_policy.FrozenPolicies, 'choose'),
            ('worker_buffer_append', lite_host.TrajectoryBuffer, 'append'),
            ('worker_shard_settlement', data, 'write_shard'),
            ('worker_sequence_index', sequences.IndexedSequenceStore, 'write'),
            ('worker_pack_line', data, 'pack_line'),
        ):
            timed(stack, timer, label, owner, name)
        result = timer.call('worker_total', play_job, job)
    assert result['status'] == expected['status'] == 'complete', result
    for key in ('result', 'coverage', 'training_eligible', 'training_shard'):
        assert result[key] == expected[key], (job['id'], key)
    hashes = {}
    for name in (original_shard.name, original_shard.name.replace('.jsonl.gz', '.dagger.jsonl.gz')):
        want = shard_digest(original_shard.parent / name)
        got = shard_digest(work / name)
        assert want == got, (job['id'], name, want, got)
        hashes[name] = want
    result = dict(id=job['id'], timings=dict(timer.values), shards=hashes)
    print('WORKER', job['id'], json.dumps(result['timings']), flush=True)
    return result


def history_clock(cell, history):
    spans = defaultdict(dict)
    for row in map(json.loads, (cell / 'scheduler.jsonl').read_text().splitlines()):
        spans[row['id']][row['event']] = row['time']
    collection = 0.0
    covered = 0
    for row in history:
        schedule = read(cell / f"duel/schedules/ppo-batch-{row['batch']:06}.json")
        entries = [spans[job['id']] for job in schedule]
        assert len(entries) == 8 and all({'start', 'finish'} <= entry.keys() for entry in entries)
        collection += max(entry['finish'] for entry in entries) - min(entry['start'] for entry in entries)
        covered += len(entries)
    return dict(recorded_wall=history[-1]['elapsed_hours'] * 3600,
                collection_wall=collection, batches=len(history), jobs=covered)


def sequence_rows(path, job_id):
    import sqlite3
    import zlib
    with sqlite3.connect(f'{path.as_uri()}?mode=ro', uri=True) as store:
        rows = store.execute('SELECT * FROM sequences WHERE game_id=? ORDER BY id', (job_id,))
        checked = []
        for row in rows:
            payload = json.loads(zlib.decompress(row[-1]))
            for record in payload:
                if 'timing' in record:
                    record['timing'].pop('ms', None)
            digest = sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
            checked.append((row[:-1], digest, len(row[-1])))
        return checked


def worker_cuts(root, output):
    from types import SimpleNamespace
    import zlib
    from learning import trajectory_buffer

    cell = root / 'cells/lambda-0.95-202611081'
    job = read(cell / 'duel/schedules/ppo-batch-000038.json')[1]
    expected = {row['id']: row for row in read_log(cell / 'duel/jobs.jsonl')}[job['id']]
    original_index = Path(job['shard']).parent / 'sequences/sequences.sqlite3'
    pinned = sequence_rows(original_index, job['id'])
    assert pinned
    records = {}
    for name in ('baseline', 'spool', 'index'):
        directory = output / name
        directory.mkdir()
        with ExitStack() as stack:
            if name == 'spool':
                stack.enter_context(patch.object(trajectory_buffer, 'zlib', SimpleNamespace(
                    compress=lambda data, **_: data, decompress=lambda data: data)))
            if name == 'index':
                stack.enter_context(patch.object(sequences, 'zlib', SimpleNamespace(
                    compressobj=lambda: zlib.compressobj(1), decompress=zlib.decompress)))
            result = game(job, expected, directory)
        db = directory / job['id'] / 'sequences/sequences.sqlite3'
        rows = sequence_rows(db, job['id'])
        assert [row[:2] for row in rows] == [row[:2] for row in pinned]
        result['index_payload_bytes'] = sum(row[2] for row in rows)
        records[name] = result
    (output / 'worker-cuts.json').write_text(json.dumps(records, indent=2) + '\n')



def main():
    root, output = map(Path, sys.argv[1:3])
    output.mkdir()
    if sys.argv[3:] == ['worker-cuts']:
        return worker_cuts(root, output)
    cells = root / 'cells'
    cell = cells / 'lambda-0.95-202611081'
    manifest = read(cell / 'manifest.json')
    config = dict(manifest['config'], control_identity=manifest['teacher'])
    state = read(cell / 'duel/state.json')
    history = [entry for entry in state['history'] if entry['method'] == 'ppo']
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    records = trainer(cell, config, history, state, output)
    jobs = {row['id']: row for row in read_log(cell / 'duel/jobs.jsonl')}
    early = read(cell / f"duel/schedules/ppo-batch-{history[0]['batch']:06}.json")
    late = read(cell / f"duel/schedules/ppo-batch-{history[-1]['batch']:06}.json")
    records['worker'] = [game(job, jobs[job['id']], output) for job in (early[0], early[1], late[0])]
    records['recorded'] = {}
    for other in sorted(cells.glob('lambda-0.95-*')):
        past = read(other / 'duel/state.json')['history']
        records['recorded'][other.name] = history_clock(other, [row for row in past if row['method'] == 'ppo'])
    (output / 'result.json').write_text(json.dumps(records, indent=2) + '\n')
    print('DONE', output / 'result.json', flush=True)


if __name__ == '__main__':
    main()
