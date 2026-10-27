"""Scenario partitions remain independent of seed-bearing run identities."""
import unittest
import tempfile
import copy
import json
from pathlib import Path
from types import SimpleNamespace

from learning.common import ROOT
from learning.maps import decorate
from learning.schedule import base_job


class ScenarioIdentityTests(unittest.TestCase):
    def test_seed_does_not_move_the_scenario_between_splits(self):
        from learning.data import split

        jobs = [decorate(base_job(ROOT, 'same-board', ['a', 'b'], seed,
                                  1000, 'unused', format_name='duel'),
                         'duel', 0, 'train') for seed in range(32)]
        self.assertEqual(len({job['game_family'] for job in jobs}), 32)
        self.assertEqual(len({split(job['game_family']) for job in jobs}), 2)
        self.assertEqual(len({job['scenario_family'] for job in jobs}), 1)
        self.assertEqual({job['split_rule'] for job in jobs}, {'scenario-v2'})
        self.assertEqual(jobs[0]['game_family'],
                         'ab8a9b778bc432db2c569078daa05b56736fd7f410c878c21384053dc9103dbe')

    def test_physical_changes_but_not_paths_change_the_scenario(self):
        from learning.maps import scenario_family

        job = decorate(base_job(ROOT, 'same-board', ['a', 'b'], 0,
                                1000, 'unused', format_name='duel'), 'duel', 0, 'train')
        moved = dict(job, id='different-id', output='other/path', seed=99, deadline=2000)
        self.assertEqual(scenario_family(job), scenario_family(moved))
        for change in (dict(engine='native'), dict(fog=False), dict(max_turns=9),
                       dict(factions=list(reversed(job['factions'])))):
            with self.subTest(change=change):
                self.assertNotEqual(scenario_family(job), scenario_family(dict(job, **change)))
        moved = copy.deepcopy(job)
        moved['map_override']['starts'][0][0] += 1
        self.assertNotEqual(scenario_family(job), scenario_family(moved))
        for field in ('rules_version', 'combat_version', 'engine_version'):
            moved = copy.deepcopy(job)
            moved['meta'][field] = 'different-profile'
            self.assertNotEqual(scenario_family(job), scenario_family(moved))

    def test_explicit_rules_directory_is_bound_before_schedule_freeze(self):
        from learning.maps import bind_scenario

        job = decorate(base_job(ROOT, 'same-board', ['a', 'b'], 0,
                                1000, 'unused', format_name='duel'), 'duel', 0, 'train')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'catalog-summary.json'
            path.write_text(json.dumps(dict(rules_file_sha256='different-frozen-rules')))
            explicit = dict(job, rules_dir=directory)
            bind_scenario(explicit)
            self.assertNotEqual(job['scenario_family'], explicit['scenario_family'])
            self.assertEqual(job['game_family'], explicit['game_family'])

    def test_scheduled_corpora_do_not_cross_partitions(self):
        from learning.data import split
        from learning.maps import SPLITS
        from learning.schedule import teacher_jobs

        for fmt, count in [('duel', 300), ('ffa4', 600), ('team2v2', 400)]:
            with self.subTest(format=fmt):
                jobs = teacher_jobs(ROOT, ['gpt6astra.zip'], ['gpt6astra.zip'],
                                    'support', 0, 19, 1000, 'unused', formats=[fmt], count=count)
                seen = {}
                for job in jobs:
                    physical = json.dumps([job['map_override'], job['factions'],
                                           job['teams'], job['max_turns']], sort_keys=True)
                    seen.setdefault(physical, set()).add(split(job['scenario_family']))
                    self.assertNotIn(job['meta']['map'], SPLITS[fmt]['holdout'])
                self.assertEqual(len(jobs), count)
                self.assertTrue(all(len(partitions) == 1 for partitions in seen.values()))

    def test_shards_and_index_use_scenario_partition(self):
        from learning.data import read_shards, split, write_shard
        from learning.sequences import IndexedSequenceStore
        from tests.v5.helpers import synthetic_decision_row

        jobs = [decorate(base_job(ROOT, 'same-board', ['a', 'b'], seed,
                                  1000, 'unused', format_name='duel'),
                         'duel', 0, 'train') for seed in range(32)]
        expected = split(jobs[0]['scenario_family'])
        job = next(job for job in jobs if split(job['game_family']) != expected)
        row = synthetic_decision_row()
        row.update(game_family=job['game_family'], scenario_family=job['scenario_family'],
                   split_rule=job['split_rule'])
        result = dict(bots=['a', 'b'], faults=[], winner=1, reason='victory')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'one.jsonl.gz'
            write_shard(path, 'one', [row], result)
            rows = read_shards([path], partition=expected)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['split'], expected)
            self.assertEqual(rows[0]['split_rule'], 'scenario-v2')
            with IndexedSequenceStore(path.parent / 'sequences') as store:
                self.assertEqual(len(store.index(partition=expected)), 1)

    def test_legacy_rows_remain_readable_but_cannot_mix_with_v2(self):
        from learning.data import split, validate_record
        from learning.updates import prepare
        from tests.v5.helpers import synthetic_decision_row

        legacy = synthetic_decision_row()
        legacy['game_family'] = 'family-1'
        legacy['split'] = split(legacy['game_family'])
        validate_record(legacy, 'duel')
        scenario = dict(legacy, game_id='other', scenario_family='family-1',
                        split_rule='scenario-v2')
        with self.assertRaisesRegex(ValueError, 'mixes split rules'):
            prepare(SimpleNamespace(format_name='duel'), [legacy, scenario])

    def test_v2_rejects_incorrect_or_missing_scenario_partition(self):
        from learning.data import split, validate_record
        from tests.v5.helpers import synthetic_decision_row

        row = synthetic_decision_row()
        row.update(split_rule='scenario-v2', scenario_family='fixed-scenario',
                   split=split('fixed-scenario'))
        validate_record(row, 'duel')
        with self.assertRaisesRegex(ValueError, 'crosses data partitions'):
            validate_record(dict(row, split='validation' if row['split'] == 'train' else 'train'))
        with self.assertRaisesRegex(ValueError, 'lacks identity'):
            validate_record(dict(row, scenario_family=None))


if __name__ == '__main__':
    unittest.main()
