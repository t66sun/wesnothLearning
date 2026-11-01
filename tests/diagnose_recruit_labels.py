"""Reconstruct teacher recruit preferences from frozen legal-view inputs only."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from lupa import LuaRuntime
import torch

from learning.features import ENTITY, GLOBAL, UNIT_TYPES
from learning.data import _shard_identity, validate_record
from learning.sequences import read_shards, _iter_rows
from tests.diagnose_bc_recruit_context import distance


def audit(rows, weights):
    fields = {name: i for i, (name, _) in enumerate(ENTITY)}
    globals_ = {name: i for i, (name, _) in enumerate(GLOBAL)}
    result = []
    for row in rows:
        label = row['candidates'][row['choice']]
        if label['kind'] != 'recruit':
            continue
        entities = row['spatial']['entities']
        own = [e for e in entities if e['features'][fields['own']]]
        counts = Counter(UNIT_TYPES[e['type_index']] for e in own
                         if not e['features'][fields['leader']])
        enemies = [e for e in entities if e['features'][fields['enemy']]
            and not e['features'][fields['age']] and not e['features'][fields['petrified']]]
        undead = sum(round(float(e['features'][fields['resistance_blade']])*100) >= 30 for e in enemies)
        drakes = sum(round(float(e['features'][fields['resistance_fire']])*100) >= 40 for e in enemies)
        leaders = [e for e in own if e['features'][fields['leader']]]
        recruits = [c for c in row['candidates'] if c['kind'] == 'recruit'
            and min(distance(c['x'], c['y'], e['x'], e['y']) for e in leaders) <= 3]
        scores = {}
        for candidate in recruits:
            name = candidate['type']
            weight = weights.get(name, 1)
            if undead > 1 and name in ('Mage', 'Dark Adept', 'Wose', 'Heavy Infantryman', 'Troll Whelp', 'Drake Burner'):
                weight *= 2
            if drakes > 1 and name in ('Spearman', 'Elvish Archer', 'Dark Adept', 'Saurian Skirmisher'):
                weight *= 1.8
            scores[name] = weight/(1+counts[name])
        best = max(scores.values())
        top_types = sorted(name for name, score in scores.items() if abs(score-best) < 1e-9)
        slots = {}
        for candidate in recruits:
            if candidate['type'] == label['type']:
                pos = (candidate['x'], candidate['y'])
                slots[pos] = min([100]+[distance(*pos, e['x'], e['y']) for e in enemies])
        top_slots = sorted(pos for pos, score in slots.items() if score == min(slots.values()))
        result.append(dict(game_id=row['game_id'], family=row['game_family'], turn=row['turn'],
            label_type=label['type'], label_slot=[label['x'], label['y']],
            decision=row.get('decision', row.get('action_index')),
            own_counts=dict(counts), undead=undead, drakes=drakes, type_scores=scores,
            top_types=top_types, top_slots=top_slots,
            type_optimal=label['type'] in top_types,
            slot_optimal=(label['x'], label['y']) in top_slots,
            own_context_complete=len(own) == round(float(row['global'][globals_['own_units']])*40),
            enemy_count_matches=len(enemies) == round(float(row['global'][globals_['visible_enemies']])*40)))
    return dict(samples=len(result),
        counts={key:sum(r[key] for r in result) for key in
            ('type_optimal', 'slot_optimal', 'own_context_complete', 'enemy_count_matches')},
        unique_type=sum(len(r['top_types']) == 1 for r in result),
        unique_slot=sum(len(r['top_slots']) == 1 for r in result), rows=result)


def full_training(paths, counts):
    for name in paths:
        path = Path(name)
        stat = path.stat()
        identity = _shard_identity(str(path), stat.st_size, stat.st_mtime_ns)
        if identity is None or identity[2] != 'train':
            continue
        counts['families'] += 1
        for row in _iter_rows(path):
            counts['raw_rows'] += 1
            if counts['raw_rows'] > 50000:
                raise ValueError('diagnostic raw-row cap exceeded')
            if row.get('faults') or row.get('choice', -1) < 0:
                continue
            kind = row['candidates'][row['choice']]['kind']
            counts[kind] += 1
            if kind == 'recruit':
                validate_record(row, 'team2v2')
                yield row


def context_key(row):
    return (tuple(sorted(row['own_counts'].items())), row['undead'] > 1,
            row['drakes'] > 1, tuple(sorted(row['type_scores'])))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads((args.run/'manifest.json').read_text())['config']
    checkpoint = args.run/'team2v2'/'last_bc.pt'
    state = torch.load(checkpoint, map_location='cpu', weights_only=False)['runner']
    teacher = Path('learning/teachers/gpt6astra/lua/four.lua').read_bytes()
    table = re.search(r'local weights=(\{.*?\n\})', teacher.decode(), re.S).group(1)
    weights = dict(LuaRuntime().eval(table))
    result = dict(checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        teacher_file_sha256=hashlib.sha256(teacher).hexdigest(), weights=weights)
    for partition, limit, seed in (
        ('train', config['bc_records'], config['seed']+state['version']-1),
        ('validation', config['bc_validation_records'], config['seed'])):
        rows = read_shards(state['teacher_shards'], partition=partition, format_name='team2v2', limit=limit, seed=seed)
        result[partition] = audit(rows, weights)
    counts = Counter()
    result['full_train'] = audit(full_training(state['teacher_shards'], counts), weights)
    result['full_train_counts'] = dict(counts)
    result['validation_contexts_seen'] = {}
    for pool in ('train', 'full_train'):
        keys = {context_key(row) for row in result[pool]['rows']}
        result['validation_contexts_seen'][pool] = sum(context_key(row) in keys for row in result['validation']['rows'])
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({part:{k:v for k,v in result[part].items() if k != 'rows'}
                      for part in ('train', 'validation', 'full_train')}), flush=True)
    print(json.dumps(dict(full_train_counts=dict(counts), validation_contexts_seen=result['validation_contexts_seen'])))


if __name__ == '__main__':
    main()
