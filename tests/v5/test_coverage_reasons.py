"""A coverage miss names the retention stage that lost the teacher's intent.

The gate folds two failures into one verdict today: whether the intent survived
candidate retention and whether the policy ranked what it did receive.  These
tests pin the shared intent/candidate contract, the reason each miss is
attributed to, and the audit invariant that the reasons of a kind add up to that
kind's misses.
"""
from __future__ import annotations

import unittest

from learning.coverage import actor, destination, matching, reason
from learning.experiment import coverage_gate
from learning.trajectory_buffer import TrajectoryBuffer

MOVE = dict(kind='move', x=2, y=3, tx=4, ty=3, full=True)
RECRUIT = dict(kind='recruit', type='Fighter', x=5, y=5)
ATTACK = dict(kind='attack', x=2, y=3, tx=3, ty=3, weapon=1)
MOVE_ATTACK = dict(kind='move_attack', x=2, y=3, tx=3, ty=3, ex=4, ey=3, weapon=1)
END_TURN = dict(kind='end_turn')


def _sum_reasons(coverage, kind):
    return sum(count for key, count in coverage['reasons'].items() if key.split(':')[0] == kind)


class IntentContractTests(unittest.TestCase):
    def test_matching_requires_the_whole_field_set(self):
        self.assertEqual(matching([END_TURN, dict(MOVE)], MOVE), 1)
        self.assertEqual(matching([END_TURN, dict(MOVE, full=False)], MOVE), -1)
        self.assertEqual(matching([END_TURN], END_TURN), 0)
        self.assertEqual(matching([], MOVE), -1)

    def test_attack_and_move_attack_are_distinct_intents(self):
        attack = dict(kind='attack', x=2, y=3, tx=4, ty=3, weapon=1)
        move_attack = dict(kind='move_attack', x=2, y=3, tx=3, ty=3, ex=4, ey=3, weapon=1)
        self.assertEqual(matching([attack], move_attack), -1)
        self.assertEqual(matching([move_attack], attack), -1)

    def test_actor_and_destination_read_stationary_actions(self):
        self.assertEqual(actor(ATTACK), (2, 3))
        self.assertEqual(destination(ATTACK), (3, 3))
        self.assertEqual(destination(END_TURN), (None, None))
        self.assertEqual(destination(dict(kind='move', x=7, y=8)), (7, 8))

    def test_reason_names_the_first_lost_stage(self):
        cases = [
            ([END_TURN], MOVE, 'kind_absent'),
            ([dict(kind='recruit', type='Archer', x=5, y=5)], RECRUIT, 'type_absent'),
            ([dict(kind='recruit', type='Fighter', x=6, y=5)], RECRUIT, 'slot_absent'),
            ([dict(MOVE, x=9, y=9, tx=9, ty=8)], MOVE, 'actor_absent'),
            ([dict(MOVE, tx=7, ty=3)], MOVE, 'destination_absent'),
            ([dict(ATTACK, weapon=2)], ATTACK, 'weapon_absent'),
            ([dict(MOVE_ATTACK, ex=5, ey=5)], MOVE_ATTACK, 'enemy_absent'),
            ([dict(MOVE_ATTACK, weapon=2)], MOVE_ATTACK, 'weapon_absent'),
            ([dict(MOVE, full=False)], MOVE, 'mode_absent'),
        ]
        for candidates, action, expected in cases:
            with self.subTest(expected=expected, action=action):
                self.assertEqual(matching(candidates, action), -1)
                self.assertEqual(reason(candidates, action), expected)

    def test_reason_ignores_candidates_of_another_kind(self):
        # A move candidate at the recruit slot must not mask the recruit miss.
        self.assertEqual(reason([dict(kind='move', x=5, y=5, tx=5, ty=6)], RECRUIT), 'kind_absent')


class CoverageReasonTests(unittest.TestCase):
    def _buffer(self):
        buffer = TrajectoryBuffer()
        buffer.append(dict(choice=0, candidates=[dict(RECRUIT)], actual=dict(RECRUIT)))
        buffer.append(dict(choice=-1, candidates=[dict(MOVE_ATTACK, weapon=2)], actual=dict(MOVE_ATTACK)))
        buffer.append(dict(choice=-1, candidates=[dict(ATTACK, weapon=2)], actual=dict(ATTACK)))
        return buffer

    def test_reasons_account_for_every_miss_of_a_kind(self):
        buffer = self._buffer()
        coverage = buffer.coverage
        self.assertEqual(coverage['total'], 3)
        self.assertEqual(coverage['matched'], 1)
        self.assertEqual(coverage['reasons'],
                         {'move_attack:weapon_absent': 1, 'attack:weapon_absent': 2})
        # move_attack is folded into attack exactly as the kind totals fold it.
        for kind, counts in coverage['kinds'].items():
            with self.subTest(kind=kind):
                self.assertEqual(_sum_reasons(coverage, kind), counts['total'] - counts['matched'])
        buffer.close()

    def test_matched_rows_are_never_counted_as_misses(self):
        buffer = TrajectoryBuffer()
        buffer.append(dict(choice=0, candidates=[dict(MOVE)], actual=dict(MOVE)))
        self.assertEqual(buffer.coverage['reasons'], {})
        self.assertEqual(_sum_reasons(buffer.coverage, 'move'), 0)
        buffer.close()

    def test_gate_sums_reasons_and_keeps_its_verdict(self):
        rows = [dict(result={}, coverage=dict(total=4, matched=3, reasons={'move:mode_absent': 1},
                                             kinds=dict(recruit=dict(total=1, matched=1),
                                                        move=dict(total=2, matched=1),
                                                        attack=dict(total=1, matched=1)))),
                dict(result={}, coverage=dict(total=2, matched=2, reasons={'move:mode_absent': 1},
                                             kinds=dict(recruit=dict(total=1, matched=1),
                                                        move=dict(total=1, matched=1),
                                                        attack=dict(total=0, matched=0))))]
        gate = coverage_gate(rows)
        self.assertEqual(gate['reasons'], {'move:mode_absent': 2})
        self.assertEqual(gate['actions']['all'], dict(matched=5, total=6, ratio=5 / 6))
        self.assertFalse(gate['passed'])
        # A result without reasons keeps the historical shape and stays countable.
        self.assertEqual(coverage_gate([dict(result={}, coverage=dict(total=1, matched=1,
                         kinds={k: dict(total=1, matched=1) for k in ('recruit', 'move', 'attack')}))])['reasons'], {})


if __name__ == '__main__':
    unittest.main()
