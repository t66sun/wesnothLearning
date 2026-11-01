"""Read-only decomposition of a committed teacher-only BC batch and checkpoint."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import time

import torch

from learning.export import load_model
from learning.model import batch
from learning.sequences import read_shards, training_windows


def kind(candidate):
    return 'attack' if candidate['kind'] == 'move_attack' else candidate['kind']


def position(candidate, role):
    if role == 'target':
        keys = ('ex', 'ey') if candidate['kind'] == 'move_attack' else ('tx', 'ty')
    elif role == 'landing':
        keys = ('tx', 'ty') if candidate['kind'] == 'move_attack' else ('x', 'y')
    else:
        keys = ('x', 'y')
    return tuple(candidate.get(key) for key in keys)


def exposure(rows):
    """Expected loss mass under equal game-family/equal-window sampling."""
    windows = training_windows(rows, turns=8)
    families = Counter(window[0]['game_family'] for window in windows)
    mass = Counter()
    counts = Counter(kind(r['candidates'][r['choice']]) for r in rows)
    for window in windows:
        weight = 1 / len(families) / families[window[0]['game_family']] / len(window)
        for row in window:
            mass[kind(row['candidates'][row['choice']])] += weight
    return dict(rows=len(rows), windows=len(windows), families=len(families),
                row_counts=dict(counts), row_share={k: v / len(rows) for k, v in counts.items()},
                expected_loss_share=dict(mass))


@torch.no_grad()
def decompose(model, rows):
    rows = [r for r in rows if len(r['candidates']) > 1]
    totals = defaultdict(Counter)
    by_type = defaultdict(Counter)
    confusion = defaultdict(Counter)
    examples = []
    for offset in range(0, len(rows), 64):
        chunk = rows[offset:offset + 64]
        logits, _ = model(*batch(chunk))
        for index, row in enumerate(chunk):
            candidates = row['candidates']
            label_index = row['choice']
            label = candidates[label_index]
            scores = logits[index, :len(candidates)].tolist()
            predicted_index = max(range(len(candidates)), key=scores.__getitem__)
            predicted = candidates[predicted_index]
            wanted = kind(label)
            same = [i for i, c in enumerate(candidates) if kind(c) == wanted]
            best_kind = max(same, key=scores.__getitem__)
            entry = totals[wanted]
            entry.update(samples=1, correct=int(predicted_index == label_index),
                         same_kind=int(kind(predicted) == wanted),
                         within_kind_correct=int(best_kind == label_index),
                         top3=int(label_index in sorted(range(len(candidates)), key=scores.__getitem__, reverse=True)[:3]))
            confusion[wanted][kind(predicted)] += 1
            if wanted == 'recruit':
                right_kind = kind(predicted) == wanted
                entry['same_type'] += int(right_kind and predicted['type'] == label['type'])
                entry['same_slot'] += int(right_kind and position(predicted, 'actor') == position(label, 'actor'))
                by_type[label['type']].update(samples=1, correct=int(predicted_index == label_index),
                                              same_type=int(right_kind and predicted['type'] == label['type']))
            elif wanted == 'attack':
                for role in ('actor', 'target', 'landing'):
                    entry['same_' + role] += int(kind(predicted) == wanted and position(predicted, role) == position(label, role))
                entry['same_weapon'] += int(kind(predicted) == wanted and predicted.get('weapon') == label.get('weapon'))
            if wanted in ('recruit', 'attack') and predicted_index != label_index and len(examples) < 12:
                fields = ('kind', 'type', 'x', 'y', 'tx', 'ty', 'ex', 'ey', 'weapon', 'full')
                examples.append(dict(game_id=row['game_id'], turn=row['turn'],
                    label={k: label[k] for k in fields if k in label},
                    predicted={k: predicted[k] for k in fields if k in predicted},
                    margin=scores[predicted_index] - scores[label_index]))
    return dict(samples=len(rows), kinds=dict(totals), recruit_types=dict(by_type),
                kind_confusion=dict(confusion), error_examples=examples)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    torch.set_num_threads(1)
    config = json.loads((args.run / 'manifest.json').read_text())['config']
    results = {}
    for fmt in config['formats']:
        started = time.monotonic()
        checkpoint = args.run / fmt / 'last_bc.pt'
        model, saved = load_model(checkpoint, fmt)
        model.eval()
        state = saved['runner']
        train = read_shards(state['teacher_shards'], partition='train', format_name=fmt,
                           limit=config['bc_records'], seed=config['seed'] + state['version'] - 1)
        heldout = read_shards(state['teacher_shards'], partition='validation', format_name=fmt,
                             limit=config['bc_validation_records'], seed=config['seed'])
        results[fmt] = dict(version=state['version'], checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                            exposure=exposure(train), train=decompose(model, train), heldout=decompose(model, heldout),
                            seconds=time.monotonic() - started)
        print(json.dumps(dict(format=fmt, **results[fmt]), sort_keys=True), flush=True)
    args.output.write_text(json.dumps(results, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
