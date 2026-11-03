"""Reach a late roster entry on the recorded Sablestone Delta opening."""

import json
import unittest

from learning.coverage import matching
from learning.lite_host import LiteHost
from learning.lite_policy import game_spec
from learning.maps import frozen_map
from learning.rules_catalog import resolve_dir


class RecruitProbePriorityTests(unittest.TestCase):
    def test_late_recruit_on_a_proven_castle_slot(self):
        # teacher-00035-duel-t0, through the first three committed actions.
        board, _ = frozen_map('sablestone_delta')
        rules_dir = resolve_dir()
        rules = json.loads((rules_dir / 'rules.json').read_text(encoding='utf-8'))
        job = dict(map_override=board, factions=['Knalgan Alliance', 'Loyalists'],
                   seed=3264892820, max_turns=30, allow_approximate=True)
        host = LiteHost(game_spec(job, rules), rules_dir)
        self.addCleanup(host.adapter.close)
        prefix = [(1, dict(kind='end_turn')),
                  (2, dict(kind='recruit', type='Spearman', x=14, y=22)),
                  (2, dict(kind='recruit', type='Spearman', x=14, y=23))]
        for side, action in prefix:
            host.decision(side, teacher=False, generate_candidates=False)
            self.assertTrue(host.execute(action)['committed'])

        row = host.decision(2, teacher=False)
        intent = dict(kind='recruit', type='Spearman', x=15, y=23)
        tile = (intent['y'] - 1) * board['width'] + intent['x'] - 1
        self.assertIn(dict(kind='recruit', unit_type='Spearman', to=tile),
                      host.adapter.legal_actions(2))
        self.assertGreaterEqual(matching(row['candidates'], intent), 0)
        self.assertLessEqual(len(row['candidates']), 37)
        self.assertLessEqual(row['timing']['recruit_probes'], 192)
        self.assertLessEqual(row['timing']['work'], 12000)
