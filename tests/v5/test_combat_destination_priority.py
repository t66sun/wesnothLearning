"""Regression at the shared decision interface from a frozen real teacher turn."""
import json
from pathlib import Path
import unittest

from learning.coverage import matching
from learning.lite_host import LiteHost


class CombatDestinationPriorityTests(unittest.TestCase):
    def test_position_or_village_pick_keeps_its_combat_probe_priority(self):
        path = Path(__file__).resolve().parents[2]/'data/datasets/diagnostic/bc_priority_20261101.json'
        data = json.loads(path.read_text())
        host = LiteHost(data['spec'])
        self.addCleanup(host.adapter.close)
        host.restore(data['snapshot'])
        row = host.decision(data['side'], teacher=False)
        # The landing hex was first picked for its village goal. Its adjacency to
        # an enemy must still put it ahead of non-combat moves under the same cap.
        self.assertGreaterEqual(matching(row['candidates'], data['intent']), 0)
        self.assertLessEqual(len(row['candidates']), 37)
        self.assertLessEqual(row['timing']['move_probes'], 48)
        self.assertLessEqual(row['timing']['work'], 12000)


if __name__ == '__main__':
    unittest.main()
