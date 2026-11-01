"""Read-only recruit errors, teacher ties and actual policy-input collisions.

Run with the frozen run's matching learning package on PYTHONPATH; this script
does not migrate old data, fit weights or change the production gate.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import torch

import learning
from learning.export import load_model
from learning.features import ENTITY
from learning.model import batch
from learning.sequences import read_shards
from tests.diagnose_bc_recruit_context import distance
from tests.diagnose_recruit_labels import audit, context_key


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@torch.no_grad()
def diagnose(model, rows, audited, seen):
    recruits = [r for r in rows if r['candidates'][r['choice']]['kind'] == 'recruit']
    assert len(recruits) == len(audited['rows'])
    counts = Counter()
    details = []
    fields = {name: i for i, (name, _) in enumerate(ENTITY)}
    for row, truth in zip(recruits, audited['rows']):
        inputs = batch([row])
        scores = model(*inputs)[0][0].tolist()
        candidates = row['candidates']
        label_index = row['choice']
        predicted_index = max(range(len(candidates)), key=scores.__getitem__)
        label, predicted = candidates[label_index], candidates[predicted_index]
        assert truth['label_type'] == label['type']
        assert truth['label_slot'] == [label['x'], label['y']]
        assert truth['type_optimal'] and truth['slot_optimal']
        entities = row['spatial']['entities']
        enemies = [e for e in entities if e['features'][fields['enemy']]
                   and not e['features'][fields['age']] and not e['features'][fields['petrified']]]
        leaders = [e for e in entities if e['features'][fields['own']] and e['features'][fields['leader']]]
        nearest = lambda candidate: min([100] + [distance(candidate['x'], candidate['y'], e['x'], e['y'])
                                               for e in enemies])
        if predicted_index == label_index:
            reason = 'exact'
        elif predicted['kind'] != 'recruit':
            reason = 'wrong_kind'
        elif min(distance(predicted['x'], predicted['y'], e['x'], e['y']) for e in leaders) > 3:
            reason = 'outside_teacher_radius'
        elif predicted['type'] not in truth['top_types']:
            reason = 'worse_type'
        elif not truth['enemy_count_matches']:
            reason = 'unresolved_enemy_context'
        elif nearest(predicted) > nearest(label):
            reason = 'worse_slot'
        else:
            reason = 'equivalent_preference'
        counts[reason] += 1
        # Compare precisely the candidate-varying tensors consumed by Policy.
        payload = inputs[5]
        tensors = [inputs[2]] + [payload[key] for key in (
            'local', 'geometry', 'actors', 'actors_types', 'actors_indices', 'actors_present',
            'targets', 'targets_types', 'targets_indices', 'targets_present')]
        collisions = [i for i in range(len(candidates)) if i != label_index
                      and all(torch.equal(t[0, label_index], t[0, i]) for t in tensors)]
        counts['input_collision_rows'] += bool(collisions)
        counts['samples'] += 1
        represented = {pool: context_key(truth) in keys for pool, keys in seen.items()}
        for pool, matched in represented.items():
            counts[pool + '_context_seen'] += matched
            counts[pool + '_seen_exact'] += matched and reason == 'exact'
        details.append(dict(game_id=row['game_id'], turn=row['turn'], decision=truth['decision'],
            reason=reason, label_type=label['type'], predicted_type=predicted.get('type'),
            label_slot=[label['x'], label['y']], predicted_slot=[predicted.get('x'), predicted.get('y')],
            margin=scores[predicted_index]-scores[label_index], input_collisions=collisions,
            type_ties=len(truth['top_types']), slot_ties=len(truth['top_slots']), context_seen=represented))
    return dict(counts=dict(counts), rows=details)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--labels', type=Path, required=True)
    parser.add_argument('--runtime-source', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    torch.set_num_threads(1)
    config = json.loads((args.run/'manifest.json').read_text())['config']
    checkpoint = args.run/'team2v2'/'last_bc.pt'
    model, saved = load_model(checkpoint, 'team2v2')
    model.eval()
    prior = json.loads(args.labels.read_text())
    assert digest(checkpoint) == prior['checkpoint_sha256']
    runtime = Path(learning.__file__).resolve().parent
    assert digest(runtime/'teachers/gpt6astra/lua/four.lua') == prior['teacher_file_sha256']
    seen = {pool: {context_key(row) for row in prior[pool]['rows']} for pool in ('train', 'full_train')}
    result = dict(runtime_source=args.runtime_source, runtime_path=str(runtime),
        checkpoint_sha256=digest(checkpoint), labels_sha256=digest(args.labels),
        runtime_hashes={name: digest(runtime/name) for name in ('model.py', 'sequences.py', 'features.py')})
    for partition, limit, seed in (
        ('train', config['bc_records'], config['seed']+saved['runner']['version']-1),
        ('validation', config['bc_validation_records'], config['seed'])):
        rows = read_shards(saved['runner']['teacher_shards'], partition=partition,
                           format_name='team2v2', limit=limit, seed=seed)
        truth = audit(rows, prior['weights'])
        assert json.loads(json.dumps(truth)) == prior[partition]
        result[partition] = diagnose(model, rows, truth, seen)
        print(json.dumps(dict(partition=partition, **result[partition]['counts'])), flush=True)
    assert result['train']['counts']['exact'] == 24
    assert result['validation']['counts']['exact'] == 11
    assert digest(checkpoint) == result['checkpoint_sha256']
    args.output.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
