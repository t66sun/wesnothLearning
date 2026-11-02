"""Fixed native accuracy/parry comparisons with explicit test-only objects."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from _engine_lite import LiteEngine
from engine_lite.differential import game_spec
from learning.native_transport import NativeTransport


CASES = [
    ('both_directions', 'Orcish Warrior', 'Orcish Grunt', 0, 20, 10, 70),
    ('lower_clamp', 'Orcish Warrior', 'Orcish Grunt', 0, -100, 20, 0),
    ('upper_clamp', 'Orcish Warrior', 'Orcish Grunt', 0, 100, -50, 100),
    ('magical', 'Mage', 'Dark Adept', 1, -100, 100, 70),
    ('marksman', 'Elvish Sharpshooter', 'Elvish Archer', 1, -100, 100, 60),
    ('no_counter', 'Mage', 'Dark Adept', 0, 20, 100, 80),
]


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
        for name, attacker, defender, wi, accuracy, parry, chance in CASES:
            rules = copy.deepcopy(original)
            spec = game_spec(rules, attacker, defender)
            for index, acc, block in [(2, accuracy, 15), (3, 5, parry)]:
                u = spec['units'][index]
                definition = rules['units'][u['unit_type']]
                for weapon in definition['weapons']:
                    weapon.update(accuracy=acc, parry=block)
                cfg = dict(id=u['id'], type=u['unit_type'], side=u['side'],
                    x=u['pos']%7+1, y=u['pos']//7+1, hitpoints=u['hp'],
                    experience=0, moves=u['moves'], attacks_left=1,
                    random_traits=False, random_gender=False, generate_name=False)
                cfg[1] = ['modifications', [['object', {1: ['effect', dict(
                    apply_to='attack', set_accuracy=acc, set_parry=block)]}]]]
                u['native_cfg'] = cfg
            for side in spec['sides']:
                side['gold'] = 0
            native.reset(spec)
            lite = LiteEngine(json.dumps(rules), json.dumps(spec))
            before = lite.snapshot()
            predicted = json.loads(lite.forecast(1, 'attacker', 'defender', wi, 0))
            assert lite.snapshot() == before
            action = dict(kind='attack', unit='attacker', target='defender', weapon=wi)
            nr = native.step(action)
            lr = json.loads(lite.step(json.dumps(action)))
            row = dict(name=name, spec=spec, native=nr, lite=lr, forecast=predicted)
            (args.output/(name+'.json')).write_text(json.dumps(row, indent=2)+'\n')
            oracle = nr['differential']['oracle']
            assert abs(oracle['attacker_hit']*100-chance) < 1e-9, (name, oracle['attacker_hit'])
            assert lr['strikes'][0]['chance'] == chance, name
            for side in ('attacker', 'defender'):
                for metric in ('average_hp', 'poisoned', 'slowed'):
                    assert abs(oracle[side][metric]-predicted[side][metric]) < 1e-9, (name, side, metric)
                for hp in set(oracle[side]['hp_chance']) | set(predicted[side]['hp_chance']):
                    assert abs(oracle[side]['hp_chance'].get(hp, 0)-predicted[side]['hp_chance'].get(hp, 0)) < 1e-9, (name, side, hp)
            if name == 'both_directions':
                assert abs(oracle['defender_hit']-.5) < 1e-9
                assert all(s['chance'] == 50 for s in lr['strikes'] if s['attacker'] == 'defender')
            results.append(dict(name=name, attacker_hit=oracle['attacker_hit'], result='PASS'))
            print(json.dumps(results[-1]), flush=True)
        summary = dict(source=args.source, rules_sha256=hashlib.sha256(raw).hexdigest(),
            native_sha256=native.executable_hash, transport_sha256=native.source_hash, cases=results)
    (args.output/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')


if __name__ == '__main__':
    main()
