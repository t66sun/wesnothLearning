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
    ('berserk', 'Dwarvish Ulfserker', 'Orcish Grunt', 0, None, None),
    ('drain', 'Ghost', 'Elvish Fighter', 0, 12, None),
    ('slow_retaliation', 'Elvish Shaman', 'Elvish Archer', 1, None, None),
    ('ranged_without_retaliation', 'Mage', 'Orcish Grunt', 1, None, None),
    ('lethal_poison', 'Orcish Assassin', 'Elvish Fighter', 1, None, 1),
    ('lethal_slow', 'Elvish Shaman', 'Orcish Grunt', 1, None, 1),
    ('poison_before_death', 'Orcish Assassin', 'Elvish Fighter', 1, None, 5),
    ('slow_before_death', 'Elvish Shaman', 'Orcish Grunt', 1, None, 5),
    ('combat_advancement', 'Elvish Fighter', 'Orcish Grunt', 0, 20, None),
    ('kill_advancement', 'Elvish Fighter', 'Orcish Grunt', 0, 20, 14),
    ('defender_advancement', 'Orcish Assassin', 'Elvish Fighter', 1, None, 20),
    ('slow_advancement', 'Elvish Shaman', 'Orcish Grunt', 1, None, 20),
    ('poison_kill_advancement', 'Elvish Fighter', 'Orcish Assassin', 1, 20, 6),
    ('slow_kill_advancement', 'Elvish Fighter', 'Elvish Shaman', 1, 20, 6),
    ('mutual_advancement', 'Elvish Fighter', 'Orcish Grunt', 0, 8, 1),
    ('firststrike', 'Elvish Fighter', 'Drake Clasher', 0, None, None),
    ('marksman', 'Elvish Sharpshooter', 'Elvish Archer', 1, None, None),
    ('charge', 'Horseman', 'Orcish Grunt', 0, None, None),
    ('backstab', 'Thief', 'Orcish Grunt', 0, None, None),
    ('backstab_ffa', 'Thief', 'Orcish Grunt', 0, None, None),
    ('backstab_petrified', 'Thief', 'Orcish Grunt', 0, None, None),
    ('level_zero_kill', 'Elvish Fighter', 'Goblin Spearman', 0, 20, 1),
    ('immune_poison', 'Orcish Assassin', 'Elvish Fighter', 1, None, None),
    ('immune_drain', 'Ghost', 'Elvish Fighter', 0, 12, None),
    ('immune_plague', 'Walking Corpse', 'Mage', 0, None, 1),
    ('immune_counter_poison', 'Elvish Fighter', 'Orcish Assassin', 1, None, None),
    ('immune_counter_drain', 'Elvish Fighter', 'Ghost', 0, None, 12),
    ('immune_counter_plague', 'Elvish Fighter', 'Walking Corpse', 0, 1, None),
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rules', type=Path, required=True)
    parser.add_argument('--wesnoth', required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', action='append', choices=[c[0] for c in CASES])
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    raw = (args.rules/'rules.json').read_bytes()
    rules = json.loads(raw)
    rows, failures = [], []
    started = time.monotonic()
    with NativeTransport(wesnoth=args.wesnoth, timeout=30, startup_timeout=120) as native:
        for name, attacker, defender, weapon, attacker_hp, defender_hp in CASES:
            if args.case and name not in args.case:
                continue
            spec = game_spec(rules, attacker, defender)
            if name.startswith('immune_'):
                flag = {'poison': 'unpoisonable', 'drain': 'undrainable', 'plague': 'unplagueable'}[name.rsplit('_', 1)[1]]
                victim = spec['units'][2 if 'counter' in name else 3]
                victim['status'] = [flag]
                if name.endswith('plague'):
                    # Native and Lite have different rolls. Deep water gives these
                    # land units 100% hit chance, so both exercise the lethal branch.
                    spec['terrain'][victim['pos']] = 'Wo'
                    assert rules['units'][victim['unit_type']]['defense']['Wo'] == 100
            for index, gap in {
                'combat_advancement': ((2, 1),), 'kill_advancement': ((2, 8),),
                'defender_advancement': ((3, 1),), 'slow_advancement': ((3, 1),),
                'poison_kill_advancement': ((2, 8),), 'slow_kill_advancement': ((2, 8),),
                'level_zero_kill': ((2, 5),), 'mutual_advancement': ((2, 8), (3, 8)),
            }.get(name, ()):
                unit = spec['units'][index]
                unit['xp'] = rules['units'][unit['unit_type']]['experience'] - gap
            if name.startswith('backstab'):
                flanker = dict(id='flanker', unit_type='Elvish Fighter', side=1, pos=32,
                               hp=rules['units']['Elvish Fighter']['hp'], moves=0,
                               attacks_left=0, xp=0, leader=False, status=[], traits=[])
                if name == 'backstab_ffa':
                    for side_id, pos in ((3, 42), (4, 44)):
                        spec['sides'].append(dict(spec['sides'][1], id=side_id, team=str(side_id)))
                        spec['units'].append(dict(flanker, id=f'leader{side_id}', side=side_id, pos=pos, leader=True))
                    flanker['side'] = 3
                if name == 'backstab_petrified':
                    flanker['status'] = ['petrified']
                spec['units'].append(flanker)
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
            snapshot = lite.snapshot()
            started_forecasts = time.perf_counter()
            for _ in range(100):
                assert lite.forecast(1, 'attacker', 'defender', weapon) == forecast
            forecast_us = (time.perf_counter()-started_forecasts)*10000
            assert lite.snapshot() == snapshot
            native_result = native.step(action)
            lite_result = lite.step(action)
            row = dict(name=name, spec=spec, action=action, initial=before,
                       legal=dict(native=native_legal, lite=lite_legal),
                       native=native_result['differential'], lite_forecast=forecast,
                       lite_actual=lite_result)
            after_units = lite.observe(1)['units']
            row['after'] = dict(native=native.observe(1)['units'], lite=after_units)
            if name.startswith('immune_'):
                victim = spec['units'][2 if 'counter' in name else 3]
                for backend, units in row['after'].items():
                    alive = next((u for u in units if u['id'] == victim['id']), None)
                    if name.endswith('poison'):
                        assert not alive or 'poisoned' not in alive['status'], (name, backend)
                    if name.endswith('plague'):
                        assert alive is None, (name, backend, 'fixture must exercise lethal plague')
                        assert not any(u['pos'] == victim['pos'] for u in units), (name, backend, 'immune victim converted')
            # Validate each sampled outcome against its own opponent outcome;
            # the two engines intentionally use different random streams.
            for backend, units in row['after'].items():
                alive = {u['id']: u for u in units}
                for index, enemy_index in ((2, 3), (3, 2)):
                    initial = spec['units'][index]
                    current = alive.get(initial['id'])
                    if current is None:
                        continue
                    enemy = spec['units'][enemy_index]
                    level = rules['units'][enemy['unit_type']]['level']
                    gain = (8*level if level else 4) if enemy['id'] not in alive else level
                    xp = initial['xp'] + gain
                    definition = rules['units'][initial['unit_type']]
                    if xp >= definition['experience'] and definition['advances_to']:
                        xp -= definition['experience']
                        if current['unit_type'] not in definition['advances_to']:
                            failures.append((name, backend, initial['id'], 'missing advancement'))
                        if set(current['status']) & {'poisoned', 'slowed'}:
                            failures.append((name, backend, initial['id'], 'advancement kept debuff'))
                    if current['xp'] != xp:
                        failures.append((name, backend, initial['id'], 'experience', xp, current['xp']))
            for who, index in (('attacker', 2), ('defender', 3)):
                after = next((u for u in after_units if u['id'] == who), None)
                # Native prediction heals to the original max HP; execution chooses a new type.
                hp = after['hp'] if after else 0
                if after and after['unit_type'] != spec['units'][index]['unit_type']:
                    hp = rules['units'][spec['units'][index]['unit_type']]['hp']
                if forecast[who]['hp_chance'].get(str(hp), 0) <= 0:
                    failures.append((name, who, 'actual outside forecast support', hp))
            lite.close()
            (args.output/(name+'.json')).write_text(json.dumps(row, indent=2)+'\n')
            oracle = row['native']['oracle']
            if name.startswith('backstab'):
                expected_damage = 4 if name == 'backstab_petrified' else 8
                assert oracle['attacker_weapon']['damage'] == expected_damage, (name, 'backstab activation')
            for who in ('attacker', 'defender'):
                for metric in ('average_hp', 'poisoned', 'slowed'):
                    if abs(oracle[who][metric]-forecast[who][metric]) >= 1e-9:
                        failures.append((name, who, metric, oracle[who][metric], forecast[who][metric]))
                nh, lh = oracle[who]['hp_chance'], forecast[who]['hp_chance']
                for hp in set(nh) | set(lh):
                    if abs(nh.get(hp, 0)-lh.get(hp, 0)) >= 1e-9:
                        failures.append((name, who, 'hp '+hp, nh.get(hp, 0), lh.get(hp, 0)))
            metrics = {who: dict(native_mean_hp=oracle[who]['average_hp'],
                lite_hp=forecast[who]['average_hp'], native_death=oracle[who]['hp_chance'].get('0', 0),
                lite_death=forecast[who]['hp_chance'].get('0', 0),
                native_poison=oracle[who]['poisoned'], lite_poison=forecast[who]['poisoned'],
                native_slow=oracle[who]['slowed'], lite_slow=forecast[who]['slowed'])
                for who in ('attacker', 'defender')}
            rows.append(dict(name=name, metrics=metrics, forecast_us=forecast_us,
                             native_counter=oracle['defender_weapon']))
            print(json.dumps(rows[-1]), flush=True)
        executable_hash = native.executable_hash
        transport_hash = native.source_hash
    result = dict(source=args.source, rules_sha256=hashlib.sha256(raw).hexdigest(),
                  executable_sha256=executable_hash, transport_sha256=transport_hash,
                  seconds=time.monotonic()-started, cases=rows,
                  failures=failures,
                  scope='Fixed public battles: full HP/status probability parity at 1e-9. No training or strength claim.')
    (args.output/'summary.json').write_text(json.dumps(result, indent=2)+'\n')
    assert not failures, failures


if __name__ == '__main__':
    main()
