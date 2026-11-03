"""File-backed export checks every sequence with complete memory across shard fragments."""
import gzip
import tempfile
import unittest
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

    def shard(self, name, *entries):
        path = self.root / (name + '.jsonl.gz')
        with gzip.open(path, 'wt', encoding='utf-8') as stream:
            for game, turn, count in entries:
                row = helpers.pad_candidates(record(game=game, index=turn), count)
                row['split'] = record_split(row)
                stream.write(pack_line(row) + '\n')
        return path

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
        model = helpers.model()
        reference = verify_numerics(model, read_raw_shards(paths, 'duel'))
        self.assertEqual(verify_shard_numerics(model, paths, workers=2), reference)
        self.assertEqual(verify_shard_numerics(model, paths, workers=1), reference)
        with self.assertRaisesRegex(ValueError, '37 retained candidates'):
            verify_shard_numerics(model, [first, bridge, end], workers=2)
        with self.assertRaisesRegex(ValueError, 'continuous turn memory'):
            verify_shard_numerics(model, [independent], workers=2)
        with self.assertRaisesRegex(ValueError, 'workers must be positive'):
            verify_shard_numerics(model, paths, workers=0)
