"""Bounded offline BC objective comparison; frozen runs are only read."""
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
from learning.sequences import read_shards, training_windows
from tests.diagnose_bc_parts import decompose, kind


def window_weights(rows):
    weights = {}
    for window in training_windows(rows, turns=8):
        counts = Counter(kind(r['candidates'][r['choice']]) for r in window)
        for row in window:
            weights[id(row)] = len(window) / len(counts) / counts[kind(row['candidates'][row['choice']])]
    return weights


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--format', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--epochs', type=int, default=8)
    parser.add_argument('--seconds-per-arm', type=int, default=600)
    args = parser.parse_args()
    torch.set_num_threads(1)
    config = json.loads((args.run / 'manifest.json').read_text())['config']
    checkpoint = args.run / args.format / 'last_bc.pt'
    model, saved = load_model(checkpoint, args.format)
    state = saved['runner']
    train = read_shards(state['teacher_shards'], partition='train', format_name=args.format,
                        limit=config['bc_records'], seed=config['seed'] + state['version'] - 1)
    heldout = read_shards(state['teacher_shards'], partition='validation', format_name=args.format,
                          limit=config['bc_validation_records'], seed=config['seed'])
    weights = window_weights(train)
    original_auxiliary = bc.auxiliary_loss

    def balanced_auxiliary(logits, rows):
        # Only the exact-policy term changes. The production update, sampler,
        # value objective, auxiliary objective and recurrent prefixes stay intact.
        targets = torch.tensor([r['choice'] for r in rows], device=logits.device)
        losses = F.cross_entropy(logits, targets, reduction='none')
        factors = logits.new_tensor([weights[id(r)] for r in rows])
        return original_auxiliary(logits, rows) + 10 * ((factors - 1) * losses).mean()

    results = dict(format=args.format, version=state['version'],
                   checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                   epochs=args.epochs, seconds_per_arm=args.seconds_per_arm, arms={})
    for name in ('baseline', 'balanced'):
        model.load_state_dict(saved['model'])
        optimizer = torch.optim.Adam(model.parameters())
        optimizer.load_state_dict(copy.deepcopy(saved['optimizer']))
        random.setstate(saved['python_rng'])
        torch.set_rng_state(saved['torch_rng'])
        visits = []

        def committed(cursor):
            visits.append({k: cursor[k] for k in ('epoch', 'step', 'updates', 'decisions_seen',
                                                  'visited_windows', 'window_visits')})

        model.train()
        started = time.monotonic()
        with patch.object(bc, 'auxiliary_loss', balanced_auxiliary if name == 'balanced' else original_auxiliary):
            metrics = bc.update(model, optimizer, train, epochs=args.epochs,
                                deadline=time.time() + args.seconds_per_arm, on_step=committed)
        elapsed = time.monotonic() - started
        model.eval()
        result = dict(metrics=metrics, training_seconds=elapsed, cursors=visits,
                      train=decompose(model, train), heldout=decompose(model, heldout),
                      quality=bc.imitation_quality(model, heldout))
        results['arms'][name] = result
        print(json.dumps(dict(arm=name, metrics=metrics, seconds=elapsed,
                              kinds=result['heldout']['kinds'])), flush=True)
        args.output.write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')
    results['same_sampling'] = results['arms']['baseline']['cursors'] == results['arms']['balanced']['cursors']
    args.output.write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
