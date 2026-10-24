"""Collector memory regressions using real host records and sequence writes."""
import copy
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zlib

import numpy as np

from tests.v5 import helpers
from tests.v5 import test_pipeline_contract as fixtures
from learning import data, lite_host, rowpack, sequences


class CollectionMemoryTests(unittest.TestCase):
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
        with fixtures.catalog_patch(fixture.rules_dir), mock.patch.object(lite_host, 'compact_row', side_effect=lambda r:r):
            baseline = lite_host.play_lite_job(baseline_job)
        self.assertEqual(baseline['status'], 'complete', baseline)
        job = fixture.job()
        original_write = data.write_shard
        captured = []

        def check_write(path, game_id, rows, *args, **kwargs):
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
