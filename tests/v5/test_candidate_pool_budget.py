"""Candidate generation is bounded by charged work, never by the clock.

``candidates.lua`` charges a fixed budget of search work per decision and caps
every native call stage, so generation is deterministic and work-proportional
whatever the machine speed.  The shared selection then keeps the pool at 37
candidates with every own unit's best legal full move represented.  These tests
drive the pure-Lua generator against API doubles with reachable sets far larger
than the budget, so the cutoff fires on purpose.
"""
from __future__ import annotations

import json
import unittest

from tests import test_lua_contracts as contracts

KINDS = {'end_turn', 'recruit', 'move', 'attack', 'move_attack'}

SETUP = """
-- Six extra own units and twenty visible enemies: the pool is far larger than 37.
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

DENSE = """
-- Thirty own units over a 20x20 reachable grid: every stage wants more work
-- than the budget grants, so each cap and the total charge must cut it short.
for i=1,30 do
    local u=wesnoth.units.create{type='Fighter',side=1,x=1+((i-1)%6),y=1+math.floor((i-1)/6)}
    u.id='d'..i
    fixture.own[#fixture.own+1]=u
    fixture.visible[#fixture.visible+1]=u
end
local hexes={}
for y=1,20 do for x=1,20 do hexes[#hexes+1]={x,y,1+((x+y)%3)} end end
wesnoth.paths.find_reach=function(u,cfg) return hexes end
"""


def _rows(table):
    return [table[index] for index in range(1, len(table) + 1)]


def _plain(value):
    if hasattr(value, 'items'):
        return {str(key): _plain(item) for key, item in value.items()}
    return value


def _fingerprint(actions):
    return json.dumps([_plain(action) for action in actions], sort_keys=True, default=str)


class CandidatePoolBudgetTests(unittest.TestCase):
    def setUp(self):
        self.lua, self.modules = contracts.initialize()
        self.lua.execute(SETUP)
        self.obs = self.modules['observation.lua'].capture(self.lua.table(), 1)
        actions, timing = self.modules['candidates.lua'].generate(self.obs)
        self.actions = _rows(actions)
        self.timing = timing
        self.own = _rows(self.lua.globals().fixture.own)

    def test_work_budget_bounds_dense_generation(self):
        self.assertLessEqual(len(self.actions), 37)
        self.assertEqual(self.actions[0]['kind'], 'end_turn')
        self.assertIs(self.timing['truncated'], True)
        self.assertEqual(self.timing['budget'], 'work-12000-v5')
        self.assertLessEqual(self.timing['work'], 12000)
        self.assertLessEqual(self.timing['reaches'], 28)
        self.assertLessEqual(self.timing['paths'], 8)
        self.assertLessEqual(self.timing['recruit_probes'], 24)
        self.assertLessEqual(self.timing['attack_probes'], 32)
        self.assertLessEqual(self.timing['move_probes'], 32)
        self.assertLessEqual(self.timing['predictions'], 16)
        self.assertEqual({action['kind'] for action in self.actions} - KINDS, set())

    def test_generation_is_deterministic_and_clock_independent(self):
        first = _fingerprint(self.actions)
        second, first_work = None, self.timing['work']
        again, again_timing = self.modules['candidates.lua'].generate(self.obs)
        second = _fingerprint(_rows(again))
        self.assertEqual(second, first)
        self.assertEqual(again_timing['work'], first_work)
        self.lua.execute('wesnoth.ms_since_init=function() return 1e12 end')
        late, late_timing = self.modules['candidates.lua'].generate(self.obs)
        self.assertEqual(_fingerprint(_rows(late)), first)
        self.assertEqual(late_timing['work'], first_work)

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

    def test_battle_forecasts_cover_the_retained_combat_set_within_sixteen(self):
        combat = [action for action in self.actions if action['kind'] in ('attack', 'move_attack')]
        self.assertLessEqual(self.timing['predictions'], 16)
        self.assertEqual(self.timing['predictions'], len(combat))
        for action in combat:
            self.assertIsNotNone(action['features'], action)
        for action in self.actions:
            if action['kind'] not in ('attack', 'move_attack'):
                self.assertEqual(action['features'][24], 0, action['kind'])

    def test_oversized_reachable_sets_are_cut_to_the_work_budget(self):
        lua, modules = contracts.initialize()
        lua.execute(DENSE)
        obs = modules['observation.lua'].capture(lua.table(), 1)
        actions, timing = modules['candidates.lua'].generate(obs)
        actions = _rows(actions)
        self.assertIs(timing['truncated'], True)
        self.assertEqual(actions[0]['kind'], 'end_turn')
        self.assertEqual(timing['budget'], 'work-12000-v5')
        self.assertLessEqual(len(actions), 37)
        self.assertLessEqual(timing['work'], 12000)
        self.assertLessEqual(timing['reaches'], 28)
        self.assertLessEqual(timing['paths'], 8)
        self.assertLessEqual(timing['recruit_probes'], 24)
        self.assertLessEqual(timing['attack_probes'], 32)
        self.assertLessEqual(timing['move_probes'], 32)
        self.assertLessEqual(timing['predictions'], 16)
        self.assertEqual({action['kind'] for action in actions} - KINDS, set())


if __name__ == '__main__':
    unittest.main()
