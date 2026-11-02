"""Regress slow valuation with and without an unrelated remote threat."""
import argparse
import hashlib
import json
from pathlib import Path
import time
from unittest.mock import patch

from _engine_lite import LiteEngine
from engine_lite.differential import unit
from learning.common import ROOT
from learning.lite_host import host_modules
from learning.native_transport import NativeTransport
from learning.teachers import identity
from tests.diagnose_teacher_boards import board, write


def position(rules, remote):
    spec = board(rules, 'slow_weapon', 'duel')
    spec['units'][2] = unit(rules, 'attacker', 'Elvish Enchantress', 1, 84)
    spec['units'][3] = unit(rules, 'defender', 'Dwarvish Steelclad', 2, 85)
    if remote:
        spec['units'].append(unit(rules, 'remote', 'Troll Warrior', 2, 122))
    for item in spec['units']:
        item['moves'] = 0
    return spec


def details(decision, legal):
    plan = dict(decision['teacher_action'])
    trace = plan.pop('score_trace')
    for row in trace:
        p = row['parameters']
        row['danger_cost_margin'] = p['risk'] * p['risk_weight'] - p['expected_hp'] + 6
    action = dict(kind='attack', unit=plan['id'], target=plan['enemy'], weapon=plan['weapon'] - 1)
    return dict(plan=plan, trace=trace, legal=action in legal, legal_actions=legal,
                teacher_error=decision.get('teacher_skipped'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rules', type=Path, required=True)
    parser.add_argument('--wesnoth', required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    raw = (args.rules / 'rules.json').read_bytes()
    rules = json.loads(raw)
    modules = host_modules()
    wrapper = (ROOT / 'tests/fixtures/teacher_score_trace.lua').read_text()
    modules['astra/duel.lua'] = 'local teacher=(function()\n' + modules['astra/duel.lua'] + '\nend)()\n' + wrapper
    rows = {}
    started = time.monotonic()
    with patch('learning.lite_host.host_modules', return_value=modules):
        with NativeTransport(wesnoth=args.wesnoth, timeout=30, startup_timeout=120) as native:
            for name, remote in (('alone', False), ('remote_threat', True)):
                spec = position(rules, remote)
                lite = LiteEngine(raw.decode(), json.dumps(spec))
                lite.configure_host(json.dumps(modules))
                lite_decision = json.loads(lite.decision(1, True))
                native.reset(spec)
                native_decision = native.decision(1, teacher=True)
                rows[name] = dict(spec=spec,
                    lite=details(lite_decision, json.loads(lite.legal_actions(1))),
                    native=details(native_decision, native.legal_actions(1)))
                write(args.output / f'{name}.json', rows[name])
            native_hash = native.executable_hash
    comparisons = {}
    for backend in ('native', 'lite'):
        before, after = rows['alone'][backend], rows['remote_threat'][backend]
        earlier = {row['weapon']: row for row in before['trace']}
        later = {row['weapon']: row for row in after['trace']}
        comparisons[backend] = dict(
            before_weapon=before['plan']['weapon'], after_weapon=after['plan']['weapon'],
            weapon_changed=before['plan']['weapon'] != after['plan']['weapon'],
            same_target_and_landing=all(before['plan'][key] == after['plan'][key]
                                        for key in ('id', 'enemy', 'tx', 'ty')),
            ranged_forecasts_equal=all(earlier[w]['forecast'] == later[w]['forecast'] for w in (2, 3)),
            target_damage_estimates_equal=all(earlier[w]['target_damage_estimate'] == later[w]['target_damage_estimate']
                                              for w in (2, 3)),
            ranged_danger_cost_inactive=all(row['danger_cost_margin'] <= 0
                                             for table in (earlier, later) for w, row in table.items() if w in (2, 3)),
            all_choices_legal=before['legal'] and after['legal'],
            remote_not_attackable=not any(action.get('target') == 'remote' for action in after['legal_actions']))
    summary = dict(source=args.source, teacher=identity(), rules_sha256=hashlib.sha256(raw).hexdigest(),
                   native_executable_sha256=native_hash, wall_seconds=time.monotonic() - started,
                   comparisons=comparisons,
                   limits='Two fixed first-decision boards; weapon stability only, not strength acceptance.')
    write(args.output / 'summary.json', summary)
    print(json.dumps(summary, indent=2), flush=True)
    for result in comparisons.values():
        for key in ('same_target_and_landing', 'ranged_forecasts_equal', 'target_damage_estimates_equal',
                    'ranged_danger_cost_inactive', 'all_choices_legal', 'remote_not_attackable'):
            assert result[key], (key, result)
    assert all(result['before_weapon'] == result['after_weapon'] == 3
               for result in comparisons.values()), comparisons


if __name__ == '__main__':
    main()
