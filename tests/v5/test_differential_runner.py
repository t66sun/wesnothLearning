import unittest
from pathlib import Path
from unittest import mock

from engine_lite.differential import _probability, combat_case, wilson


class DifferentialRunnerTests(unittest.TestCase):
    def test_native_decision_forwards_teacher_and_budget(self):
        from learning.native_transport import NativeTransport
        transport = NativeTransport.__new__(NativeTransport)
        transport._request = lambda kind, **payload: dict(kind=kind, **payload)
        self.assertEqual(transport.decision(2, teacher=True, budget_ms=20000),
                         dict(kind='decision', side=2, teacher=True, budget_ms=20000))

    def test_small_sample_cannot_claim_one_percentage_point(self):
        self.assertFalse(_probability(16, 32, .5)['passed'])
        self.assertEqual(_probability(16, 32, .5)['status'], 'inconclusive')
        self.assertTrue(_probability(32768, 65536, .5)['passed'])
        self.assertFalse(_probability(34000, 65536, .5)['passed'])
        self.assertEqual(_probability(34000, 65536, .5)['status'], 'failed')

    def test_deterministic_mismatch_skips_statistical_sampling(self):
        native, lite = mock.Mock(), mock.Mock()
        native.step.return_value = {'differential': {'strikes': [], 'oracle': {}}}
        lite.step.return_value = {'strikes': []}
        with mock.patch('engine_lite.differential.game_spec', return_value={}), \
                mock.patch('engine_lite.differential._state', side_effect=[{'turn': 1}, {'turn': 2}]), \
                mock.patch('engine_lite.differential._units', return_value={}), \
                mock.patch('engine_lite.differential.statistics') as sample:
            result = combat_case(native, lite, {}, ('ordinary', 'a', 'b', 0), 512, 2048)
        sample.assert_not_called()
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['statistics']['samples'], 0)

    def test_zero_observed_events_still_have_uncertainty(self):
        low, high = wilson(0, 32)
        self.assertEqual(low, 0.)
        self.assertGreater(high, .01)

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
