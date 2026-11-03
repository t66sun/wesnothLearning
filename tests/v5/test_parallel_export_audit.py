"""File-backed export checks every sequence with complete memory across shard fragments."""
import copy
import gzip
import tempfile
import unittest
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from unittest.mock import patch

from learning.__main__ import main
from learning.common import ROOT
from learning.data import record_split
from learning.export import verify_numerics
from learning.rowpack import pack_line
from learning.sequences import read_raw_shards
from tests.test_core import record
from tests.v5 import helpers


class ParallelExportAuditTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def write_rows(self, name, rows):
        path = self.root / (name + '.jsonl.gz')
        with gzip.open(path, 'wt', encoding='utf-8') as stream:
            for row in rows:
                row['split'] = record_split(row)
                stream.write(pack_line(row) + '\n')
        return path

    def shard(self, name, *entries, fmt='duel'):
        rows = [helpers.pad_candidates(record(2 if fmt == 'duel' else 4, game, turn), count)
                for game, turn, count in entries]
        return self.write_rows(name, [dict(row, format=fmt) for row in rows])

    def test_cli_passes_shard_paths_without_eager_reads_and_selects_worker_count(self):
        for fmt in ('duel', 'ffa4', 'team2v2'):
            (self.root / fmt).mkdir()
            (self.root / fmt / 'one.jsonl.gz').touch()
        args = ['export', '--duel', 'duel.pt', '--ffa4', 'ffa.pt', '--team2v2', 'team.pt',
                '--audit-data', str(self.root), '--output', str(self.root / 'export')]
        for flags, expected in [([], 1), (['--audit-workers', '8'], 8)]:
            with patch('learning.export.export_checkpoints') as exporter, patch('builtins.print'):
                main(args + flags)
            kwargs = exporter.call_args.kwargs
            self.assertEqual(kwargs['audit_workers'], expected)
            self.assertEqual(kwargs['audit_paths']['duel'], [self.root / 'duel/one.jsonl.gz'])

    def test_split_sequences_are_grouped_transitively_and_parallel_matches_serial(self):
        from learning.sequence_parity import _sequence_file_groups, verify_shard_numerics
        first = self.shard('first', ('a', 2, 8))
        bridge = self.shard('bridge', ('a', 1, 8), ('b', 1, 8))
        end = self.shard('end', ('b', 2, 8))
        independent = self.shard('other', ('c', 1, 37))
        paths = [first, bridge, end, independent]
        groups = _sequence_file_groups(paths)
        self.assertCountEqual(groups, [[first, bridge, end], [independent]])
        files = dict(duel=paths, ffa4=[self.shard('ffa', ('f', 1, 37), ('f', 2, 8), fmt='ffa4')])
        models = {fmt: helpers.model(format_name=fmt) for fmt in files}
        expected = {fmt: verify_numerics(model, read_raw_shards(files[fmt], fmt)) for fmt, model in models.items()}
        with patch('learning.sequence_parity.ProcessPoolExecutor', wraps=ProcessPoolExecutor) as pool:
            self.assertEqual(verify_shard_numerics(models, files, workers=2), expected)
        self.assertEqual(pool.call_count, 1)
        self.assertEqual(pool.call_args.kwargs['max_workers'], 2)
        self.assertEqual(verify_shard_numerics(models, files, workers=1), expected)
        duel = dict(duel=models['duel'])
        with self.assertRaisesRegex(ValueError, '37 retained candidates'):
            verify_shard_numerics(duel, dict(duel=[first, bridge, end]), workers=2)
        with self.assertRaisesRegex(ValueError, 'continuous turn memory'):
            verify_shard_numerics(duel, dict(duel=[independent]), workers=2)
        with self.assertRaisesRegex(ValueError, 'workers must be positive'):
            verify_shard_numerics(duel, dict(duel=paths), workers=0)

    def test_reuse_requires_equal_complete_inputs_and_writes(self):
        from learning.sequence_parity import _ParityAudit, _Measurement
        policy = [dict(record(game='game', index=turn), source='policy') for turn in (1, 2)]
        policy[0]['memory_write'] = copy.deepcopy({k: policy[0][k] for k in ('global', 'opponents', 'spatial', 'turn')})
        dagger = [dict(copy.deepcopy(row), source='astra', data_pool='dagger', choice=-1) for row in policy]
        policy_file = self.write_rows('policy', policy)
        audit = _ParityAudit(helpers.model())
        stats = _Measurement(True, 2, 1e-12)
        with patch.object(audit, 'measure', return_value=stats) as scored:
            result = audit.measure_files([policy_file, self.write_rows('dagger', dagger)])
            self.assertEqual(result, _Measurement(True, 4, 1e-12))
            self.assertEqual(scored.call_count, 1)
            dagger[0]['memory_write']['global'][0] += 0.125
            scored.reset_mock()
            result = audit.measure_files([policy_file, self.write_rows('changed', dagger)])
            self.assertEqual(result, _Measurement(True, 4, 1e-12))
            self.assertEqual(scored.call_count, 2)
