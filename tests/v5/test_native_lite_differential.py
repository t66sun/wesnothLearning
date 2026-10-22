"""Narrow native/lite differential on the real 1.18.8 rules.

This test is deliberately narrower than the P1 acceptance gate: it compares the
initial public geometry, unit fields and legal-action kinds, then executes only
``end_turn`` and checks the turn hand-off.  It does not claim deterministic
combat or full native/lite equivalence.  Run it only where a real Wesnoth
1.18.8 executable is available; the ordinary suite skips it.
"""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from learning.common import ROOT
from learning.native_transport import NativeTransport

from .helpers import engine, legal, observe, step

RULES = ROOT / 'rules/1.18.8/rules.json'
CATALOG = ROOT / 'rules/1.18.8/catalog.json'
WESNOTH = os.environ.get('WESNOTH_EXE')


def _spec():
    board = json.loads((ROOT / 'vendor/arena/maps/arena2.json').read_text(encoding='utf-8'))
    width = len(board['terrain'][0])
    # Put a visible adjacent pair on open terrain so the attack contract can be
    # compared without claiming that either engine rolled the same hits.
    terrain = [code for row in board['terrain'] for code in row]
    units = [
        dict(id='leader_1', unit_type='Elvish Fighter', side=1, pos=(7 - 1) * width + (3 - 1),
             hp=33, moves=5, attacks_left=1, xp=0, leader=True, status=[], traits=[]),
        dict(id='enemy_1', unit_type='Skeleton', side=2, pos=(7 - 1) * width + (4 - 1),
             hp=34, moves=5, attacks_left=1, xp=0, leader=True, status=[], traits=[]),
    ]
    sides = [
        dict(id=1, team='1', faction='Rebels', gold=100, base_income=2,
             recruit=['Elvish Fighter', 'Elvish Archer'], fog=False, shroud=False,
             share_view=False, share_maps=False),
        dict(id=2, team='2', faction='Undead', gold=100, base_income=2,
             recruit=['Skeleton', 'Walking Corpse'], fog=False, shroud=False,
             share_view=False, share_maps=False),
    ]
    return dict(width=width, height=len(board['terrain']), terrain=terrain, sides=sides,
                units=units, village_owner={}, seed=7, max_turns=3,
                experience_modifier=100, allow_approximate=True)


def _unit_fields(view):
    return {u['id']: (u['unit_type'], u['side'], u['pos'], u['hp'], u['moves'], u['attacks_left'])
            for u in view['units']}


def _actions(view):
    return {(a.get('kind'), a.get('unit'), a.get('target'), a.get('to'), a.get('full'),
             a.get('unit_type')) for a in view}


@unittest.skipUnless(WESNOTH and Path(WESNOTH).is_file() and RULES.is_file() and CATALOG.is_file(),
                     'native 1.18.8 executable/captured full rules are absent')
class NativeLiteDifferentialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = json.loads(RULES.read_text(encoding='utf-8'))
        cls.transport = NativeTransport(_spec(), wesnoth=WESNOTH, timeout=30, startup_timeout=120)

    @classmethod
    def tearDownClass(cls):
        cls.transport.close()

    def setUp(self):
        self.transport.reset(_spec())
        self.lite = engine(game_spec=_spec(), rules_data=self.rules)

    def test_initial_public_geometry_and_unit_fields_match(self):
        native = self.transport.observe(1)
        lite = observe(self.lite, 1)
        self.assertEqual(native['width'], lite['width'])
        self.assertEqual(native['height'], lite['height'])
        self.assertEqual(native['terrain'], lite['terrain'])
        self.assertEqual(native['turn'], lite['turn'])
        self.assertEqual(native['current_side'], lite['current_side'])
        native_units = _unit_fields(native)
        lite_units = _unit_fields(lite)
        self.assertEqual(set(native_units), set(lite_units))
        for identifier in native_units:
            self.assertEqual(native_units[identifier], lite_units[identifier], identifier)
        native_teams = {s['id']: s['team'] for s in native['sides']}
        lite_teams = {s['id']: s['team'] for s in lite['sides']}
        self.assertEqual(native_teams, lite_teams)
        public_side = ('id', 'team', 'gold', 'base_income', 'total_income', 'fog',
                       'shroud', 'share_view', 'share_maps', 'eliminated')
        for native_side, lite_side in zip(native['sides'], lite['sides']):
            self.assertEqual({k: native_side.get(k) for k in public_side},
                             {k: lite_side.get(k) for k in public_side})
            self.assertEqual(sorted(native_side.get('recruit') or []),
                             sorted(lite_side.get('recruit') or []))

    def test_legal_sets_and_requested_recruits_match(self):
        native_actions = _actions(self.transport.legal_actions(1))
        lite_actions = _actions(legal(self.lite, 1))
        self.assertEqual({a for a in native_actions if a[0] == 'move'},
                         {a for a in lite_actions if a[0] == 'move'})
        self.assertEqual({a for a in native_actions if a[0] == 'attack'},
                         {a for a in lite_actions if a[0] == 'attack'})
        self.assertEqual(native_actions, lite_actions)
        for side in _spec()['sides']:
            native_side = self.transport.observe(side['id'])['sides'][side['id'] - 1]
            self.assertEqual(sorted(native_side['recruit']), sorted(side['recruit']))

    def test_attack_candidate_and_end_turn_handoff_match(self):
        native_legal = self.transport.legal_actions(1)
        lite_legal = legal(self.lite, 1)
        native_attacks = {(a.get('unit'), a.get('target')) for a in native_legal if a.get('kind') == 'attack'}
        lite_attacks = {(a.get('unit'), a.get('target')) for a in lite_legal if a.get('kind') == 'attack'}
        self.assertIn(('leader_1', 'enemy_1'), native_attacks)
        self.assertIn(('leader_1', 'enemy_1'), lite_attacks)

        native_step = self.transport.step({'kind': 'end_turn'})
        lite_step = step(self.lite, {'kind': 'end_turn'})
        self.assertEqual(native_step['current_side'], 2)
        self.assertEqual(lite_step['current_side'], 2)
        self.assertEqual(native_step['turn'], lite_step['turn'])

        native_step = self.transport.step({'kind': 'end_turn'})
        lite_step = step(self.lite, {'kind': 'end_turn'})
        self.assertEqual(native_step['turn'], 2)
        self.assertEqual(lite_step['turn'], 2)
        self.assertEqual(native_step['current_side'], 1)

    def test_empty_requested_recruits_disable_native_recruitment(self):
        spec = _spec()
        spec['sides'][0]['recruit'] = []
        self.transport.reset(spec)
        self.assertEqual(self.transport.observe(1)['sides'][0]['recruit'], [])
        self.assertFalse(any(a['kind'] == 'recruit' for a in self.transport.legal_actions(1)))
        lite = engine(game_spec=spec, rules_data=self.rules)
        self.assertEqual(observe(lite, 1)['sides'][0]['recruit'], [])
        self.assertFalse(any(a['kind'] == 'recruit' for a in legal(lite, 1)))
