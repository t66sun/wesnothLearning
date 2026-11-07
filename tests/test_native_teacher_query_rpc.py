"""Actual Native RPC uses the frozen teacher descriptor, without executing it."""
import os
import unittest

from learning.native_transport import NativeTransport, _hash, _stable
from learning.teachers.registry import DELIVERY, describe
from tests.v5.test_native_rpc import _spec


class NativeTeacherQueryRpcTests(unittest.TestCase):
    def test_wrong_format_descriptor_is_rejected_before_starting(self):
        spec = _spec()
        spec['teacher_spec'] = describe(DELIVERY/'selected_teacher.zip', 'team2v2')
        with self.assertRaisesRegex(ValueError, 'frozen descriptor'):
            NativeTransport(spec, wesnoth=os.environ['WESNOTH_EXE'])

    def test_frozen_duel_query_leaves_public_battle_state_unchanged(self):
        spec = _spec()
        spec['teacher_spec'] = describe(DELIVERY/'selected_teacher.zip', 'duel')
        with NativeTransport(spec, wesnoth=os.environ['WESNOTH_EXE']) as transport:
            before = transport.observe(1)
            queried = transport.decision(1, teacher=True)
            after = transport.observe(1)
            self.assertIsNone(queried.get('teacher_skipped'))
            self.assertIsNotNone(queried.get('teacher_action'))
            self.assertGreaterEqual(queried['timing']['teacher_ms'], 0)
            self.assertEqual(_hash(_stable(before)), _hash(_stable(after)))
            self.assertEqual(transport.snapshot()['game_spec']['teacher_spec'], spec['teacher_spec'])


if __name__ == '__main__':
    unittest.main()
