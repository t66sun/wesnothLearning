"""In a duel a hurt unit drops its enemy goals and heads for the village.

``candidates.lua`` computes ``hurt = hitpoints < max_hitpoints*.65``; when the
unit is hurt and the game is not multiplayer the enemy goals are dropped, so
only villages and the keep remain as strategic targets.  The two arms are the
same board and the same units, differing only in the moving unit's hitpoints.

Synthetic LiteEngine states; the enemy carries no weapons so that the hurt
risk weighting cannot mask the goal change.
"""
from __future__ import annotations

import copy
import unittest

from tests.v5 import helpers

WIDTH, HEIGHT = 12, 11
VILLAGE = 9 * WIDTH + 1                        # zero-based (1, 9) == Wesnoth (2, 10)
VILLAGE_HEX = helpers.lua_hex(VILLAGE, WIDTH)
KEEP, CASTLES = 0, (0 * WIDTH + 1, 1 * WIDTH + 1)
MOVER = (5, 5)                                 # zero-based position of m1, Wesnoth (6, 6)
ENEMY_HEX = (8, 7)
HEALTHY, HURT = 32, 20                         # Archer max 32: 20 < 32*.65 = 20.8


def _rules():
    """A weaponless, slow watchtower: no threat damage, no risk masking."""
    rules = copy.deepcopy(helpers.rules())
    sentinel = copy.deepcopy(rules['units']['Fighter'])
    sentinel.update(id='Sentinel', moves=2, weapons=[])
    rules['units']['Sentinel'] = sentinel
    return rules


def _sentinel(identifier, side, x, y):
    unit = helpers._unit(identifier, 'Fighter', side, x, y, width=WIDTH, leader=True)
    unit['unit_type'] = 'Sentinel'
    unit['moves'] = 2
    return unit


def _state(hitpoints):
    terrain = ['Gg'] * (WIDTH * HEIGHT)
    terrain[KEEP] = 'Gg^Kh'
    for index in CASTLES:
        terrain[index] = 'Gg^Ch'
    terrain[VILLAGE] = 'Gg^Vh'
    units = [
        helpers._unit('p1', 'Fighter', 1, 0, 0, width=WIDTH, leader=True),
        helpers._unit('m1', 'Archer', 1, MOVER[0], MOVER[1], width=WIDTH, hp=hitpoints),
        _sentinel('e1', 2, 7, 6),
    ]
    return helpers.spec(sides=2, width=WIDTH, height=HEIGHT, terrain=terrain, units=units)


MOVER_HEX = helpers.lua_hex(MOVER[1] * WIDTH + MOVER[0], WIDTH)


def _destinations(engine):
    """Destination tile to pick categories for the non-leader mover, plus timing."""
    decision = helpers.decision(engine, 1)
    destinations = {}
    for candidate in decision['candidates']:
        if candidate['kind'] not in ('move', 'move_attack'):
            continue
        if (candidate['x'], candidate['y']) != MOVER_HEX:
            continue
        # Only moves carry a pick category; a move_attack is the attack option.
        category = candidate['category'] if candidate['kind'] == 'move' else 'attack'
        destinations.setdefault((candidate['tx'], candidate['ty']), set()).add(category)
    return destinations, decision['timing']


class DuelHurtBranchTests(unittest.TestCase):
    def setUp(self):
        self.healthy, self.healthy_timing = _destinations(helpers.engine(
            game_spec=_state(HEALTHY), rules_data=_rules()))
        self.hurt, self.hurt_timing = _destinations(helpers.engine(
            game_spec=_state(HURT), rules_data=_rules()))

    def test_hurt_unit_gives_up_positional_pressure_towards_the_enemy(self):
        def near(destinations):
            return {hex_: categories for hex_, categories in destinations.items()
                    if helpers.cube_distance(hex_, ENEMY_HEX) == 1}
        healthy, hurt = near(self.healthy), near(self.hurt)
        self.assertTrue(healthy, sorted(self.healthy))
        self.assertTrue(any('position' in categories for categories in healthy.values()),
                        'a healthy unit should rank tiles next to the enemy as position')
        self.assertEqual(set().union(*hurt.values()) - {'attack'}, set(),
                         'a hurt unit keeps only the goal-free attack option by the enemy')

    def test_hurt_unit_approaches_the_village_instead(self):
        def village_side(destinations):
            return {hex_ for hex_ in destinations
                    if helpers.cube_distance(hex_, VILLAGE_HEX) <= 2}
        healthy, hurt = village_side(self.healthy), village_side(self.hurt)
        self.assertGreater(len(hurt), len(healthy), (sorted(hurt), sorted(healthy)))
        gained = hurt - healthy
        self.assertTrue(gained, (sorted(hurt), sorted(healthy)))
        for hex_ in gained:
            self.assertLessEqual(helpers.cube_distance(hex_, VILLAGE_HEX), 2, hex_)
            self.assertNotEqual(helpers.cube_distance(hex_, ENEMY_HEX), 1, hex_)

    def test_goal_change_is_not_a_budget_artefact(self):
        for timing in (self.healthy_timing, self.hurt_timing):
            self.assertEqual(timing['budget'], 'work-12000-v5', timing)
            self.assertFalse(timing['truncated'], timing)
            self.assertGreater(timing['predictions'], 0, timing)


if __name__ == '__main__':
    unittest.main()
