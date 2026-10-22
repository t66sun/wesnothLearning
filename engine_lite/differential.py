"""Bounded native 1.18.8/lite rule audit; no training or installed add-on changes.

python -m engine_lite.differential --wesnoth /opt/wesnoth-1.18.8/bin/wesnoth \
    --rules rules/1.18.8 --output verification/native-differential

Native executes one real battle per case and exports its exact combat distribution.
Actual native hit/miss events drive deterministic lite replay. Independent lite RNG
samples are compared to that native distribution, avoiding thousands of restarts.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import time

from learning.adapters import LiteAdapter
from learning.native_transport import NativeTransport

DEFAULT_MINIMUM_SAMPLES = 512
DEFAULT_MAXIMUM_SAMPLES = 2048


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


def wilson(successes, count):
    if not count:
        return [0., 1.]
    p, z = successes / count, 1.959963984540054
    den = 1 + z*z/count
    middle = (p + z*z/(2*count))/den
    radius = z*math.sqrt(p*(1-p)/count + z*z/(4*count*count))/den
    return [max(0., middle-radius), min(1., middle+radius)]


def _probability(successes, count, expected):
    interval = wilson(successes, count)
    error = abs(successes/count-expected)
    upper = max(abs(x-expected) for x in interval)
    status = _interval_status(interval, expected, .01)
    return dict(native=expected, lite=successes/count, error=error, ci95=interval,
                error_upper95=upper, passed=status == 'passed', status=status)


def _interval_status(interval, expected, tolerance):
    low, high = interval
    if low >= expected-tolerance and high <= expected+tolerance:
        return 'passed'
    if high < expected-tolerance or low > expected+tolerance:
        return 'failed'
    return 'inconclusive'


def _combined_status(results):
    statuses = [item.get('status', 'passed' if item['passed'] else 'failed') for item in results]
    return 'failed' if 'failed' in statuses else 'inconclusive' if 'inconclusive' in statuses else 'passed'


def statistics(lite, spec, action, oracle, *, minimum=DEFAULT_MINIMUM_SAMPLES,
               maximum=DEFAULT_MAXIMUM_SAMPLES):
    """Increase only when the 1 pp/0.5 HP bound needs more evidence."""
    count = 0
    sums = {who: dict(hp=0., hp2=0., dead=0, poisoned=0, slowed=0, hits=0, blows=0)
            for who in ('attacker', 'defender')}
    target = minimum
    while True:
        while count < target:
            trial = dict(spec, seed=spec['seed']+count+1)
            lite.reset(trial)
            outcome = lite.step(action)
            units = {u['id']: u for u in lite.observe(1)['units']}
            for who in sums:
                value = sums[who]
                u = units.get(who)
                hp = u['hp'] if u else 0
                value['hp'] += hp
                value['hp2'] += hp*hp
                value['dead'] += hp == 0
                for status in ('poisoned', 'slowed'):
                    value[status] += bool(u and status in u['status'])
            for strike in outcome['strikes']:
                value = sums[strike['attacker']]
                value['hits'] += strike['hit']
                value['blows'] += 1
            count += 1
        metrics = {}
        for who, value in sums.items():
            expected = oracle[who]
            mean = value['hp']/count
            variance = max(0., value['hp2']/count-mean*mean)
            half = 1.959963984540054*math.sqrt(variance/count)
            native_variance = sum(float(p)*(int(hp)-expected['average_hp'])**2
                                  for hp, p in expected['hp_chance'].items())
            hp_status = _interval_status([mean-half, mean+half], expected['average_hp'], .5)
            metrics[who] = dict(
                hp=dict(native=expected['average_hp'], lite=mean, variance=variance,
                        native_variance=native_variance, ci95=[mean-half, mean+half],
                        error=abs(mean-expected['average_hp']),
                        passed=hp_status == 'passed', status=hp_status),
                death=_probability(value['dead'], count, expected['hp_chance'].get('0', 0.)),
                poisoned=_probability(value['poisoned'], count, expected['poisoned']),
                slowed=_probability(value['slowed'], count, expected['slowed']),
                hit=_probability(value['hits'], value['blows'], oracle[who+'_hit'])
                    if value['blows'] else dict(passed=True, not_applicable='no retaliation'))
        status = _combined_status([metric for row in metrics.values() for metric in row.values()])
        if status != 'inconclusive' or target == maximum:
            return dict(samples=count, passed=status == 'passed', status=status, metrics=metrics,
                        confidence='individual 95% Wilson probability / normal HP mean intervals; native oracle is exact engine simulation')
        target = min(maximum, target*2)


def combat_case(native, lite, rules, case, minimum, maximum):
    name, attacker, defender, weapon = case
    spec = game_spec(rules, attacker, defender)
    # Make healing by drains observable even when the attacker receives no retaliation.
    if name == 'drains':
        spec['units'][2]['hp'] = max(1, spec['units'][2]['hp']-8)
    action = dict(kind='attack', unit='attacker', target='defender', weapon=weapon)
    native.reset(spec)
    lite.reset(spec)
    initial = _compare('initial', _state(native.observe(1)), _state(lite.observe(1)))
    result = native.step(action)
    probe = result['differential']
    lite.inject_hits(strike['hit'] for strike in probe['strikes'])
    outcome = lite.step(action)
    native_strikes = [{k: s[k] for k in ('attacker', 'defender', 'hit', 'defender_hp')}
                      for s in probe['strikes']]
    lite_strikes = [{k: s[k] for k in ('attacker', 'defender', 'hit', 'defender_hp')}
                    for s in outcome['strikes']]
    differences = initial + _compare('injected battle', {'strikes': native_strikes}, {'strikes': lite_strikes})
    differences += _compare('post battle', _units(native.observe(1)), _units(lite.observe(1)))
    if differences:
        stats = dict(samples=0, passed=False, status='not_run',
                     reason='deterministic state/strike mismatch; fix it before statistical sampling')
    else:
        stats = statistics(lite, spec, action, probe['oracle'], minimum=minimum, maximum=maximum)
    status = 'failed' if differences else stats['status']
    return dict(name=name, passed=status == 'passed', status=status, differences=differences,
                native_actual=probe, statistics=stats)


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
    parser.add_argument('--rules', type=Path, default=Path('rules/1.18.8'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--minimum-samples', type=int, default=DEFAULT_MINIMUM_SAMPLES,
                        help='initial samples per combat (default: 512; formal audit: 16384)')
    parser.add_argument('--maximum-samples', type=int, default=DEFAULT_MAXIMUM_SAMPLES,
                        help='sample cap per combat (default: 2048; formal audit: 65536)')
    parser.add_argument('--case', action='append', choices=[c[0] for c in COMBATS])
    parser.add_argument('--skip-state', action='store_true')
    args = parser.parse_args(argv)
    if not 1 <= args.minimum_samples <= args.maximum_samples:
        parser.error('samples must satisfy 1 <= minimum <= maximum')
    args.output.mkdir(parents=True, exist_ok=True)
    rules_bytes = (args.rules/'rules.json').read_bytes()
    rules = json.loads(rules_bytes)
    start = time.monotonic()
    report = dict(kind='native_lite_differential_v1', rules_sha256=hashlib.sha256(rules_bytes).hexdigest(),
                  cases=[], probability_tolerance=.01, mean_hp_tolerance=.5,
                  minimum_samples=args.minimum_samples, maximum_samples=args.maximum_samples)
    lite = LiteAdapter(game_spec(rules), rules_dir=args.rules, require_accepted=False)
    with NativeTransport(wesnoth=args.wesnoth, timeout=60, startup_timeout=120) as native:
        if not args.skip_state:
            report['cases'].extend(state_cases(native, lite, rules))
        for case in COMBATS:
            if args.case and case[0] not in args.case:
                continue
            result = combat_case(native, lite, rules, case, args.minimum_samples, args.maximum_samples)
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
    lines += ['', 'The JSON contains real native strike traces, injected replay differences, native exact distributions,',
              'lite sample counts and individual 95% confidence intervals. This is a representative rule audit,',
              'not a claim that arbitrary campaign scripts are supported.', '']
    (args.output/'REPORT.md').write_text('\n'.join(lines), encoding='utf-8')
    return {'passed': 0, 'failed': 1, 'inconclusive': 2}[report['status']]


if __name__ == '__main__':
    raise SystemExit(main())
