"""Astra's village ledger: seen once, remembered per side, restored intact.

``host.lua`` copies every legally observed village ownership into the frozen
Astra index ``x*1000+y`` before a teacher query.  Losing sight of the village
must not erase that memory, another side must never inherit it, and a
snapshot/restore cycle must reproduce it exactly.

The states are synthetic LiteEngine positions: no native game is launched and
nothing here is a statement about live play.
"""
from __future__ import annotations

import copy
import json
import unittest

from tests.v5 import helpers

WIDTH, HEIGHT = 12, 11
VILLAGE = 7 * WIDTH + 2                       # zero-based (2, 7) == Wesnoth (3, 8)
KEEP = 0 * WIDTH + 0
CASTLES = (0 * WIDTH + 1, 1 * WIDTH + 1)


def _rules():
    """Short-vision observers, so a move can genuinely lose sight of a village."""
    rules = copy.deepcopy(helpers.rules())
    scout = copy.deepcopy(rules['units']['Archer'])
    scout.update(id='Scout', vision=2)
    watcher = copy.deepcopy(rules['units']['Fighter'])
    watcher.update(id='Watcher', vision=1)
    rules['units']['Scout'] = scout
    rules['units']['Watcher'] = watcher
    return rules


def _observer(identifier, kind, side, x, y, **options):
    base = 'Archer' if kind == 'Scout' else 'Fighter'
    unit = helpers._unit(identifier, base, side, x, y, width=WIDTH, **options)
    unit['unit_type'] = kind
    return unit


def _state():
    terrain = ['Gg'] * (WIDTH * HEIGHT)
    for index, code in ((KEEP, 'Gg^Kh'), (CASTLES[0], 'Gg^Ch'), (CASTLES[1], 'Gg^Ch')):
        terrain[index] = code
    terrain[VILLAGE] = 'Gg^Vh'
    units = [
        helpers._unit('p1', 'Fighter', 1, 0, 0, width=WIDTH, leader=True),
        _observer('m1', 'Scout', 1, 2, 6),
        _observer('e1', 'Watcher', 2, 4, 7),
        _observer('e2', 'Watcher', 2, 10, 9, leader=True),
    ]
    return helpers.spec(sides=2, width=WIDTH, height=HEIGHT, terrain=terrain, units=units)


VILLAGE_HEX = helpers.lua_hex(VILLAGE, WIDTH)


def _wait(instance, side, turn=None):
    for _ in range(40):
        view = helpers.observe(instance, 1)
        if view['current_side'] == side and (turn is None or view['turn'] == turn):
            return view
        helpers.step(instance, {'kind': 'end_turn'})
    raise AssertionError('side %s turn %s never arrived' % (side, turn))


class VillageMemoryLedgerTests(unittest.TestCase):
    def setUp(self):
        self.engine = helpers.engine(game_spec=_state(), rules_data=_rules())
        # Side 1's turn: m1 stands next to the neutral village.
        helpers.decision(self.engine, 1)
        self.first = helpers.snapshot(self.engine)
        _wait(self.engine, 2)
        helpers.decision(self.engine, 2)
        self.other_side = helpers.snapshot(self.engine)
        capture = [action for action in helpers.legal(self.engine, 2)
                   if action['kind'] == 'move' and action.get('unit') == 'e1'
                   and action['to'] == VILLAGE]
        self.assertTrue(capture, 'the side-2 scout must be able to take the village')
        helpers.step(self.engine, capture[0])
        _wait(self.engine, 1, turn=2)
        helpers.decision(self.engine, 1)
        self.captured = helpers.snapshot(self.engine)
        moves = [action for action in helpers.legal(self.engine, 1)
                 if action['kind'] == 'move' and action.get('unit') == 'm1']
        far = max(moves, key=lambda action: helpers.cube_distance(
            helpers.lua_hex(action['to'], WIDTH), VILLAGE_HEX))
        helpers.step(self.engine, far)
        self.blind = helpers.observe(self.engine, 1)
        helpers.decision(self.engine, 1)
        self.after_lost_sight = helpers.snapshot(self.engine)

    def _owners(self, snapshot, side):
        return snapshot['host']['teacher_memory'][str(side)]['owners']

    def test_sighting_is_filed_under_the_frozen_astra_index(self):
        owners = self._owners(self.first, 1)
        self.assertEqual(helpers.ledger_owner(self.first, 1, *VILLAGE_HEX), 0, owners)
        # host.lua drops the observation key: only the numeric Astra index remains.
        self.assertNotIn('%d,%d' % VILLAGE_HEX, owners, owners)

    def test_other_sides_do_not_inherit_a_sighting(self):
        self.assertIn(str(VILLAGE_HEX[0] * 1000 + VILLAGE_HEX[1]), self._owners(self.first, 1))
        self.assertNotIn(str(VILLAGE_HEX[0] * 1000 + VILLAGE_HEX[1]), self._owners(self.other_side, 2))
        self.assertFalse(self.blind['visible'][VILLAGE])
        self.assertEqual(self.blind['villages'][str(VILLAGE)][0], 2)

    def test_capture_is_remembered_and_survives_lost_sight(self):
        self.assertEqual(helpers.ledger_owner(self.captured, 1, *VILLAGE_HEX), 2)
        self.assertFalse(self.blind['visible'][VILLAGE], 'the scout must be out of sight')
        owners = self._owners(self.after_lost_sight, 1)
        self.assertEqual(helpers.ledger_owner(self.after_lost_sight, 1, *VILLAGE_HEX), 2, owners)

    def test_snapshot_restore_round_trips_the_ledger(self):
        before = self.after_lost_sight
        helpers.restore(self.engine, json.dumps(before))
        after = helpers.snapshot(self.engine)
        self.assertEqual(after['host']['teacher_memory'], before['host']['teacher_memory'])
        self.assertEqual(after['host']['exploration'], before['host']['exploration'])
        self.assertEqual(after['game'], before['game'])


if __name__ == '__main__':
    unittest.main()
