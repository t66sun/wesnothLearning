"""Candidate pool budget: the 128-slot cap never starves a unit's full move.

``candidates.lua`` reserves every own unit's best legal full move before the
shared 128-slot cap, fills the rest round-robin, and caps battle forecasts at
16.  This drives the pure-Lua candidate generator against API doubles with a
large reachable set, so the pool overflows on purpose.
"""
from __future__ import annotations

import unittest

from tests import test_lua_contracts as contracts

KINDS = {'end_turn', 'recruit', 'move', 'attack', 'move_attack'}

SETUP = """
-- Six extra own units and twenty visible enemies: the pool is far larger than 128.
for i=1,6 do
    local u=wesnoth.units.create{type='Fighter',side=1,x=1+((i-1)%2),y=3+math.floor((i-1)/2)}
    u.id='s'..i
    fixture.own[#fixture.own+1]=u
    fixture.visible[#fixture.visible+1]=u
end
for i=1,20 do
    local e=wesnoth.units.create{type='Fighter',side=2,x=4+((i-1)%5),y=1+math.floor((i-1)/5)}
    e.id='E'..i
    fixture.visible[#fixture.visible+1]=e
end
local hexes={}
for y=1,6 do for x=1,8 do hexes[#hexes+1]={x,y,1+((x+y)%3)} end end
wesnoth.paths.find_reach=function(u,cfg)
    assert(cfg.viewing_side==1 and cfg.ignore_visibility==false,'visibility-aware path required')
    return hexes
end
"""


def _rows(table):
    return [table[index] for index in range(1, len(table) + 1)]


class CandidatePoolBudgetTests(unittest.TestCase):
    def setUp(self):
        self.lua, self.modules = contracts.initialize()
        self.lua.execute(SETUP)
        self.obs = self.modules['observation.lua'].capture(self.lua.table(), 1)
        actions, timing = self.modules['candidates.lua'].generate(self.obs, 300)
        self.actions = _rows(actions)
        self.timing = timing
        self.own = _rows(self.lua.globals().fixture.own)

    def test_pool_is_capped_and_reports_truncation(self):
        self.assertEqual(len(self.actions), 128, len(self.actions))
        self.assertTrue(self.timing['truncated'])
        self.assertEqual(self.timing['budget'], 'fixed-20000-v2')
        self.assertEqual({action['kind'] for action in self.actions} - KINDS, set())

    def test_every_unit_with_moves_keeps_one_full_move_from_its_hex(self):
        full_moves = {}
        for action in self.actions:
            if action['kind'] == 'move' and action['full']:
                full_moves.setdefault((action['x'], action['y']), []).append(action)
        mobile = [(unit['x'], unit['y'], unit['moves']) for unit in self.own if unit['moves'] > 0]
        self.assertEqual(len(mobile), 8, mobile)
        for x, y, moves in mobile:
            self.assertIn((x, y), full_moves, (x, y, sorted(full_moves)))
            for action in full_moves[(x, y)]:
                self.assertEqual(action['used'], moves, action['used'])
                self.assertNotEqual((action['tx'], action['ty']), (x, y))

    def test_no_intent_is_generated_twice(self):
        seen = set()
        stops = {}
        for action in self.actions:
            if action['kind'] == 'move':
                key = ('move', action['x'], action['y'], action['tx'], action['ty'])
                self.assertNotIn((key, action['full']), seen, key)
                self.assertNotIn((action['tx'], action['ty']), stops.get(key[:3], set()), key)
                stops.setdefault(key[:3], set()).add((action['tx'], action['ty']))
                seen.add((key, action['full']))
                if not action['full']:
                    self.assertGreaterEqual(action['used'], 0, action)
            else:
                # A combat intent is identified by its weapon and, for a moving
                # attack, by the enemy it strikes as well.
                key = (action['kind'], action['x'], action['y'], action['tx'], action['ty'],
                       action['weapon'], action['ex'], action['ey'])
                self.assertNotIn(key, seen, key)
                seen.add(key)

    def test_battle_forecasts_stop_at_sixteen(self):
        combat = [action for action in self.actions if action['kind'] in ('attack', 'move_attack')]
        self.assertGreaterEqual(len(combat), 16, len(combat))
        self.assertEqual(self.timing['predictions'], 16)
        for action in self.actions:
            if action['kind'] in ('attack', 'move_attack'):
                self.assertIsNotNone(action['features'], action)
        for action in self.actions:
            if action['kind'] not in ('attack', 'move_attack'):
                self.assertEqual(action['features'][24], 0, action['kind'])


if __name__ == '__main__':
    unittest.main()
