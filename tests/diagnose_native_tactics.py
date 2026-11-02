"""Native/lite probability regression on fixed public combat positions."""
import argparse
import hashlib
import json
from pathlib import Path
import time

from engine_lite.differential import game_spec
from learning.adapters import LiteAdapter
from learning.native_transport import NativeTransport


CASES = (
    ('kill_threshold', 'Elvish Fighter', 'Orcish Grunt', 0, None, 14),
    ('death_threshold', 'Elvish Fighter', 'Orcish Grunt', 0, 8, None),
    ('poison', 'Orcish Assassin', 'Elvish Fighter', 1, None, None),
    ('slow', 'Elvish Shaman', 'Orcish Grunt', 1, None, None),
    ('resistance_retaliation', 'Skeleton', 'Dwarvish Fighter', 0, None, None),
    ('ranged_without_retaliation', 'Mage', 'Orcish Grunt', 1, None, None),
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rules', type=Path, required=True)
    parser.add_argument('--wesnoth', required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    raw = (args.rules/'rules.json').read_bytes()
    rules = json.loads(raw)
    rows = []
    started = time.monotonic()
    with NativeTransport(wesnoth=args.wesnoth, timeout=30, startup_timeout=120) as native:
        for name, attacker, defender, weapon, attacker_hp, defender_hp in CASES:
            spec = game_spec(rules, attacker, defender)
            for side in spec['sides']:
                side['gold'] = 0
            for index, hp in ((2, attacker_hp), (3, defender_hp)):
                if hp is not None:
                    spec['units'][index]['hp'] = hp
            action = dict(kind='attack', unit='attacker', target='defender', weapon=weapon)
            native.reset(spec)
            lite = LiteAdapter(spec, rules_dir=args.rules, require_accepted=False)
            before = dict(native=native.observe(1), lite=lite.observe(1))
            native_legal = native.legal_actions(1)
            lite_legal = lite.legal_actions(1)
            assert action in native_legal and action in lite_legal, name
            forecast = lite.forecast(1, 'attacker', 'defender', weapon)
            native_result = native.step(action)
            lite_result = lite.step(action)
            row = dict(name=name, spec=spec, action=action, initial=before,
                       legal=dict(native=native_legal, lite=lite_legal),
                       native=native_result['differential'], lite_forecast=forecast,
                       lite_actual=lite_result)
            for who, identifier in (('attacker', 'attacker'), ('defender', 'defender')):
                after = next((u for u in lite.observe(1)['units'] if u['id'] == identifier), None)
                assert forecast[who]['hp_chance'].get(str(after['hp'] if after else 0), 0) > 0, name
            lite.close()
            (args.output/(name+'.json')).write_text(json.dumps(row, indent=2)+'\n')
            oracle = row['native']['oracle']
            for who in ('attacker', 'defender'):
                for metric in ('average_hp', 'poisoned', 'slowed'):
                    assert abs(oracle[who][metric]-forecast[who][metric]) < 1e-9, (name, who, metric)
                nh, lh = oracle[who]['hp_chance'], forecast[who]['hp_chance']
                for hp in set(nh) | set(lh):
                    assert abs(nh.get(hp, 0)-lh.get(hp, 0)) < 1e-9, (name, who, hp)
            metrics = {who: dict(native_mean_hp=oracle[who]['average_hp'],
                lite_hp=forecast[who]['average_hp'], native_death=oracle[who]['hp_chance'].get('0', 0),
                lite_death=forecast[who]['hp_chance'].get('0', 0),
                native_poison=oracle[who]['poisoned'], lite_poison=forecast[who]['poisoned'],
                native_slow=oracle[who]['slowed'], lite_slow=forecast[who]['slowed'])
                for who in ('attacker', 'defender')}
            rows.append(dict(name=name, metrics=metrics,
                             native_counter=oracle['defender_weapon']))
            print(json.dumps(rows[-1]), flush=True)
        executable_hash = native.executable_hash
        transport_hash = native.source_hash
    result = dict(source=args.source, rules_sha256=hashlib.sha256(raw).hexdigest(),
                  executable_sha256=executable_hash, transport_sha256=transport_hash,
                  seconds=time.monotonic()-started, cases=rows,
                  scope='Six fixed public battles: full HP/status probability parity at 1e-9. No training or strength claim.')
    (args.output/'summary.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
