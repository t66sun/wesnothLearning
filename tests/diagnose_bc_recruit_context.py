"""Test two legal recruit-context inputs on a copy of a frozen BC model."""
import argparse
from collections import Counter
import copy
import hashlib
import json
from pathlib import Path
import random
import time
from unittest.mock import patch

import torch
import torch.nn.functional as F

from learning import bc
from learning.export import load_model
from learning.features import ENTITY, GLOBAL
from learning.model import batch
from learning.sequences import read_shards
from learning.updates import prepare, setup
from tests import diagnose_bc_parts as parts


def distance(x, y, tx, ty):
    q, tq = x - 1, tx - 1
    r, tr = y - 1 - q // 2, ty - 1 - tq // 2
    return max(abs(q - tq), abs(r - tr), abs(q + r - tq - tr))


def context(row):
    fields = {name: i for i, (name, _) in enumerate(ENTITY)}
    entities = row['spatial']['entities']
    own = Counter(e['type_index'] for e in entities
                  if e['features'][fields['own']] and not e['features'][fields['leader']])
    enemies = [e for e in entities if e['features'][fields['enemy']] and not e['features'][fields['age']]]
    return [[own[c['actor']['type_index']] / 10,
             min((distance(c['x'], c['y'], e['x'], e['y']) for e in enemies), default=50) / 50]
            if c['kind'] == 'recruit' else [0., 0.] for c in row['candidates']]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--format', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--updates', type=int, help='maximum updates using complete epochs; default eight epochs')
    parser.add_argument('--seconds', type=int, default=600)
    args = parser.parse_args()
    torch.set_num_threads(1)
    config = json.loads((args.run / 'manifest.json').read_text())['config']
    path = args.run / args.format / 'last_bc.pt'
    model, saved = load_model(path, args.format)
    state = saved['runner']
    train = read_shards(state['teacher_shards'], partition='train', format_name=args.format,
                        limit=config['bc_records'], seed=config['seed'] + state['version'] - 1)
    heldout = read_shards(state['teacher_shards'], partition='validation', format_name=args.format,
                          limit=config['bc_validation_records'], seed=config['seed'])
    extra = {id(r): context(r) for r in train + heldout}
    old = model.scorer[0]
    expanded = torch.nn.Linear(old.in_features + 2, old.out_features)
    with torch.no_grad():
        expanded.weight.copy_(F.pad(old.weight, (0, 2)))
        expanded.bias.copy_(old.bias)
    model.scorer[0] = expanded
    optimizer = torch.optim.Adam(model.parameters())
    optimizer.load_state_dict(copy.deepcopy(saved['optimizer']))
    for key in ('exp_avg', 'exp_avg_sq'):
        optimizer.state[expanded.weight][key] = F.pad(optimizer.state[expanded.weight][key], (0, 2))
    current = None
    steps = setup(model, prepare(model, train, allow_drop=True), config['minibatch'])[-1]
    epochs = args.updates // steps if args.updates is not None else 8

    def inputs(rows, *a, **kw):
        nonlocal current
        tensors = batch(rows, *a, **kw)
        values = tensors[2].new_zeros(*tensors[2].shape[:2], 2)
        for i, row in enumerate(rows):
            values[i, :len(row['candidates'])] = values.new_tensor(extra[id(row)])
        current = values
        return tensors

    def append_context(module, inputs):
        return (torch.cat([inputs[0], current], -1),)

    model.scorer.register_forward_pre_hook(append_context)
    random.setstate(saved['python_rng'])
    torch.set_rng_state(saved['torch_rng'])
    model.train()
    cursors = []

    def committed(cursor):
        cursors.append({k: cursor[k] for k in ('epoch', 'step', 'updates', 'decisions_seen',
                                              'visited_windows', 'window_visits')})
        if cursor['updates'] % 50 == 0:
            print(json.dumps(dict(updates=cursor['updates'],
                                  training_seconds=time.monotonic()-started)), flush=True)

    with patch.object(bc, 'batch', inputs), patch.object(parts, 'batch', inputs):
        model.eval()
        before = parts.decompose(model, heldout)
        model.train()
        started = time.monotonic()
        metrics = bc.update(model, optimizer, train, epochs=epochs, minibatch=config['minibatch'],
                            deadline=time.time() + args.seconds, on_step=committed)
        elapsed = time.monotonic() - started
        model.eval()
        result = dict(format=args.format, checkpoint_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                      epochs=epochs, max_updates=args.updates, planned_updates=epochs*steps,
                      seconds_cap=args.seconds, training_seconds=elapsed, metrics=metrics, cursors=cursors,
                      before=before, train=parts.decompose(model, train), heldout=parts.decompose(model, heldout),
                      quality=bc.imitation_quality(model, heldout))
        if not metrics['interrupted']:
            assert metrics['updates'] == epochs*steps
    own_index = [name for name, _ in ENTITY].index('own')
    total_index = [name for name, _ in GLOBAL].index('own_units')
    result['incomplete_own_context_rows'] = int(sum(
        abs(sum(e['features'][own_index] for e in r['spatial']['entities']) - r['global'][total_index] * 40) > .01
        for r in train + heldout))
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(metrics=metrics, seconds=elapsed, kinds=result['heldout']['kinds'])), flush=True)


if __name__ == '__main__':
    main()
