"""Reconcile the frozen #312 budget, full paired work and endpoints."""
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time

import torch

from driver import digest, load, write
from learning.bc_anchor import weights_sha256


def json_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def object_digest(value):
    return hashlib.sha256(json_bytes(value)).hexdigest()


def normalized(value, root):
    if isinstance(value, dict):
        return {key: normalized(item, root) for key, item in value.items()}
    if isinstance(value, list):
        return [normalized(item, root) for item in value]
    if isinstance(value, str) and (value == root or value.startswith(root + '/')):
        return '$CELL' + value[len(root):]
    return value


def lines(path):
    with Path(path).open() as stream:
        return [json.loads(line) for line in stream]


def shard_identity(path):
    """Keep all row metadata and packed bytes except the measured Lua milliseconds."""
    identity = hashlib.sha256()
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            metadata = row['m'] if row.get('v') == 2 else row
            if 'timing' in metadata:
                metadata['timing'].pop('ms', None)
            identity.update(json_bytes(row) + b'\n')
    return identity.hexdigest()


def adam_identity(optimizer):
    identity = hashlib.sha256()
    identity.update(json_bytes(optimizer['param_groups']) + b'\n')
    for parameter, fields in sorted(optimizer['state'].items()):
        for name, value in sorted(fields.items()):
            if torch.is_tensor(value):
                descriptor = [parameter, name, str(value.dtype), list(value.shape),
                              hashlib.sha256(value.detach().cpu().numpy().tobytes()).hexdigest()]
            else:
                descriptor = [parameter, name, value]
            identity.update(json_bytes(descriptor) + b'\n')
    return identity.hexdigest()


def comparable_history(rows):
    comparable = []
    for row in rows:
        record = {key: value for key, value in row.items() if key not in ('elapsed_hours', 'peak_rss_mb')}
        record['reads'] = {role: {key: value for key, value in stats.items() if key != 'gz_bytes'}
                           for role, stats in row['reads'].items()}
        comparable.append(record)
    return comparable


def check_cell(stage, plan, start, arm, seed):
    label = f'{arm}-{seed}'
    record = load(stage / 'cells' / f'{label}-exit.json')
    settled = load(stage / 'cells' / f'{label}-settled.json')
    budget_limit = plan['budget_seconds']
    assert record['seed'] == seed and record['arm'] == arm
    assert not record['timed_out'] and record['exit_code'] == 0
    assert start['started'] <= record['started'] < record['finished'] <= record['deadline']
    assert record['deadline'] <= start['training_deadline']
    assert abs(record['finished'] - record['started'] - record['wall_seconds']) < 0.1
    assert 0 < record['deadline'] - record['started'] <= budget_limit['cell_hard']
    assert 0 < record['admission'] - record['started'] <= budget_limit['cell_admission']
    assert record['deadline'] - record['admission'] == budget_limit['cell_hard'] - budget_limit['cell_admission']
    assert settled['stage'] == 'ppo_complete' and settled['result']['status'] == 'stage_complete'

    root = Path(settled['root'])
    assert root == Path(plan['arms'][arm]['source']) / 'runs/ppo312' / str(seed)
    manifest = load(root / 'manifest.json')
    config = dict(manifest['config'])
    assert config.pop('seed') == seed and 0 < config.pop('hours') <= budget_limit['cell_hard'] / 3600
    assert config == plan['config']
    assert manifest['rules']['rules_sha256'] == plan['rules']['sha256']
    assert manifest['teacher'] == plan['arms'][arm]['teacher']
    assert [item['sha256'] for item in manifest['opponents']] == [plan['astra']['teacher_parent_sha256']]
    init = load(root / 'initialization.json')
    assert init['optimizer_states'] == 0 and init['weights_sha256'] == plan['endpoint']['weights_sha256']
    branch = load(root / 'branch.json')
    assert branch['reset_optimizer']
    assert branch['checkpoints']['duel']['bc_endpoint']['sha256'] == plan['endpoint']['checkpoint_sha256']

    duel = root / 'duel'
    budget = load(root / 'budget.json')
    assert budget['hard_deadline'] == record['deadline'] and budget['admission_deadline'] == record['admission']
    state = load(duel / 'state.json')
    assert state['stage'] == 'ppo_complete' and not state['error']
    assert state['pending_train'] is None and state['pending_validation'] is None
    target = plan['successful_batches_per_cell']
    assert state['phase_ppo_target'] == dict(batches=target, history_start=budget['history_start'])
    history = state['history'][budget['history_start']:]
    assert len(history) == settled['all_batches']
    assert all(row['method'] == 'ppo' and not row['interrupted'] for row in history)
    assert sum(row['committed_steps'] > 0 for row in history) == settled['positive_batches'] == target

    rows = lines(duel / 'jobs.jsonl')
    replies = {row['id']: row for row in rows}
    assert len(rows) == len(replies)
    scheduler = lines(root / 'scheduler.jsonl')
    submitted = {event['id']: event['time'] for event in scheduler if event['event'] == 'start'}
    finished = {event['id']: event['time'] for event in scheduler if event['event'] == 'finish'}
    assert set(submitted) == set(finished) == set(replies)
    assert len(scheduler) == 2 * len(replies)

    identities, games, trajectories = {}, {}, {}
    phases = dict(ppo=0.0, validation=0.0)
    counts = dict(ppo_games=0, validation_games=0, trajectories=0)
    due_versions = set()
    ordinal = 0

    def panel(path, phase):
        jobs = load(path)
        assert jobs
        keys = [job['id'] for job in jobs]
        assert len(keys) == len(set(keys))
        assert all(record['started'] <= submitted[key] <= finished[key] <= record['deadline'] for key in keys)
        if phase == 'ppo':
            assert min(submitted[key] for key in keys) < record['admission']
        phases[phase] += max(finished[key] for key in keys) - min(submitted[key] for key in keys)
        counts[f'{phase}_games'] += len(keys)
        for job in jobs:
            key = job['id']
            assert key not in identities
            reply = replies[key]
            assert reply['status'] == 'complete' and not reply['result']['faults']
            assert reply['result']['task_terminal'] and job['task_id'] == plan['endpoint']['task_id']
            assert job['max_turns'] == 30
            board = job['meta']['map']
            assert job['meta']['map_sha256'] == plan['arms'][arm]['maps'][board]
            identity = {name: value for name, value in job.items() if name != 'deadline'}
            identities[key] = object_digest(normalized(identity, str(root)))
            games[key] = object_digest(normalized(reply, str(root)))
        return jobs

    for offset, entry in enumerate(history):
        batch = budget['first_batch'] + offset
        assert entry['batch'] == batch
        jobs = panel(duel / f'schedules/ppo-batch-{batch:06}.json', 'ppo')
        assert len(jobs) == plan['config']['rollout_games']
        versions = {job['meta']['version'] for job in jobs}
        assert len(versions) == 1
        version = int(versions.pop().removeprefix('v'))
        if entry['committed_steps'] and (version + 1) % config['validation_interval'] == 0:
            due_versions.add(version + 1)
        assert sum(replies[job['id']]['training_shard']['written'] for job in jobs) == entry['planned_targets']
        for job in jobs:
            assert job['training_scenario']['index'] == ordinal
            ordinal += 1
            assert replies[job['id']]['training_eligible']
            seat = job['meta']['seat']
            assert job['bots'][2 - seat] == manifest['opponents'][0]['path']
            shard = Path(job['shard'])
            trajectory = [shard_identity(shard)]
            dagger = shard.with_name(shard.name.replace('.jsonl.gz', '.dagger.jsonl.gz'))
            if str(dagger) in state['dagger_shards']:
                trajectory.append(shard_identity(dagger))
            else:
                assert not dagger.exists()
            trajectories[job['id']] = trajectory
            counts['trajectories'] += len(trajectory)

    validation = {}
    schedules = duel / 'schedules'
    for path in sorted(schedules.glob('validation-*.json')) + sorted(schedules.glob('champion-*.json')):
        panel(path, 'validation')
        kind, version = path.stem.split('-')
        name = f'v{version}.json' if kind == 'validation' else f'champion-v{version}.json'
        validation[path.stem] = object_digest(normalized(load(duel / 'validation' / name), str(root)))
    assert due_versions == {int(name.split('-')[1]) for name in validation if name.startswith('validation-')}
    assert set(identities) == set(replies)

    checkpoint_path = duel / 'latest.pt'
    checkpoint = torch.load(checkpoint_path, map_location='cpu', weights_only=False)
    model = checkpoint['model']
    assert json.loads(json.dumps(checkpoint['runner'])) == state
    weights = weights_sha256(model)
    assert weights == history[-1]['policy_sha256_after']
    model_digest = dict(full=weights,
                        actor_and_shared=weights_sha256({k: v for k, v in model.items() if not k.startswith('value.')}),
                        critic_head=weights_sha256({k: v for k, v in model.items() if k.startswith('value.')}))
    rng = dict(python=object_digest(checkpoint['python_rng']),
               torch=hashlib.sha256(checkpoint['torch_rng'].cpu().numpy().tobytes()).hexdigest())
    totals = {key: sum(row[key] for row in history)
              for key in ('planned_targets', 'committed_steps', 'inspected_decisions', 'committed_decisions')}
    totals.update(counts, settled_batches=len(history), positive_batches=target,
                  kl_stops=sum(bool(row['kl_stopped']) for row in history))
    comparable = dict(schedules=identities, replies=games, trajectories=trajectories,
                      history=object_digest(comparable_history(history)), validation=validation,
                      model=model_digest, adam=adam_identity(checkpoint['optimizer']), rng=rng, work=totals)
    return dict(wall=record, worker_spans=phases, peak_rss_mib=max(row['peak_rss_mb'] for row in history),
                initialization=init, checkpoint_file_sha256=digest(checkpoint_path),
                comparable=comparable)


def compare(stage, plan):
    started = time.time()
    start = load(stage / 'run-start.json')
    end = load(stage / 'run-exit.json')
    assert digest(stage / 'launch.json') == start['launch_sha256']
    assert start['deadline'] == end['deadline'] == start['started'] + plan['budget_seconds']['total']
    assert start['training_deadline'] == start['deadline'] - plan['budget_seconds']['report']
    cells, errors = {}, {}
    for seed, arm in plan['order']:
        label = f'{arm}-{seed}'
        try:
            cells[label] = check_cell(stage, plan, start, arm, seed)
        except Exception as exc:
            errors[label] = repr(exc)
        print('AUDIT', label, errors.get(label, 'checked'), flush=True)

    pairs = {}
    for seed in plan['seeds']:
        if not all(f'{arm}-{seed}' in cells for arm in ('base', 'optimized')):
            continue
        base, opt = (cells[f'{arm}-{seed}'] for arm in ('base', 'optimized'))
        left, right = base['comparable'], opt['comparable']
        equality = {key: value == right[key] for key, value in left.items()}
        mismatches = {key: [item for item in value.keys() | right[key].keys()
                            if value.get(item) != right[key].get(item)][:8]
                      for key, value in left.items() if isinstance(value, dict) and not equality[key]}
        pairs[seed] = dict(base_seconds=base['wall']['wall_seconds'], optimized_seconds=opt['wall']['wall_seconds'],
                           equality=equality, example_mismatches=mismatches,
                           rss_delta_mib=opt['peak_rss_mib'] - base['peak_rss_mib'])

    ordered = [cells[f'{arm}-{seed}']['wall'] for seed, arm in plan['order'] if f'{arm}-{seed}' in cells]
    complete = not errors and end['status'] == 'complete' and len(pairs) == len(plan['seeds'])
    in_order = all(a['finished'] <= b['started'] for a, b in zip(ordered, ordered[1:]))
    finished = time.time()
    audited_in_budget = finished <= start['deadline']
    base_wall = sum(pair['base_seconds'] for pair in pairs.values())
    opt_wall = sum(pair['optimized_seconds'] for pair in pairs.values())
    ratio = opt_wall / base_wall if base_wall else None
    adoption = (complete and in_order and audited_in_budget
                and ratio <= plan['gates']['maximum_wall_ratio']
                and all(pair['optimized_seconds'] < pair['base_seconds']
                        and all(pair['equality'].values()) for pair in pairs.values())
                and max(cell['peak_rss_mib'] for key, cell in cells.items() if key.startswith('optimized-'))
                - max(cell['peak_rss_mib'] for key, cell in cells.items() if key.startswith('base-'))
                <= plan['gates']['maximum_rss_increase_mib'])
    return dict(run_start=start, run_exit=end, cells=cells, errors=errors, pairs=pairs,
                ordered=in_order, complete=complete, adoption=adoption,
                base_wall_seconds=base_wall, optimized_wall_seconds=opt_wall, wall_ratio=ratio,
                audit_started=started, audit_finished=finished, audited_in_budget=audited_in_budget,
                actual_total_seconds=finished - start['started'])


def main():
    stage, output = map(Path, sys.argv[1:])
    result = compare(stage, load(stage / 'launch.json'))
    write(output, result)
    print(json.dumps({key: value for key, value in result.items() if key not in ('cells', 'pairs')}), flush=True)


if __name__ == '__main__':
    main()
