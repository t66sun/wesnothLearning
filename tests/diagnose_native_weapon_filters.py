"""Native counter eligibility and explicit attack-weight contract."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from _engine_lite import LiteEngine
from engine_lite.differential import game_spec
from learning.native_transport import NativeTransport


CASES = [('zero', (0, 1), 'hammer'), ('negative', (-1, 1), 'hammer'),
         ('none', (0, -1), None), ('positive', (1, 1000), 'axe')]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rules', type=Path, required=True)
    parser.add_argument('--wesnoth', required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    raw = (args.rules/'rules.json').read_bytes()
    original = json.loads(raw)
    results = []
    with NativeTransport(wesnoth=args.wesnoth, timeout=30, startup_timeout=120) as native:
        for name, weights, expected in CASES:
            rules = copy.deepcopy(original)
            spec = game_spec(rules, 'Elvish Fighter', 'Dwarvish Fighter')
            for index in (2, 3):
                unit = spec['units'][index]
                effects = {}
                for wi, weapon in enumerate(rules['units'][unit['unit_type']]['weapons']):
                    field = 'attack_weight' if index == 2 else 'defense_weight'
                    weight = 0 if index == 2 else weights[wi]
                    weapon[field] = weight
                    effects[wi+1] = ['effect', dict(apply_to='attack', name=weapon['id'], **{field: weight})]
                cfg = dict(id=unit['id'], type=unit['unit_type'], side=unit['side'],
                    x=unit['pos']%7+1, y=unit['pos']//7+1, hitpoints=unit['hp'],
                    experience=0, moves=unit['moves'], attacks_left=1,
                    random_traits=False, random_gender=False, generate_name=False)
                cfg[1] = ['modifications', [['object', effects]]]
                unit['native_cfg'] = cfg
            for side in spec['sides']:
                side['gold'] = 0
            native.reset(spec)
            lite = LiteEngine(json.dumps(rules), json.dumps(spec))
            action = dict(kind='attack', unit='attacker', target='defender', weapon=0)
            assert action in native.legal_actions(1)
            assert action in json.loads(lite.legal_actions(1))
            before = lite.snapshot()
            predicted = json.loads(lite.forecast(1, 'attacker', 'defender', 0, 0))
            assert lite.snapshot() == before
            nr = native.step(action)
            lr = json.loads(lite.step(json.dumps(action)))
            row = dict(name=name, spec=spec, native=nr, lite=lr, forecast=predicted)
            (args.output/(name+'.json')).write_text(json.dumps(row, indent=2)+'\n')
            oracle = nr['differential']['oracle']
            counter = oracle.get('defender_weapon')
            assert (counter.get('name') if counter else None) == expected, (name, counter)
            for side in ('attacker', 'defender'):
                for metric in ('average_hp', 'poisoned', 'slowed'):
                    assert abs(oracle[side][metric]-predicted[side][metric]) < 1e-9, (name, side, metric)
                for hp in set(oracle[side]['hp_chance']) | set(predicted[side]['hp_chance']):
                    assert abs(oracle[side]['hp_chance'].get(hp, 0)-predicted[side]['hp_chance'].get(hp, 0)) < 1e-9, (name, side, hp)
            if expected is None:
                assert all(s['attacker'] == 'attacker' for s in lr['strikes'])
            results.append(dict(name=name, counter=expected, result='PASS'))
            print(json.dumps(results[-1]), flush=True)
        summary = dict(source=args.source, rules_sha256=hashlib.sha256(raw).hexdigest(),
            native_sha256=native.executable_hash, transport_sha256=native.source_hash, cases=results)
    (args.output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')


if __name__ == '__main__':
    main()
