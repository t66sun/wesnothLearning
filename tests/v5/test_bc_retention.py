"""Unused BC targets must be released before admitting the next family."""
from collections import Counter
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import weakref

from learning import data, sequences
from tests.v5 import helpers
from tests.v5.test_bc_fill import result


class RetainedTargetTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.paths = []
        names = [f'retention-{i}' for i in range(20)
                 if data.split(f'retention-{i}') == 'train'][:3]
        for name in names:
            rows = helpers.sequence_rows(turns=4, decisions_per_turn=64,
                                         game_id=name, game_family=name)
            path = Path(temp.name) / f'{name}.jsonl.gz'
            data.write_shard(path, name, rows, result())
            self.paths.append(str(path))

    def test_rounding_keeps_families_balanced_and_prior_shares_nonincreasing(self):
        self.assertEqual(sequences._water_fill([100, 100, 100], 4), [2, 1, 1])
        for capacities in ([100, 1, 100], [1, 100, 2, 100], [100]*64):
            for requested in (4, 10, 64, 2048):
                previous = []
                for count in range(1, len(capacities)+1):
                    current = sequences._water_fill(capacities[:count], requested)
                    self.assertEqual(sum(current), min(sum(capacities[:count]), requested))
                    self.assertTrue(all(now <= old for now, old in zip(current, previous)))
                    previous = current

    def test_unused_target_objects_are_released_before_next_decode(self):
        original = sequences._family_windows
        references = []
        decoded = []
        histories = {}

        def observe(*args):
            self.assertLessEqual(sum(ref() is not None for ref in references), 96)
            windows, prefix = original(*args)
            references.extend(weakref.ref(row['candidates'][0]['features'])
                              for window in windows for row in window)
            histories.update({(row['game_family'], row['turn'], row['decision']):
                              [slot['turn'] for slot in row['_history']]
                              for window in windows for row in window})
            decoded.append(str(args[0][0][0]))
            return windows, prefix

        with mock.patch.object(sequences, '_family_windows', side_effect=observe):
            rows = sequences.read_shards(self.paths, partition='train', limit=96, seed=7)
        self.assertEqual(sorted(Counter(r['game_family'] for r in rows).values()), [32]*3)
        self.assertEqual(len(set(decoded)), 3)
        self.assertEqual(len(decoded), 3)
        for row in rows:
            self.assertEqual([slot['turn'] for slot in row['_history']],
                             histories[row['game_family'], row['turn'], row['decision']])

    def test_unused_targets_do_not_exclude_families_from_retained_budget(self):
        costs = []
        payloads = []
        for name in self.paths:
            path = Path(name)
            stat = path.stat()
            windows, prefix = sequences._family_windows([(path, stat)], 'train', None, 8)
            costs.append(prefix + sum(sequences._row_bytes(r) for w in windows for r in w))
            payloads.append(sequences._payload_bytes(str(path), stat.st_size, stat.st_mtime_ns))
        # Enough for any first family, but retaining all of its unused targets
        # prevents the second payload from being admitted on the old reader.
        budget = max(costs) + min(payloads) - 1
        stats = {}
        rows = sequences.read_shards(self.paths, partition='train', limit=96, seed=7,
                                     retain_budget=budget, stats=stats)
        self.assertEqual(sorted(Counter(r['game_family'] for r in rows).values()), [32]*3)
        self.assertEqual(stats['families_decoded'], 3)
        self.assertLessEqual(stats['retained_bytes'], budget)
        self.assertEqual(stats['deficit'], 0)


if __name__ == '__main__':
    unittest.main()
