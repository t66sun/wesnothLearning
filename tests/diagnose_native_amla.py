"""Fixed native standard AMLA comparisons, without collection or training."""
import argparse
import hashlib
import json
from pathlib import Path

from engine_lite.differential import game_spec
from learning.adapters import LiteAdapter
from learning.native_transport import NativeTransport
from tests.v5.test_amla_declarations import standard


CASES = [('attacker', False, 0, 100, 1), ('defender', True, 0, 100, 1),
         ('kill', False, 0, 100, 8), ('repeat', False, 1, 100, 1),
         ('training_repeat', False, 3, 70, 1)]


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
    with NativeTransport(wesnoth=args.wesnoth, timeout=30, startup_timeout=120) as native:
        for name, defending, count, modifier, gap in CASES:
            spec = game_spec(rules, 'Elvish Shaman' if defending else 'Elvish Champion',
                             'Elvish Champion' if defending else 'Orcish Grunt')
            spec['experience_modifier'] = modifier
            index = 3 if defending else 2
            champion = spec['units'][index]
            definition = rules['units']['Elvish Champion']
            required = (definition['experience']*modifier+50)//100
            for _ in range(count):
                required += (required*20+50)//100
            champion.update(hp=20, xp=required-gap, amla_count=count,
                resolved_max_hp=definition['hp']+3*count, resolved_max_experience=required,
                status=['poisoned', 'slowed'])
            if gap == 8:
                spec['units'][3]['hp'] = 1
            if count:
                cfg = dict(id=champion['id'], type=champion['unit_type'], side=champion['side'],
                    x=champion['pos']%7+1, y=champion['pos']//7+1, hitpoints=20,
                    experience=champion['xp'], moves=champion['moves'], attacks_left=1,
                    random_traits=False, random_gender=False, generate_name=False)
                def native_wml(value):
                    if not isinstance(value, dict):
                        return value
                    return {int(k) if k.isdecimal() else k: native_wml(v) for k, v in value.items()}
                declaration = native_wml(standard()['1']['2'])
                cfg[1] = ['modifications', [['advancement', declaration] for _ in range(count)]]
                champion['native_cfg'] = cfg
            for side in spec['sides']:
                side['gold'] = 0
            action = dict(kind='attack', unit='attacker', target='defender', weapon=1 if defending else 0)
            native.reset(spec)
            lite = LiteAdapter(spec, rules_dir=args.rules, require_accepted=False)
            initial = {'native': native.observe(1), 'lite': lite.observe(1)}
            predicted = lite.forecast(1, 'attacker', 'defender', action['weapon'])
            nr, lr = native.step(action), lite.step(action)
            after = {'native': native.observe(1), 'lite': lite.observe(1)}
            row = dict(name=name, spec=spec, initial=initial, after=after,
                       native=nr, lite=lr, forecast=predicted)
            (args.output/(name+'.json')).write_text(json.dumps(row, indent=2)+'\n')
            for side in ('attacker', 'defender'):
                oracle = nr['differential']['oracle'][side]
                for metric in ('average_hp', 'poisoned', 'slowed'):
                    assert abs(oracle[metric]-predicted[side][metric]) < 1e-9, (name, side, metric)
                for hp in set(oracle['hp_chance']) | set(predicted[side]['hp_chance']):
                    assert abs(oracle['hp_chance'].get(hp, 0)-predicted[side]['hp_chance'].get(hp, 0)) < 1e-9
            summary = {}
            for backend, view in after.items():
                alive = {u['id']: u for u in view['units']}
                actor = alive.get(champion['id'])
                assert actor is not None, (name, backend, 'champion must survive this fixture')
                enemy = spec['units'][2 if defending else 3]
                level = rules['units'][enemy['unit_type']]['level']
                gain = (8*level if level else 4) if enemy['id'] not in alive else level
                advanced = champion['xp']+gain >= required
                expected_hp = definition['hp']+3*(count+int(advanced))
                expected_xp = champion['xp']+gain-(required if advanced else 0)
                self_max = actor['resolved_max_hp']
                assert self_max == expected_hp, (name, backend, 'max_hp', self_max, expected_hp)
                assert actor['xp'] == expected_xp, (name, backend, 'xp')
                next_required = required+(required*20+50)//100 if advanced else required
                assert actor['resolved_max_experience'] == next_required, (name, backend, 'max_xp')
                if advanced:
                    assert actor['hp'] == expected_hp and not set(actor['status']) & {'poisoned', 'slowed'}, (name, backend)
                summary[backend] = dict(advanced=advanced, hp=actor['hp'], xp=actor['xp'], max_xp=next_required)
            rows.append(dict(name=name, result=summary))
            print(json.dumps(rows[-1]), flush=True)
            lite.close()
        result = dict(source=args.source, rules_sha256=hashlib.sha256(raw).hexdigest(),
            native_sha256=native.executable_hash, transport_sha256=native.source_hash, cases=rows)
    (args.output/'summary.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
