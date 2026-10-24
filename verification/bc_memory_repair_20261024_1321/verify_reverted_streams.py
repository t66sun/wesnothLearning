"""Counterfactual checks without editing the working sources."""
import subprocess
import types
import unittest
from unittest import mock

from learning import data, sequences
from tests.v5.test_collection_memory import CollectionMemoryTests


def old_module(name):
    module = types.ModuleType('learning._old_'+name)
    exec(subprocess.check_output(['git','show',f'78acd2d:learning/{name}.py']), module.__dict__)
    return module


legacy_sequences=old_module('sequences');legacy_data=old_module('data')
suite=unittest.TestSuite([CollectionMemoryTests('test_sequence_writer_releases_prior_rows_while_consuming_generator'),
                         CollectionMemoryTests('test_shard_writer_does_not_rebuild_an_entire_raw_row_list')])
with mock.patch.object(sequences,'IndexedSequenceStore',legacy_sequences.IndexedSequenceStore),mock.patch.object(data,'write_shard',legacy_data.write_shard):
    result=unittest.TextTestRunner(verbosity=2).run(suite)
assert len(result.failures)==2 and not result.errors
print('EXPECTED_REVERTED_FAILURES',len(result.failures))
