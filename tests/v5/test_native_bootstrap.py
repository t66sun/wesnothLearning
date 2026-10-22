"""Run the real native RPC startup Lua without launching Wesnoth.

The side objects model multiplayer faction defaults already applied by the
engine. Native integration tests separately check the actual engine boundary.
"""
import unittest

from lupa import LuaRuntime

from learning.common import ROOT


class NativeBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lua.execute("""
            session = {spec={width=8, units={}, sides={
                {id=1, gold=100, recruit={'Mage'}},
                {id=2, gold=80, recruit={}}
            }}, initialized=false, reward_initialized=false}
            __learning_native_rpc = session
            map_units = {}
            initialized_recruits = {}
            local rewards = {initialize_all=function()
                for i, side in ipairs(wesnoth.sides) do
                    initialized_recruits[i] = table.concat(side.recruit, ',')
                end
            end}
            local judge = {done=function() return true end, check=function() end}
            wesnoth = {
                sides={{gold=102, recruit={'Elvish Fighter','Elvish Archer'}},
                       {gold=82, recruit={'Skeleton','Walking Corpse'}}},
                units={
                    create=function(cfg)
                        return {id=cfg.id, type=cfg.type, side=cfg.side,
                                canrecruit=cfg.canrecruit, status={}}
                    end,
                    to_map=function(u) map_units[u.id]=u end,
                    find_on_map=function(filter)
                        local u=map_units[filter.id]
                        return u and u.side==filter.side and {u} or {}
                    end
                },
                require=function(path)
                    if path:find('rewards.lua',1,true) then return rewards end
                    if path:find('runtime.lua',1,true) then return judge end
                    return {}
                end
            }
        """)
        self.lua.globals().rpc = self.lua.execute(
            (ROOT / 'learning/native_rpc.lua').read_text(encoding='utf-8'))

    def evaluate(self):
        self.lua.execute('rpc:evaluation({}, {})')

    def test_requested_recruits_replace_faction_defaults_before_rewards(self):
        self.evaluate()
        self.assertEqual(self.lua.eval("table.concat(wesnoth.sides[1].recruit, ',')"), 'Mage')
        self.assertEqual(self.lua.eval('initialized_recruits[1]'), 'Mage')
        self.assertEqual(self.lua.eval('wesnoth.sides[1].gold'), 100)

    def test_empty_recruits_disable_recruitment(self):
        self.evaluate()
        self.assertEqual(self.lua.eval('#wesnoth.sides[2].recruit'), 0)
        self.assertEqual(self.lua.eval('initialized_recruits[2]'), '')

    def test_bootstrap_does_not_reset_later_turns(self):
        self.evaluate()
        self.lua.execute("wesnoth.sides[1].recruit={'Spearman'}; wesnoth.sides[1].gold=61")
        self.evaluate()
        self.assertEqual(self.lua.eval("table.concat(wesnoth.sides[1].recruit, ',')"), 'Spearman')
        self.assertEqual(self.lua.eval('wesnoth.sides[1].gold'), 61)

    def test_requested_leader_type_and_flag_are_preserved(self):
        self.lua.execute("""
            session.spec.units = {
                {id='custom_leader', unit_type='Mage', side=1, pos=0,
                 leader=true, hp=24, moves=3, attacks_left=1, xp=4},
                {id='non_leader', unit_type='Spearman', side=2, pos=1,
                 leader=false, hp=25, moves=2, attacks_left=0, xp=2}
            }
            rpc.initialize()
        """)
        self.evaluate()
        self.assertEqual(self.lua.eval('map_units.custom_leader.type'), 'Mage')
        self.assertTrue(self.lua.eval('map_units.custom_leader.canrecruit'))
        self.assertFalse(self.lua.eval('map_units.non_leader.canrecruit'))
        self.assertEqual(self.lua.eval('map_units.custom_leader.hitpoints'), 24)


if __name__ == '__main__':
    unittest.main()
