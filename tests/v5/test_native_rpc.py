"""Native 1.18.8 restart/replay smoke; requires WESNOTH_EXE and real data.

The shared code contract tests use synthetic rules. This module is the explicit
native boundary: it is skipped unless a real 1.18.8 executable is configured.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from learning.common import ROOT
from learning.lite_policy import game_spec
from learning.native_transport import NativeTransport, _hash, _stable


def _spec():
    rules = {'units': {'Elvish Captain': {'hp': 42, 'moves': 5},
                       'Orcish Warrior': {'hp': 44, 'moves': 5}}}
    job = dict(bots=['astra', 'astra'], factions=['Rebels', 'Northerners'], seed=7,
               teams=[1, 2], fog=True, shroud=False, share_view=True, share_maps=True,
               max_turns=2, allow_approximate=True)
    return game_spec(job, rules)


def _executable():
    value = os.environ.get('WESNOTH_EXE')
    return Path(value) if value and Path(value).is_file() else None


@unittest.skipUnless(_executable(), 'WESNOTH_EXE is not a real native 1.18.8 executable')
class NativeRpcSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.transport = NativeTransport(_spec(), wesnoth=str(_executable()), timeout=30, startup_timeout=120)

    @classmethod
    def tearDownClass(cls):
        cls.transport.close()

    def setUp(self):
        self.transport.reset(_spec())

    def test_native_observe_legal_decision_and_execute(self):
        view = self.transport.observe(1)
        self.assertEqual(view['engine_id'], 'native-1.18.8')
        self.assertEqual(view['turn'], 1)
        self.assertTrue(view['units'])
        legal = self.transport.legal_actions(1)
        self.assertGreater(len(legal), 0)
        self.assertEqual(legal[0]['kind'], 'end_turn')
        decision = self.transport.decision(1)
        self.assertGreater(len(decision['candidates']), 0)
        result = self.transport.execute_candidate(decision['candidates'][0])
        self.assertIn('committed', result)

    def test_native_restore_restarts_and_replays_same_state(self):
        self.transport.observe(1)
        self.transport.legal_actions(1)
        decision = self.transport.decision(1)
        self.transport.execute_candidate(decision['candidates'][0])
        before = _hash(_stable(self.transport.observe(1)))
        snapshot = self.transport.snapshot()
        self.assertEqual(snapshot['kind'], 'native_restart_replay_v1')
        self.assertTrue(snapshot['rpc_log'])
        self.transport.restore(snapshot)
        self.assertEqual(_hash(_stable(self.transport.observe(1))), before)

    def test_native_restore_rejects_a_diverged_replay_log(self):
        self.transport.observe(1)
        snapshot = self.transport.snapshot()
        snapshot['rpc_log'][0]['response_sha256'] = '0' * 64
        with self.assertRaises(Exception):
            self.transport.restore(snapshot)
        self.assertIsNone(self.transport.process)

    def test_native_timeout_closes_the_session(self):
        with tempfile.TemporaryDirectory() as directory:
            transport = NativeTransport(_spec(), wesnoth=str(_executable()), timeout=1e-6,
                                        startup_timeout=120, work_dir=directory)
            try:
                with self.assertRaises(Exception):
                    transport.observe(1)
                self.assertIsNone(transport.process)
            finally:
                transport.close()
