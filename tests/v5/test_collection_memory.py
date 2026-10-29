"""Collector memory regressions using real host records and sequence writes."""
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
import weakref
from unittest import mock
import zlib

import numpy as np

from tests.v5 import helpers
from tests.v5 import test_pipeline_contract as fixtures
from learning import data, lite_host, rowpack, sequences


class CollectionMemoryTests(unittest.TestCase):
    def ephemeral_rows(self):
        template = helpers.synthetic_decision_row()
        references = []
        for number in range(4):
            row = rowpack.compact_row(template)
            row['decision'] = number
            references.append(weakref.ref(row['global']))
            if number >= 2:
                self.assertIsNone(references[number - 2](), 'consumer retained prior decision arrays')
            yield row

    def test_sequence_writer_releases_prior_rows_while_consuming_generator(self):
        with tempfile.TemporaryDirectory() as directory, sequences.IndexedSequenceStore(directory) as store:
            self.assertEqual(store.write(self.ephemeral_rows()), 4)

    def test_shard_writer_does_not_rebuild_an_entire_raw_row_list(self):
        test = self
        class Replayable:
            def __iter__(self):return test.ephemeral_rows()
        with tempfile.TemporaryDirectory() as directory:
            result = data.write_shard(Path(directory)/'rows.jsonl.gz', 'game-1', Replayable(), fixtures.result())
        self.assertEqual(result['written'], 4)

    def test_projected_metric_rows_preserve_turn_five_and_ten_diagnostics(self):
        from learning.trajectory_buffer import TrajectoryBuffer
        from learning.reward_metrics import summarize_game
        rows = helpers.sequence_rows(turns=10, decisions_per_turn=1)
        for row in rows:
            row['reward_raw'] = dict(economy=.1, control=.2, explored=.3)
            row['reward_after'] = dict(row['reward_raw'])
        job = dict(id='seq-1', engine='lite', factions=['Rebels','Undead'],
                   meta=dict(format='duel',map='test',map_sha256='test',map_partition='train',context='solo'))
        expected = summarize_game(rows, fixtures.result(), job)
        with TrajectoryBuffer() as buffer:
            for row in rows:buffer.append(row)
            actual = summarize_game(buffer.metric_rows(), fixtures.result(), job)
        self.assertIsNotNone(expected[0]['horizons']['5']['loss'])
        self.assertIsNotNone(expected[0]['horizons']['10']['loss'])
        self.assertEqual(actual, expected)

    def test_collector_spools_complete_rows_without_retaining_their_arrays(self):
        from learning.trajectory_buffer import TrajectoryBuffer
        row = rowpack.compact_row(helpers.synthetic_decision_row())
        original = rowpack.plain_row(row)
        reference = weakref.ref(row['global'])
        with TrajectoryBuffer() as buffer:
            buffer.append(row)
            del row
            self.assertIsNone(reference())
            self.assertEqual(len(buffer), 1)
            for _ in range(2):
                self.assertEqual(rowpack.plain_row(next(iter(buffer))), original)
            metrics = list(buffer.metric_rows())
            self.assertNotIn('candidates', metrics[0])
            self.assertNotIn('board', metrics[0]['spatial'])
            self.assertEqual(rowpack.plain_row(metrics[0]['spatial']['entities']), original['spatial']['entities'])

    def test_missing_metric_vector_stays_missing_after_numpy_support(self):
        from learning.reward_metrics import _field
        self.assertIsNone(_field({'global': None, 'global_features': None}, 'own_units'))

    def test_compaction_preserves_precision_labels_and_container_types(self):
        row = helpers.synthetic_decision_row()
        row['global'][0] = 0.12345678901234567
        original = copy.deepcopy(row)
        compact = rowpack.compact_row(row)
        self.assertIsInstance(compact['global'], np.ndarray)
        self.assertEqual(compact['global'].dtype, np.float64)
        self.assertIsInstance(compact['opponents'], list)
        self.assertIsInstance(compact['turn'], int)
        self.assertIsInstance(compact['choice'], int)
        self.assertEqual(rowpack.plain_row(compact), original)
        self.assertEqual(row, original)
        self.assertEqual(rowpack.pack_line(compact), rowpack.pack_line(original))

    def test_real_collector_compacts_before_write_without_changing_output(self):
        fixture = fixtures.LiteJobTests('test_missing_catalog_is_reported_as_infrastructure_error')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        baseline_job = fixture.job(shard=str(fixture.directory / 'baseline/game.jsonl.gz'))
        baseline_job['meta']['phase'] = 'validation'
        class LegacyRows(list):
            def metric_rows(self):return iter(self)
            def close(self):pass
            @property
            def truncated(self):return sum(r['timing'].get('truncated', False) for r in self)
            @property
            def coverage(self):
                kinds = {kind: dict(total=sum(r['actual']['kind'] == kind for r in self),
                                   matched=sum(r['actual']['kind'] == kind and r['choice'] >= 0 for r in self))
                         for kind in ('recruit','move','attack','move_attack','end_turn')}
                for name in ('total','matched'):kinds['attack'][name] += kinds['move_attack'][name]
                return dict(total=len(self),matched=sum(r['choice'] >= 0 for r in self),kinds=kinds)
        with fixtures.catalog_patch(fixture.rules_dir), mock.patch.object(lite_host, 'compact_row', side_effect=lambda r:r), mock.patch.object(lite_host, 'TrajectoryBuffer', LegacyRows):
            baseline = lite_host.play_lite_job(baseline_job)
        self.assertEqual(baseline['status'], 'complete', baseline)
        job = fixture.job()
        job['meta']['phase'] = 'validation'
        original_write = data.write_shard
        captured = []

        def check_write(path, game_id, rows, *args, **kwargs):
            from learning.trajectory_buffer import TrajectoryBuffer
            self.assertIsInstance(rows, TrajectoryBuffer)
            captured.extend(rows)
            self.assertTrue(rows)
            self.assertTrue(all(isinstance(r['global'], np.ndarray) for r in rows))
            return original_write(path, game_id, rows, *args, **kwargs)

        with fixtures.catalog_patch(fixture.rules_dir), mock.patch.object(data, 'write_shard', side_effect=check_write):
            outcome = lite_host.play_lite_job(job)
        self.assertEqual(outcome['status'], 'complete', outcome)
        self.assertTrue(captured)
        self.assertEqual(outcome['coverage'], baseline['coverage'])
        self.assertEqual(outcome['reward_diagnostics'], baseline['reward_diagnostics'])
        # The job record is the run's per-game log line: it carries aggregates,
        # never one entry per decision.
        self.assertFalse({'timings', 'native_timings'} & set(outcome), sorted(outcome))
        def stable_lines(path):
            with gzip.open(path, 'rt') as stream:
                rows = [json.loads(line) for line in stream]
            for row in rows:
                # Wall-clock profiling is intentionally nondeterministic.
                meta = row.get('m', row)
                meta['timing'].pop('ms', None)
            return [json.dumps(row, separators=(',', ':')) for row in rows]
        self.assertEqual(stable_lines(job['shard']), stable_lines(baseline_job['shard']))

    def test_index_streams_rows_with_identical_legacy_payload(self):
        rows = helpers.sequence_rows(turns=3, decisions_per_turn=3)
        expected = json.dumps([sequences._raw(r) for r in rows], separators=(',', ':'), allow_nan=False).encode()
        original = json.dumps

        def bounded_dumps(value, *args, **kwargs):
            if isinstance(value, list) and value and isinstance(value[0], dict):
                raise AssertionError('whole sequence materialized as JSON')
            return original(value, *args, **kwargs)

        with tempfile.TemporaryDirectory() as directory, sequences.IndexedSequenceStore(directory) as store:
            with mock.patch.object(sequences.json, 'dumps', side_effect=bounded_dumps):
                self.assertEqual(store.write(rows), len(rows))
            payload = store.connection.execute('SELECT payload FROM sequences').fetchone()[0]
            self.assertEqual(zlib.decompress(payload), expected)
            self.assertEqual(store.write(rows), len(rows))
            changed = copy.deepcopy(rows)
            changed[0]['reward_raw'] = dict(economy=.9, control=.2, explored=.1)
            with self.assertRaisesRegex(ValueError, 'different raw content'):
                store.write(changed)
        with tempfile.TemporaryDirectory() as directory, sequences.IndexedSequenceStore(directory) as store:
            compact = [rowpack.compact_row(r) for r in rows]
            self.assertEqual(store.write(compact), len(rows))
            self.assertEqual(store.write(compact), len(rows))
            payload = store.connection.execute('SELECT payload FROM sequences').fetchone()[0]
            self.assertEqual(json.loads(zlib.decompress(payload)), json.loads(expected))


if __name__ == '__main__':
    unittest.main()
