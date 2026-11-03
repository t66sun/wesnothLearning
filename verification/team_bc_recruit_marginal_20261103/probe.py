"""Matched, in-memory type-marginal comparison on the frozen team v10 runtime."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import signal
import time
from unittest.mock import patch

import torch

from learning import bc
from learning.experiment import bc_effective
from learning.export import load_model
from learning.sequences import read_shards
from learning.updates import prepare, rollout_identity, setup
from tests.diagnose_bc_parts import decompose


HERE = Path(__file__).resolve().parent
FROZEN = Path('/home/tongshu/acceptance/team_bc_branch_20261102')
RUN = FROZEN / 'runs/team_bc_branch'
CHECKPOINT = RUN / 'team2v2/last_bc.pt'
OUT = HERE / 'observed'
ORIGINAL = bc.auxiliary_loss
FORMAT = 'team2v2'


def file_hash(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def object_hash(value):
    def tensor_data(tensor):
        data = tensor.detach().cpu().contiguous().numpy().tobytes()
        return [str(tensor.dtype), list(tensor.shape), hashlib.sha256(data).hexdigest()]

    encoded = json.dumps(value, default=tensor_data, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(encoded.encode()).hexdigest()


def write(name, value):
    with (OUT / name).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def recruit_auxiliary(logits, rows):
    # Only the actor key in the original auxiliary loss consults actor.id.
    # Use a distinct namespace for the virtual actor for each recruit type.
    supervised = []
    for row in rows:
        candidates = row['candidates']
        if candidates[row['choice']]['kind'] == 'recruit':
            candidates = [dict(c, actor={'id': ('recruit', c['type'])}) if c['kind'] == 'recruit' else c
                          for c in candidates]
            row = dict(row, candidates=candidates)
        supervised.append(row)
    return ORIGINAL(logits, supervised)


def check_loss():
    def recruit(name, slot):
        return dict(kind='recruit', type=name, x=slot, y=1, actor={'id': 'learning_probe'})

    candidates = [recruit('A', 1), recruit('A', 2), recruit('B', 2), {'kind': 'end_turn'}]
    row = {'choice': 0, 'candidates': candidates}
    same_type = torch.tensor([[0., 2., -1., 0.]])
    other_type = torch.tensor([[0., -1., 2., 0.]])
    original = [float(ORIGINAL(x, [row])) for x in (same_type, other_type)]
    experiment = [float(recruit_auxiliary(x, [row])) for x in (same_type, other_type)]
    assert abs(original[0] - original[1]) < 1e-6 and experiment[0] < experiment[1]
    other_row = dict(row, choice=3)
    assert torch.equal(recruit_auxiliary(same_type, [other_row]), ORIGINAL(same_type, [other_row]))
    return dict(original=original, recruit_type=experiment)


def duplicate_actor_groups(rows):
    count = 0
    for row in rows:
        cs = row['candidates']
        if cs[row['choice']]['kind'] != 'recruit':
            continue
        actor = cs[row['choice']]['actor']['id']
        assert all(((c.get('actor') or {}).get('id') == actor) == (c['kind'] == 'recruit') for c in cs)
        count += 1
    return count


def measure(model, train, validation, config, gate):
    model.eval()
    quality = bc.imitation_quality(model, validation, thresholds=config['bc_accuracy'])
    gate_inputs = dict(gate, imitation=quality)
    return dict(validation=quality['formats'][FORMAT], complete_gate=bc_effective(gate_inputs),
                train_kinds=decompose(model, train)['kinds'],
                validation_kinds=decompose(model, validation)['kinds'])


def state_hashes(model, optimizer):
    return dict(model=object_hash(model.state_dict()), adam=object_hash(optimizer.state_dict()),
                python_rng=object_hash(random.getstate()), torch_rng=object_hash(torch.get_rng_state()))


def fit(name, model, saved, train, validation, windows, config, gate, expected_state):
    started = time.monotonic()
    deadline = time.time() + 600
    signal.alarm(600)
    model.load_state_dict(saved['model'])
    optimizer = torch.optim.Adam(model.parameters())
    optimizer.load_state_dict(deepcopy(saved['optimizer']))
    random.setstate(saved['python_rng'])
    torch.set_rng_state(saved['torch_rng'])
    start_state = state_hashes(model, optimizer)
    assert start_state == expected_state
    indices = {id(window[0]): i for i, window in enumerate(windows)}
    visits = []
    factory = bc.make_bc_sampler

    def traced_sampler(rows):
        sampler = factory(rows)
        original_sample = sampler.sample

        def sample(count):
            drawn = original_sample(count)
            visits.append([indices[id(row)] for row in drawn])
            return drawn

        sampler.sample = sample
        return sampler

    def committed(cursor):
        if cursor['updates'] % 56 == 0:
            print(name, 'updates', cursor['updates'], 'elapsed', round(time.monotonic() - started, 2),
                  flush=True)

    print(name, 'start', flush=True)
    loss = ORIGINAL if name == 'control' else recruit_auxiliary
    model.train()
    with patch.object(bc, 'make_bc_sampler', traced_sampler), patch.object(bc, 'auxiliary_loss', loss):
        metrics = bc.update(model, optimizer, train, epochs=16, minibatch=config['minibatch'],
                            deadline=deadline, on_step=committed)
    update_seconds = time.monotonic() - started
    assert not metrics['interrupted'] and metrics['updates'] == len(visits) == 224, metrics
    assert metrics['window_visits'] == sum(map(len, visits)) == 896
    measures = measure(model, train, validation, config, gate)
    result = dict(start_state=start_state, metrics=metrics, windows_by_step=visits,
                  update_seconds=update_seconds, elapsed_seconds=time.monotonic() - started, **measures)
    write(name + '.json', result)
    signal.alarm(0)
    print(name, 'complete', result['complete_gate'], result['validation_kinds'], flush=True)
    return result


def main():
    torch.set_num_threads(1)
    OUT.mkdir(exist_ok=False)
    assert Path(bc.__file__).resolve().parent == FROZEN / 'learning'
    inventory = json.loads((HERE.parent / 'team_bc_branch_20261102/input_model_hashes.json').read_text())
    assert all(file_hash(path) == value for path, value in inventory.items())
    assert inventory[str(CHECKPOINT)] == 'b74350699b445e63cdd11fd07f317e0d818fe3d3166d49705b1342b00336035e'
    gate_file = RUN / 'team2v2/bc_gate.json'
    assert file_hash(gate_file) == '70f1ef8ef6cf3ff931c72847257a4ba9ea117cc9813d870396c7a64afffb8376'
    gate = json.loads(gate_file.read_text())
    config = json.loads((RUN / 'manifest.json').read_text())['config']
    assert config['bc_accuracy'] == dict(all=.4, recruit=.6, move=.35, attack=.35)
    model, saved = load_model(CHECKPOINT, FORMAT)
    state = saved['runner']
    assert state['version'] == state['batch'] == 10
    paths = state['teacher_shards']
    assert len(paths) == 48 and set(paths) == {p for p in inventory if p.endswith('.jsonl.gz')}
    train = read_shards(paths, partition='train', format_name=FORMAT, limit=config['bc_records'],
                        seed=config['seed'] + state['version'] - 1)
    validation = read_shards(paths, partition='validation', format_name=FORMAT,
                             limit=config['bc_validation_records'], seed=config['seed'])
    assert len(train) == 2048 and len(validation) == 1024 and config['seed'] == 20261101
    assert config['minibatch'] == 256
    device, windows, count, micro, steps = setup(model, prepare(model, train, allow_drop=True), 256)
    assert (device.type, len(windows), count, micro, steps) == ('cpu', 54, 4, 32, 14)
    reference = json.loads((HERE.parent / 'team_bc_branch_20261102/parts.json').read_text())[FORMAT]
    start = measure(model, train, validation, config, gate)
    assert start['validation_kinds'] == reference['heldout']['kinds']
    assert start['train_kinds'] == reference['train']['kinds']
    assert start['validation']['samples'] == gate['imitation']['formats'][FORMAT]['samples']
    assert not start['complete_gate']
    duplicate_groups = dict(train=duplicate_actor_groups(train), validation=duplicate_actor_groups(validation))
    assert duplicate_groups == {'train': 126, 'validation': 85}
    expected_state = dict(model=object_hash(saved['model']), adam=object_hash(saved['optimizer']),
                          python_rng=object_hash(saved['python_rng']), torch_rng=object_hash(saved['torch_rng']))
    entry = dict(train_hash=rollout_identity(train), validation_hash=rollout_identity(validation),
                 checkpoint_sha256=inventory[str(CHECKPOINT)], state_hashes=expected_state,
                 runtime_file=str(bc.__file__), loss_swap=check_loss(), duplicate_actor_groups=duplicate_groups,
                 train_rows=len(train),
                 validation_rows=len(validation), windows=len(windows), steps_per_epoch=steps,
                 epochs=16, updates_per_arm=224, max_seconds_per_arm=600, thresholds=config['bc_accuracy'],
                 frozen_gate=gate, start=start)
    write('entry.json', entry)
    print('preflight', entry['train_hash'], entry['validation_hash'], expected_state, flush=True)
    args = (model, saved, train, validation, windows, config, gate, expected_state)
    control = fit('control', *args)
    candidate = fit('recruit_type', *args)
    assert candidate['windows_by_step'] == control['windows_by_step']
    assert candidate['metrics']['decisions_seen'] == control['metrics']['decisions_seen']
    assert all(file_hash(path) == value for path, value in inventory.items())
    summary = dict(start_state_equal=candidate['start_state'] == control['start_state'],
                   ordered_windows_sha256=object_hash(control['windows_by_step']),
                   ordered_windows_equal=True, decisions_seen=control['metrics']['decisions_seen'],
                   original_inputs_unchanged=True,
                   complete_gate={name: arm['complete_gate'] for name, arm in
                                  [('control', control), ('recruit_type', candidate)]})
    print(json.dumps(summary), flush=True)
    write('comparison.json', summary)


if __name__ == '__main__':
    main()
