"""Read-only scope diagnosis of native top-level weapon weight declarations."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from engine_lite.audit import children, training_closure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rules-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    directory = args.rules_dir
    catalog = json.loads((directory/'catalog.json').read_text())
    rules_bytes = (directory/'rules.json').read_bytes()
    digest = hashlib.sha256(rules_bytes).hexdigest()
    if digest != catalog['rules_file_sha256']:
        raise ValueError('rules differ from their frozen hash')
    rules = json.loads(rules_bytes)
    coverage = json.loads((directory/'coverage.json').read_text())
    closure = training_closure(rules, coverage)
    training = set(closure['unit_ids'])
    records, captures, units = {}, [], set()
    attacks = 0
    for source in catalog['captures']:
        raw = (directory/'captures'/(source['sha256']+'.json')).read_bytes()
        if hashlib.sha256(raw).hexdigest() != source['sha256']:
            raise ValueError('capture differs from its frozen hash: '+source['scope'])
        capture = json.loads(raw)
        captures.append(dict(scope=source['scope'], sha256=source['sha256']))
        for unit_id, compact in capture['units'].items():
            units.add(unit_id)
            native_id = unit_id if unit_id in capture['raw_definitions'] else compact['native_id']
            for index, (tag, declaration) in enumerate(children(capture['raw_definitions'][native_id])):
                if tag != 'attack':
                    continue
                attacks += 1
                weights = {key: declaration[key] for key in ('attack_weight', 'defense_weight')
                           if key in declaration and float(declaration[key]) != 1.0}
                if not weights:
                    continue
                key = (unit_id, index, json.dumps(weights, sort_keys=True))
                row = records.setdefault(key, dict(unit=unit_id, native_id=native_id,
                    weapon=declaration.get('name'), weights=weights, scopes=[],
                    in_training_closure=unit_id in training))
                row['scopes'].append(source['scope'])
    rows = [records[key] for key in sorted(records)]
    result = dict(source_commit=os.environ['SOURCE_COMMIT'], rules_sha256=digest,
        captures=captures, captured_units=len(units), attack_declarations_with_scope_repetition=attacks,
        training_unit_count=len(training), training_unit_ids=sorted(training),
        nondefault_weight_declarations=rows,
        affected_training_unit_ids=sorted({row['unit'] for row in rows if row['in_training_closure']}),
        scope='top-level base-type attack declarations only; excludes variations and runtime objects',
        limits='No native combat, collection, training or strength result; full filters remain unaccepted.')
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({key: result[key] for key in ('source_commit', 'rules_sha256',
        'captured_units', 'training_unit_count', 'affected_training_unit_ids')}
        | dict(captures=len(captures), nondefault_declarations=len(rows)), indent=2))


if __name__ == '__main__':
    main()
