"""An ally-owned, ally-occupied village still pulls side 1 without being landable.

``candidates.lua`` scores a village owned by an ally with the multiplayer
bonus (13+3), so a side-1 unit is drawn towards it, yet the same unit may
never choose the village as its destination: the tile is occupied by an ally
and engine capture requires an unoccupied hex.  Both arms are the same board,
differing only in whether the tile carries a village.

Synthetic LiteEngine states; no native game is involved.
"""
from __future__ import annotations

import unittest

from tests.v5 import helpers

WIDTH, HEIGHT = 12, 11
VILLAGE = 6 * WIDTH + 9                        # zero-based (9, 6) == Wesnoth (10, 7)
VILLAGE_HEX = helpers.lua_hex(VILLAGE, WIDTH)
KEEP, CASTLES = 0, (0 * WIDTH + 1, 1 * WIDTH + 1)
MOVER = (7, 6)                                 # zero-based position of m1


def _state(village=True):
    terrain = ['Gg'] * (WIDTH * HEIGHT)
    terrain[KEEP] = 'Gg^Kh'
    for index in CASTLES:
        terrain[index] = 'Gg^Ch'
    units = [
        helpers._unit('p1', 'Fighter', 1, 0, 0, width=WIDTH, leader=True),
        helpers._unit('m1', 'Archer', 1, MOVER[0], MOVER[1], width=WIDTH),
        helpers._unit('e1', 'Fighter', 2, 11, 9, width=WIDTH, leader=True),
        # Side 3 shares team 'A' with side 1 and stands on the village.
        helpers._unit('a1', 'Mage', 3, 9, 6, width=WIDTH, leader=True),
        helpers._unit('b1', 'Ghost', 4, 0, 10, width=WIDTH, leader=True),
    ]
    state = helpers.spec(sides=4, width=WIDTH, height=HEIGHT, terrain=terrain, units=units)
    if village:
        terrain[VILLAGE] = 'Gg^Vh'
        state['village_owner'] = {str(VILLAGE): 3}
    return state


def _destinations(engine):
    decision = helpers.decision(engine, 1)
    return {(candidate['tx'], candidate['ty']) for candidate in decision['candidates']
            if candidate['kind'] in ('move', 'move_attack')}


class AlliedVillageGoalTests(unittest.TestCase):
    def setUp(self):
        self.ally = helpers.engine(game_spec=_state(True))
        self.control = helpers.engine(game_spec=_state(False))

    def test_ally_village_is_never_a_destination_or_a_legal_move(self):
        view = helpers.observe(self.ally, 1)
        self.assertEqual(view['villages'][str(VILLAGE)][0], 3, view['villages'])
        decision = helpers.decision(self.ally, 1)
        targets = {(candidate['tx'], candidate['ty']) for candidate in decision['candidates']
                   if candidate['kind'] in ('move', 'move_attack')}
        self.assertNotIn(VILLAGE_HEX, targets)
        moves = {action['to'] for action in helpers.legal(self.ally, 1) if action['kind'] == 'move'}
        self.assertNotIn(VILLAGE, moves)

    def test_ally_village_pulls_side_one_towards_it(self):
        ally = _destinations(self.ally)
        control = _destinations(self.control)
        near = {hex_ for hex_ in ally if helpers.cube_distance(hex_, VILLAGE_HEX) == 1}
        self.assertTrue(near, sorted(ally))
        self.assertEqual({hex_ for hex_ in control
                          if helpers.cube_distance(hex_, VILLAGE_HEX) == 1}, set())
        self.assertNotEqual(ally, control)
        # The control keeps the same ally on the same hex: only the strategic
        # village goal differs, never the occupancy of the tile itself.
        self.assertNotIn(VILLAGE_HEX, control)

    def test_ally_village_is_in_astra_ledger_with_its_owner(self):
        helpers.decision(self.ally, 1)
        self.assertEqual(helpers.ledger_owner(helpers.snapshot(self.ally), 1, *VILLAGE_HEX), 3)


if __name__ == '__main__':
    unittest.main()
