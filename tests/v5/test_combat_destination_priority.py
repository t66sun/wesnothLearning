"""Regression at the shared decision interface from a frozen real teacher turn."""
import json
import gzip
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

    def test_planning_cannot_starve_later_actors_or_combat_features(self):
        path = Path(__file__).resolve().parents[2]/'data/datasets/diagnostic/bc_budget_20261101.json.gz'
        with gzip.open(path,'rt') as stream:
            data = json.load(stream)
        host = LiteHost(data['spec'])
        self.addCleanup(host.adapter.close)
        host.restore(data['snapshot'])
        row = host.decision(data['side'], teacher=False)
        actor = data['intent']['x'],data['intent']['y']
        moves = [c for c in row['candidates'] if c['kind']=='move']
        self.assertTrue(any((c['x'],c['y'])==actor for c in moves))
        for c in row['candidates']:
            if c['kind'] in ('attack','move_attack'):
                self.assertEqual(c['features'][23],1)
        self.assertLessEqual(len(row['candidates']),37)
        self.assertLessEqual(row['timing']['work'],12000)

    def test_reachable_safe_retreat_survives_the_proximity_shortlist(self):
        path = Path(__file__).resolve().parents[2]/'data/datasets/diagnostic/bc_retreat_20261101.json.gz'
        with gzip.open(path,'rt') as stream:
            data = json.load(stream)
        host = LiteHost(data['spec'])
        self.addCleanup(host.adapter.close)
        host.restore(data['snapshot'])
        row = host.decision(data['side'],teacher=False)
        self.assertGreaterEqual(matching(row['candidates'],data['intent']),0)
        self.assertLessEqual(len(row['candidates']),37)
        self.assertLessEqual(row['timing']['work'],12000)


if __name__ == '__main__':
    unittest.main()
