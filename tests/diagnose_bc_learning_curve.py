"""Bounded original-loss learning curve; never updates a frozen run or checkpoint."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import time

import torch

from learning import bc
from learning.export import load_model
from learning.sequences import read_shards
from learning.updates import prepare, setup
from tests.diagnose_bc_parts import decompose, exposure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--format', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--updates', type=int, default=600)
    parser.add_argument('--seconds', type=int, default=900)
    args = parser.parse_args()
    torch.set_num_threads(1)
    config = json.loads((args.run/'manifest.json').read_text())['config']
    checkpoint = args.run/args.format/'last_bc.pt'
    model, saved = load_model(checkpoint, args.format)
    state = saved['runner']
    train = read_shards(state['teacher_shards'], partition='train', format_name=args.format,
        limit=config['bc_records'], seed=config['seed']+state['version']-1)
    heldout = read_shards(state['teacher_shards'], partition='validation', format_name=args.format,
        limit=config['bc_validation_records'], seed=config['seed'])
    steps = setup(model, prepare(model, train, allow_drop=True), config['minibatch'])[-1]
    epochs = args.updates//steps
    optimizer = torch.optim.Adam(model.parameters())
    optimizer.load_state_dict(saved['optimizer'])
    result = dict(format=args.format, version=state['version'],
        checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        max_updates=args.updates, planned_updates=epochs*steps, epochs=epochs,
        seconds=args.seconds, exposure=exposure(train), curve=[])
    started = time.monotonic()

    def measure(updates):
        model.eval()
        row = dict(updates=updates, elapsed_seconds=time.monotonic()-started,
            train=decompose(model, train), heldout=decompose(model, heldout),
            quality=bc.imitation_quality(model, heldout))
        result['curve'].append(row)
        args.output.write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(dict(updates=updates, seconds=row['elapsed_seconds'],
            train=row['train']['kinds'], heldout=row['heldout']['kinds'])), flush=True)
        model.train()

    measure(0)
    random.setstate(saved['python_rng'])
    torch.set_rng_state(saved['torch_rng'])
    started = time.monotonic()
    last_cursor = {}

    def committed(cursor):
        last_cursor.update(cursor)
        if cursor['updates'] in (50, 150, 300, 600):
            measure(cursor['updates'])

    result['metrics'] = bc.update(model, optimizer, train, epochs=epochs,
        minibatch=config['minibatch'], deadline=time.time()+args.seconds, on_step=committed)
    result['elapsed_seconds'] = time.monotonic()-started
    result['cursor'] = last_cursor
    updates = result['metrics']['updates']
    if result['curve'][-1]['updates'] != updates:
        measure(updates)
    args.output.write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
