"""Bounded native 1.18.8/lite rule audit; no training or installed add-on changes.

python -m engine_lite.differential --wesnoth /opt/wesnoth-1.18.8/bin/wesnoth \
    --rules data/rules/1.18.8 --output verification/native-differential

Native executes one real battle per case. Lite runs the same state through the
deterministic `expected_damage_v1` rules; the native random rolls are recorded but
are not treated as an oracle for damage, statuses or death timing.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import time

from learning.adapters import LiteAdapter
from learning.native_transport import NativeTransport

COMBATS = (
    ('ordinary', 'Elvish Fighter', 'Orcish Grunt', 0),
    ('resistance', 'Elvish Fighter', 'Skeleton', 0),
    ('magical', 'Mage', 'Elvish Fighter', 1),
    ('poison', 'Orcish Assassin', 'Elvish Fighter', 1),
    ('slow', 'Elvish Shaman', 'Orcish Grunt', 1),
    ('drains', 'Ghost', 'Orcish Grunt', 0),
    ('charge', 'Horseman', 'Orcish Grunt', 0),
    ('firststrike', 'Orcish Grunt', 'Spearman', 0),
)


def unit(rules, identifier, kind, side, pos, *, leader=False, hp=None, status=()):
    data = rules['units'][kind]
    return dict(id=identifier, unit_type=kind, side=side, pos=pos,
                hp=data['hp'] if hp is None else hp, moves=data['moves'],
                attacks_left=1, xp=0, leader=leader, status=list(status), traits=[])


def game_spec(rules, attacker='Elvish Fighter', defender='Orcish Grunt'):
    terrain = ['Gg'] * 49
    terrain[0], terrain[1], terrain[8] = 'Kh', 'Ch', 'Gg^Vh'
    sides = [dict(id=i, team=str(i), faction=faction, gold=100, base_income=2,
                  recruit=['Elvish Fighter'] if i == 1 else ['Orcish Grunt'],
                  fog=False, shroud=False, share_view=False, share_maps=False)
             for i, faction in ((1, 'Rebels'), (2, 'Northerners'))]
    return dict(width=7, height=7, terrain=terrain, sides=sides,
                units=[unit(rules, 'leader1', 'Elvish Captain', 1, 0, leader=True),
                       unit(rules, 'leader2', 'Orcish Warrior', 2, 48, leader=True),
                       unit(rules, 'attacker', attacker, 1, 23),
                       unit(rules, 'defender', defender, 2, 24)],
                village_owner={}, seed=713, max_turns=4, experience_modifier=100,
                allow_approximate=True, differential_probe=True)


def _units(view):
    return {u['id']: (u['unit_type'], u['side'], u['pos'], u['hp'], u['moves'],
                       u['attacks_left'], u['xp'], sorted(u['status']))
            for u in view['units']}


def _state(view):
    return {key: view[key] for key in ('turn', 'current_side', 'terrain', 'visible', 'explored')} | {
        'units': _units(view), 'villages': view['villages'],
        'sides': [{k: s.get(k) for k in ('id', 'team', 'gold', 'recruit', 'total_income')}
                  for s in view['sides']]}


def _compare(label, native, lite):
    differences = []
    for key in sorted(set(native) | set(lite)):
        if native.get(key) != lite.get(key):
            differences.append(dict(check=label, field=key, native=native.get(key), lite=lite.get(key)))
    return differences


def _combined_status(results):
    statuses = [item.get('status', 'passed' if item['passed'] else 'failed') for item in results]
    if 'failed' in statuses:
        return 'failed'
    if 'inconclusive' in statuses:
        return 'inconclusive'
    if 'expected_difference' in statuses:
        return 'expected_difference'
    return 'passed'


def combat_case(native, lite, rules, case):
    """Record a native battle and the deterministic lite battle for the same state.

    Native resolves every strike with a random roll, so its damage, statuses and
    death turn are not an oracle for `expected_damage_v1`. The rule-invariant
    comparison is the strike order (who strikes first, and the alternation) up to
    the first death; damage and status deltas are recorded as expected differences
    instead of being reported as parity or as a failed gate.
    """
    name, attacker, defender, weapon = case
    spec = game_spec(rules, attacker, defender)
    # Make healing by drains observable even when the attacker receives no retaliation.
    if name == 'drains':
        spec['units'][2]['hp'] = max(1, spec['units'][2]['hp']-8)
    action = dict(kind='attack', unit='attacker', target='defender', weapon=weapon)
    native.reset(spec)
    lite.reset(spec)
    differences = _compare('initial', _state(native.observe(1)), _state(lite.observe(1)))
    probe = native.step(action)['differential']
    outcome = lite.step(action)
    native_strikes = probe.get('strikes', [])
    lite_strikes = outcome.get('strikes', [])
    native_order = [(s['attacker'], s['defender']) for s in native_strikes]
    lite_order = [(s['attacker'], s['defender']) for s in lite_strikes]
    shared = min(len(native_order), len(lite_order))
    if native_order[:shared] != lite_order[:shared]:
        differences.append(dict(check='strike order', native=native_order, lite=lite_order))
    expected = []
    for label, native_row, lite_row in zip(('strike '+str(i) for i in range(shared)),
                                           native_strikes, lite_strikes):
        delta = {key: dict(native=native_row.get(key), lite=lite_row.get(key))
                 for key in ('hit', 'chance', 'damage', 'defender_hp')
                 if native_row.get(key) != lite_row.get(key)}
        if delta:
            expected.append(dict(check=label, difference=delta))
    native_units = _units(native.observe(1))
    lite_units = _units(lite.observe(1))
    for unit_id in sorted(set(native_units) | set(lite_units)):
        if native_units.get(unit_id) != lite_units.get(unit_id):
            expected.append(dict(check='post battle unit '+unit_id,
                                 native=native_units.get(unit_id), lite=lite_units.get(unit_id)))
    return dict(name=name, passed=not differences,
                status='failed' if differences else 'expected_difference',
                differences=differences, expected_differences=expected,
                native_actual=probe, lite_actual=outcome,
                rule_profile='expected_damage_v1',
                note='native stochastic strikes are not an oracle for deterministic expected damage')


def state_cases(native, lite, rules):
    results = []
    spec = game_spec(rules)
    # Neutral village capture, movement consumption, healing, refresh and economy.
    spec['units'][2] = unit(rules, 'attacker', 'Elvish Fighter', 1, 15, hp=20)
    native.reset(spec); lite.reset(spec)
    differences = _compare('initial legal actions',
        {'actions': sorted(json.dumps(a, sort_keys=True) for a in native.legal_actions(1))},
        {'actions': sorted(json.dumps(a, sort_keys=True) for a in lite.legal_actions(1))})
    for action in (dict(kind='move', unit='attacker', to=8, full=False),
                   dict(kind='end_turn'), dict(kind='end_turn')):
        native.step(action); lite.step(action)
        differences += _compare(str(action), _state(native.observe(1)), _state(lite.observe(1)))
    results.append(dict(name='move_village_heal_income', passed=not differences, differences=differences))
    # IDs and random recruit traits differ. Compare the purchased base unit/cost,
    # while ensuring deterministic no-trait recruitment is not claimed here.
    spec = game_spec(rules); native.reset(spec); lite.reset(spec)
    action = dict(kind='recruit', unit_type='Elvish Fighter', to=1)
    native.step(action); lite.step(action)
    nv, lv = native.observe(1), lite.observe(1)
    def purchase(view):
        return dict(gold=view['sides'][0]['gold'],
                    recruits=[(u['unit_type'], u['side'], u['pos'], u['moves'], u['attacks_left'])
                              for u in view['units'] if u['pos'] == 1])
    differences = _compare('recruit purchase', purchase(nv), purchase(lv))
    results.append(dict(name='recruit_cost_and_consumption', passed=not differences, differences=differences,
                        excluded='native random recruitment traits require a separate injected-trait contract'))
    spec = game_spec(rules)
    spec['sides'][0].update(fog=True, shroud=True)
    spec['sides'][1].update(fog=True, shroud=True)
    native.reset(spec); lite.reset(spec)
    differences = _compare('fog/shroud player view', _state(native.observe(1)), _state(lite.observe(1)))
    results.append(dict(name='fog_shroud', passed=not differences, differences=differences))
    for share in (False, True):
        spec = game_spec(rules)
        spec['sides'] += [dict(spec['sides'][0], id=3), dict(spec['sides'][1], id=4)]
        for side in spec['sides']:
            side.update(team=str(side['id'] % 2), fog=True, shroud=True,
                        share_view=share, share_maps=share)
        spec['units'] += [unit(rules, 'leader3', 'Elvish Captain', 3, 6, leader=True),
                          unit(rules, 'leader4', 'Orcish Warrior', 4, 42, leader=True)]
        native.reset(spec); lite.reset(spec)
        differences = _compare('team sharing '+str(share), _state(native.observe(1)), _state(lite.observe(1)))
        for _ in range(4):
            native.step(dict(kind='end_turn')); lite.step(dict(kind='end_turn'))
        differences += _compare('four-side round', _state(native.observe(1)), _state(lite.observe(1)))
        results.append(dict(name='team_sharing_'+str(share).lower(), passed=not differences, differences=differences))
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wesnoth', required=True)
    parser.add_argument('--rules', type=Path, default=Path('data/rules/1.18.8'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', action='append', choices=[c[0] for c in COMBATS])
    parser.add_argument('--skip-state', action='store_true')
    args = parser.parse_args(argv)
    args.output.mkdir(parents=True, exist_ok=True)
    rules_bytes = (args.rules/'rules.json').read_bytes()
    rules = json.loads(rules_bytes)
    start = time.monotonic()
    report = dict(kind='native_lite_differential_v1', rules_sha256=hashlib.sha256(rules_bytes).hexdigest(),
                  cases=[], combat_version='expected_damage_v1')
    lite = LiteAdapter(game_spec(rules), rules_dir=args.rules, require_accepted=False)
    with NativeTransport(wesnoth=args.wesnoth, timeout=60, startup_timeout=120) as native:
        if not args.skip_state:
            report['cases'].extend(state_cases(native, lite, rules))
        for case in COMBATS:
            if args.case and case[0] not in args.case:
                continue
            result = combat_case(native, lite, rules, case)
            report['cases'].append(result)
            print(case[0], result['status'], flush=True)
        report['native_executable_sha256'] = native.executable_hash
    report['wall_seconds'] = time.monotonic()-start
    report['status'] = _combined_status(report['cases']) if report['cases'] else 'inconclusive'
    report['passed'] = report['status'] == 'passed'
    (args.output/'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    lines = ['# Native/lite differential', '', f"Result: {report['status']}", '',
             '| Case | Result |', '|---|---|']
    lines += [f"| {c['name']} | {c.get('status', 'passed' if c['passed'] else 'failed')} |" for c in report['cases']]
    lines += ['', 'The JSON contains real native strike traces and the deterministic lite battle for the same',
              'state. Native random rolls are not an oracle for `expected_damage_v1`: damage, status and',
              'death deltas are recorded as expected differences, and only strike order is compared.',
              'This is a representative rule audit, not a claim that arbitrary campaign scripts are supported.', '']
    (args.output/'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
    return {'passed': 0, 'failed': 1, 'expected_difference': 2, 'inconclusive': 2}[report['status']]


if __name__ == '__main__':
    raise SystemExit(main())
