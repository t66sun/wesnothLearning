"""Bounded BC filling: fair first allocation, backfill, and explicit stop reasons.

Rows come from the real Lua capture path in ``tests/v5/helpers`` and are packed
by ``learning.data.write_shard``; the shards differ only in supervised capacity.
"""
import unittest
from unittest import mock

from learning import data, sequences
from learning.sequences import read_shards
from tests.v5 import helpers


def result(bots=('astra', 'astra')):
    bots = list(bots)
    return dict(engine_id='lite-0.1', winner=1, winning_team=0, truncated=False,
                reason='victory', survivors=[1, 2], bots=bots,
                factions=['Fighter', 'Skeleton'], teams=None, turns=10, faults=[],
                rank_points={str(index): 0.5 for index in range(1, len(bots) + 1)},
                approximate=True)


class BoundedFillTests(unittest.TestCase):
    def setUp(self):
        context = helpers.temporary_directory()
        self.directory = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        self.paths = [self.shard('big', 8), self.shard('medium', 3), self.shard('small', 2)]
        self.capacity = 13

    def shard(self, name, turns, decisions_per_turn=1):
        rows = helpers.sequence_rows(turns=turns, decisions_per_turn=decisions_per_turn,
                                     game_id=name, game_family=name)
        path = self.directory / 'shards' / (name + '.jsonl.gz')
        data.write_shard(path, name, rows, result())
        return str(path)

    def counts(self, rows):
        counts = {}
        for row in rows:
            counts[row['game_family']] = counts.get(row['game_family'], 0) + 1
        return counts

    def test_backfill_uses_unused_capacity_after_fair_share(self):
        stats = {}
        # The largest family alone holds 8 rows, so 10 forces backfill from the
        # capacity the fair share left unused in the smaller families.
        rows = read_shards(self.paths, limit=10, seed=7, turns=1, stats=stats)
        self.assertEqual(len(rows), 10)
        self.assertEqual(self.counts(rows), {'big': 5, 'medium': 3, 'small': 2})
        self.assertEqual(stats['stop_reason'], 'window_limit')
        self.assertEqual(stats['deficit'], 0)
        self.assertEqual(stats['rows'], 10)
        self.assertEqual(stats['requested'], 10)
        self.assertEqual(stats['families_decoded'], 3)
        self.assertTrue(all(row['choice'] >= 0 for row in rows))
        # A shortened target keeps its whole raw prefix.
        for row in rows:
            self.assertEqual(len(row['_history']), row['turn'] - 1)

    def test_buckets_own_their_target_rows_instead_of_borrowing(self):
        # Two provenance buckets: eight rows of one engine, two of the other.
        paths = []
        for index, (name, turns) in enumerate((('game-0', 8), ('game-1', 2))):
            rows = helpers.sequence_rows(turns=turns, decisions_per_turn=1,
                                         game_id=name, game_family=name)
            for row in rows:
                row['engine_id'] = f'lite-0.{index + 1}'
            path = self.directory / 'buckets' / f'{index}.jsonl.gz'
            data.write_shard(path, name, rows, result())
            paths.append(str(path))
        stats = {}
        rows = read_shards(paths, limit=10, seed=7, turns=1, stats=stats)
        # Five and five are the bucket targets; the second bucket owns only two
        # rows, so the request stays short instead of silently borrowing.
        self.assertEqual(self.counts(rows), {'game-0': 5, 'game-1': 2})
        self.assertEqual(stats['deficit'], 3)
        self.assertEqual(stats['stop_reason'], 'insufficient_data')
        self.assertEqual(stats['families_decoded'], 2)

    def test_gz_budget_stops_before_decoding_the_next_family(self):
        budget = (self.directory / 'shards' / 'small.jsonl.gz').stat().st_size
        stats = {}
        rows = read_shards(self.paths, limit=10, seed=7, turns=1,
                           gz_budget=budget, stats=stats)
        self.assertEqual(len(rows), 2)
        self.assertLessEqual(stats['gz_bytes'], budget)
        self.assertEqual(stats['deficit'], 8)
        self.assertEqual(stats['stop_reason'], 'gz_budget')
        self.assertEqual(stats['families_decoded'], 1)
        self.assertEqual(stats['families_admitted'], 1)
        self.assertEqual(stats['families_retained'], 1)
        self.assertEqual(stats['families_selected'], 3)

    def test_retain_budget_stops_with_a_smaller_deterministic_result(self):
        alone = {}
        full = read_shards([self.paths[0]], limit=self.capacity, seed=7, turns=1, stats=alone)
        self.assertEqual(len(full), 8)
        budget = alone['retained_bytes']
        stats = {}
        rows = read_shards(self.paths, limit=self.capacity, seed=7, turns=1,
                           retain_budget=budget, stats=stats)
        self.assertGreater(len(rows), 0)
        self.assertLess(len(rows), self.capacity)
        self.assertGreater(stats['deficit'], 0)
        self.assertEqual(stats['stop_reason'], 'retain_budget')
        self.assertLessEqual(stats['retained_bytes'], budget)
        again = read_shards(self.paths, limit=self.capacity, seed=7, turns=1,
                            retain_budget=budget, stats={})
        self.assertEqual([(row['game_id'], row['turn']) for row in rows],
                         [(row['game_id'], row['turn']) for row in again])

    def test_request_beyond_capacity_reports_insufficient_data(self):
        stats = {}
        rows = read_shards(self.paths, limit=self.capacity + 5, seed=7, turns=1, stats=stats)
        self.assertEqual(len(rows), self.capacity)
        self.assertEqual(stats['deficit'], 5)
        self.assertEqual(stats['stop_reason'], 'insufficient_data')

    def test_family_payload_decoded_and_prefix_charged_once(self):
        stats = {}
        with mock.patch.object(sequences, '_family_windows',
                               wraps=sequences._family_windows) as windows, \
                mock.patch.object(sequences, '_prefix_bytes', wraps=sequences._prefix_bytes) as prefix:
            rows = read_shards(self.paths, limit=10, seed=7, turns=1, stats=stats)
        self.assertEqual(len(rows), 10)
        self.assertEqual(stats['families_decoded'], 3)
        self.assertEqual(windows.call_count, stats['families_decoded'])
        self.assertEqual(prefix.call_count, stats['families_decoded'])
        decoded = [str(call.args[0][0][0]) for call in windows.call_args_list]
        self.assertEqual(len(set(decoded)), len(decoded))

    def test_same_seed_repeats_rows_and_stats(self):
        first = {}
        once = read_shards(self.paths, limit=10, seed=11, turns=1, stats=first)
        second = {}
        twice = read_shards(self.paths, limit=10, seed=11, turns=1, stats=second)
        self.assertEqual(first, second)
        self.assertEqual([(r['game_id'], r['turn'], r['decision']) for r in once],
                         [(r['game_id'], r['turn'], r['decision']) for r in twice])

    def test_full_read_keeps_every_row(self):
        stats = {}
        # Budgets bound bounded reads only: a full read is the escape hatch and
        # still returns every supervised row.
        rows = read_shards(self.paths, turns=1, gz_budget=1, retain_budget=1, stats=stats)
        self.assertEqual(len(rows), self.capacity)
        self.assertIsNone(stats['requested'])
        self.assertEqual(stats['rows'], self.capacity)
        self.assertEqual(stats['deficit'], 0)
        self.assertEqual(stats['stop_reason'], 'window_limit')
        self.assertEqual(stats['families_decoded'], 3)
        self.assertEqual(stats['families_admitted'], 3)
        self.assertEqual(stats['families_retained'], 3)
        self.assertEqual(stats['windows'], 13)
        self.assertEqual(stats['kinds'], {'end_turn': 13})


if __name__ == '__main__':
    unittest.main()
