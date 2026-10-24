import unittest
from pathlib import Path
from unittest import mock

from engine_lite.differential import _combined_status, combat_case


def strike(attacker, defender, *, hit=True, chance=60, damage=7, defender_hp=13):
    return dict(attacker=attacker, defender=defender, hit=hit, chance=chance,
                damage=damage, defender_hp=defender_hp)


def run(native_strikes, lite_strikes):
    """Run combat_case with a fake native probe against a mock formula-free lite engine."""
    native = mock.Mock()
    lite = mock.Mock(spec=['reset', 'step', 'observe'])  # no inject_hits: the engine has no RNG
    native.observe.return_value = {'units': []}
    native.step.return_value = {'differential': {'strikes': native_strikes}}
    lite.step.return_value = {'strikes': lite_strikes}
    lite.observe.return_value = {'units': []}
    with mock.patch('engine_lite.differential.game_spec', return_value={'units': [{}, {}, {}]}), \
            mock.patch('engine_lite.differential._state', return_value={'turn': 1}), \
            mock.patch('engine_lite.differential._units', return_value={}):
        return combat_case(native, lite, {}, ('ordinary', 'a', 'b', 0))


class DifferentialRunnerTests(unittest.TestCase):
    def test_native_decision_forwards_teacher_and_budget(self):
        from learning.native_transport import NativeTransport
        transport = NativeTransport.__new__(NativeTransport)
        transport._request = lambda kind, **payload: dict(kind=kind, **payload)
        self.assertEqual(transport.decision(2, teacher=True, budget_ms=20000),
                         dict(kind='decision', side=2, teacher=True, budget_ms=20000))

    def test_strike_order_mismatch_is_a_failure(self):
        result = run([strike('a', 'b'), strike('b', 'a')], [strike('b', 'a')])
        self.assertEqual(result['status'], 'failed')
        self.assertFalse(result['passed'])
        self.assertEqual(result['differences'][0]['check'], 'strike order')

    def test_random_damage_deltas_are_expected_differences(self):
        # The native roll hit for 4; the deterministic formula connects for 7.
        result = run([strike('a', 'b', damage=4, defender_hp=16)], [strike('a', 'b', damage=7)])
        self.assertEqual(result['status'], 'expected_difference')
        self.assertTrue(result['passed'])
        self.assertEqual(result['expected_differences'][0]['check'], 'strike 0')
        self.assertEqual(result['expected_differences'][0]['difference']['damage'],
                         dict(native=4, lite=7))
        self.assertEqual(result['rule_profile'], 'expected_damage_v1')

    def test_combined_status_orders_expected_differences_below_failures(self):
        self.assertEqual(_combined_status([dict(status='failed', passed=False), dict(status='expected_difference', passed=True)]), 'failed')
        self.assertEqual(_combined_status([dict(status='expected_difference', passed=True), dict(status='passed', passed=True)]),
                         'expected_difference')
        self.assertEqual(_combined_status([dict(status='passed', passed=True), dict(status='inconclusive', passed=False)]), 'inconclusive')
        self.assertEqual(_combined_status([dict(status='passed', passed=True)]), 'passed')

    def test_native_probe_preserves_strike_order_and_handles_death(self):
        from lupa import LuaRuntime
        lua = LuaRuntime()
        lua.execute('''
            handlers={}; a={id='a',hitpoints=12,status={}}; d={id='d',hitpoints=8,status={}}
            on_map={a=a,d=d}
            wesnoth={game_events={add=function(event) handlers[event.name]=event.action end},
                units={get=function(x) return x==1 and a or d end,
                       find_on_map=function(filter) return {on_map[filter.id]} end},
                simulate_combat=function()
                    local p={average_hp=8,hp_chance={[0]=.2,[10]=.8},poisoned=0,slowed=0}
                    return p,p,{chance_to_hit=60},{chance_to_hit=40}
                end}
        ''')
        probe = lua.execute(Path('engine_lite/lua/differential_probe.lua').read_text())
        probe.initialize()
        probe.before(lua.table_from(dict(kind='attack', x=1, y=1, tx=2, ty=1, weapon=1)))
        lua.execute("d.hitpoints=2; handlers['attacker hits'](); handlers['defender misses'](); "
                    "d.hitpoints=0; handlers['attacker hits'](); on_map.d=nil")
        result = probe.after()
        self.assertEqual([result.strikes[i].hit for i in (1, 2, 3)], [True, False, True])
        self.assertEqual(result.defender.hp, 0)
        self.assertEqual(result.oracle.attacker.hp_chance['0'], .2)


if __name__ == '__main__':
    unittest.main()
