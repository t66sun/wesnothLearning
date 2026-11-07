"""Configuration and schedule contracts extracted from the pipeline suite."""
from __future__ import annotations

import copy
import hashlib
import json
import time
import unittest
from itertools import combinations
from types import SimpleNamespace
from unittest import mock

from learning import maps, schedule
from learning.experiment import FormatExperiment, coverage_gate, default_config, opening_gate, validate_config
from learning.formats import FORMATS, PLAYERS
from tests.v5.test_pipeline_contract import catalog_patch, frozen_rules, helpers


class ConfigScheduleTests(unittest.TestCase):
    def setUp(self):
        context = helpers.temporary_directory()
        self.directory = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        self.board = dict(width=8, height=6,
                          terrain=[['Gg'] * 8 for _ in range(6)],
                          starts=[[2, 2], [5, 3], [2, 4], [5, 1]])

    def test_cpu_defaults(self):
        with catalog_patch(self.directory / 'no-rules'):
            config = default_config('cpu')
        self.assertEqual(config['workers'], 8)
        self.assertEqual(config['trainer_threads'], 1)
        self.assertEqual(config['device'], 'cpu')
        self.assertEqual(config['final_blocks'], 30)
        self.assertEqual(config['validation_games'], dict(duel=6, ffa4=12, team2v2=24))
        self.assertEqual(config['engine'], 'lite')
        validate_config(config)

    def test_cuda_default_global_workers_is_eight(self):
        config = default_config('cuda')
        self.assertEqual(config['workers'], 8)

    def test_configuration_constraints(self):
        base = default_config('cpu')
        cases = [
            (dict(final_blocks=29), 'formal evaluation needs 30 full blocks per control'),
            (dict(workers=0), 'GLOBAL game process count'),
            (dict(workers=17), 'GLOBAL game process count'),
            (dict(rollout_games=6), 'multiple of four'),
            (dict(rollout_games=0), 'multiple of four'),
            (dict(validation_games=dict(duel=3, ffa4=4, team2v2=8)),
             'full seat rotations'),
            (dict(validation_games=dict(duel=6, ffa4=4, team2v2=4)),
             'both teammate contexts'),
            (dict(formats=['duel', 'duel']), 'formats'),
            (dict(shaping_weight=0.1), 'replace --shaping-weight with control set'),
            (dict(engine='other'), 'engine'),
            (dict(reward_mode='other'), 'unknown reward mode'),
            (dict(bc_accuracy=dict(all=0.4)), 'invalid BC accuracy thresholds'),
            (dict(hours=0), 'hours'),
        ]
        for changes, message in cases:
            config = dict(base, **changes)
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(ValueError, message):
                    validate_config(config)

    def test_lite_selected_for_complete_accepted_catalog(self):
        accepted = frozen_rules(self.directory / 'accepted')
        with catalog_patch(accepted):
            self.assertEqual(default_config('cpu')['engine'], 'lite')

    def test_pending_catalog_does_not_silently_switch_default_engine(self):
        pending = frozen_rules(self.directory / 'pending', complete=False)
        with catalog_patch(pending):
            self.assertEqual(default_config('cpu')['engine'], 'lite')

    def test_missing_catalog_does_not_silently_switch_default_engine(self):
        with catalog_patch(self.directory / 'missing'):
            self.assertEqual(default_config('cpu')['engine'], 'lite')

    def test_coverage_gate_thresholds(self):
        base = dict(status='complete', coverage=dict(total=100, matched=90, kinds={
            'recruit': dict(total=10, matched=8),
            'move': dict(total=50, matched=40),
            'attack': dict(total=40, matched=32)}))
        self.assertTrue(coverage_gate([dict(base)])['passed'])
        self.assertFalse(coverage_gate([dict(base, coverage=dict(total=100, matched=89,
                                                                  kinds=base['coverage']['kinds']))])['passed'])
        faulted = dict(base, result=dict(faults=['abort']))
        self.assertFalse(coverage_gate([faulted])['passed'])
        ineligible = dict(base, training_eligible=False)
        self.assertFalse(coverage_gate([ineligible])['passed'])
        empty = dict(base, coverage=dict(total=0, matched=0, kinds={}))
        self.assertFalse(coverage_gate([empty])['passed'])

    def test_opening_gate_needs_two_complete_games(self):
        def completed():
            return dict(status='complete', meta=dict(seat=1), result=dict(faults=[]), behavior=[
                dict(side=1,left_castle=True, village_captured=True, end_turn=True,
                     remaining_moves=2,usable_moves=2)])
        self.assertTrue(opening_gate([completed(), completed()])['passed'])
        self.assertFalse(opening_gate([completed()])['passed'])
        broken = completed()
        broken['behavior'] = [dict(side=1,left_castle=False, village_captured=True,
                                   end_turn=True, remaining_moves=2,usable_moves=2)]
        self.assertFalse(opening_gate([completed(), broken])['passed'])

    def _evaluation(self, **kwargs):
        with mock.patch.object(maps, 'frozen_map',
                               lambda name: (copy.deepcopy(self.board), 'sha-' + name)):
            return schedule.evaluation_jobs(self.directory, 'policy', 'control',
                                            ['astra'], 1, 11, 1000.0, None,
                                            **kwargs)

    def test_evaluation_schedule_is_deterministic_and_format_aware(self):
        first = self._evaluation()
        second = self._evaluation()
        self.assertEqual([job['id'] for job in first], [job['id'] for job in second])
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))
        ids = [job['id'] for job in first]
        self.assertEqual(len(ids), len(set(ids)))
        groups = {}
        for job in first:
            groups.setdefault((job['meta']['format'], job['meta']['block'],
                               job['meta']['context']), []).append(job)
        for (fmt, block, context), jobs in groups.items():
            rotations = {job['meta']['rotation'] for job in jobs}
            self.assertEqual(rotations, set(range(PLAYERS[fmt])))
            self.assertEqual(len(jobs), PLAYERS[fmt])
        self.assertTrue(all(job['meta']['map_partition'] == 'validation' for job in first))
        for fmt in FORMATS:
            self.assertEqual(len([j for j in first if j['meta']['format'] == fmt]),
                             PLAYERS[fmt] * (2 if fmt == 'team2v2' else 1))

    def test_lite_schedule_contains_no_baseline_bots(self):
        jobs = self._evaluation()
        self.assertFalse(any(bot == 'baseline' for job in jobs
                             if job['meta']['context'] != 'baseline_partner'
                             for bot in job['bots']))
        with mock.patch.object(maps, 'frozen_map',
                               lambda name: (copy.deepcopy(self.board), 'sha-' + name)):
            native_jobs = schedule.evaluation_jobs(self.directory, 'policy', 'control',
                                                   ['baseline'], 1, 12, 1000.0, None,
                                                   formats=('team2v2',))
        self.assertTrue(any('baseline' in job['bots'] for job in native_jobs))

    def test_calibration_schedule_pairs_fixed_opponents(self):
        fixed = ['A', 'B', 'C']
        with mock.patch.object(maps, 'frozen_map',
                               lambda name: (copy.deepcopy(self.board), 'sha-' + name)):
            jobs = schedule.calibration_jobs(self.directory, fixed, 1, 3, 1000.0, None,
                                             formats=('duel',))
        pairs = list(combinations(fixed, 2))
        self.assertEqual(len(jobs), len(pairs) * PLAYERS['duel'])
        self.assertEqual({job['id'].split('-')[0] for job in jobs},
                         {f'cal{index:02}' for index in range(len(pairs))})
        self.assertEqual(len({job['id'] for job in jobs}), len(jobs))
        for job in jobs:
            self.assertEqual(job['meta']['map_partition'], 'validation')

    def test_base_job_format_contract(self):
        team = schedule.base_job(self.directory, 'team', ['a'] * 4, 5, time.time() + 10,
                                 None, format_name='team2v2')
        self.assertEqual(team['teams'], [1, 2, 1, 2])
        self.assertEqual(team['max_turns'], 30)
        self.assertEqual(team['factions'], schedule.factions(0, 4))
        duel = schedule.base_job(self.directory, 'duel', ['a', 'b'], 5, time.time() + 10,
                                 None, format_name='duel')
        self.assertIsNone(duel['teams'])

    def test_teacher_and_rollout_schedules(self):
        with self.assertRaisesRegex(ValueError, 'one supervision teacher'):
            schedule.teacher_jobs(self.directory, ['/x/first.zip','/x/second.zip'], ['astra'], {}, 1, 1,
                                  time.time() + 10, None, formats=('duel',))
        with mock.patch.object(maps, 'frozen_map',
                               lambda name: (copy.deepcopy(self.board), 'sha-' + name)):
            teachers = schedule.teacher_jobs(self.directory, ['/x/gpt6astra.zip'], ['astra'],
                                             {}, 1, 1, time.time() + 10, None,
                                             formats=('duel', 'ffa4'))
        self.assertEqual(len(teachers), 2)
        self.assertTrue(all(job['meta']['phase'] == 'teacher' for job in teachers))
        self.assertTrue(all(job['shard'].endswith('.jsonl.gz') for job in teachers))
        self.assertTrue(all('sides' in job['learning'] for job in teachers))
        self.assertEqual(len({job['id'] for job in teachers}), len(teachers))
        with mock.patch.object(maps, 'frozen_map',
                               lambda name: (copy.deepcopy(self.board), 'sha-' + name)):
            rollouts = schedule.rollout_jobs(self.directory, 'policy', '/x/history.pt',
                                             ['astra'], {}, 2, 1, 1, time.time() + 10,
                                             None, formats=('duel',))
        self.assertEqual(len(rollouts), 4)
        self.assertTrue(all(job['meta']['phase'] == 'ppo' for job in rollouts))
        self.assertEqual(len({job['id'] for job in rollouts}), 4)
        self.assertTrue(all(next(iter(job['learning']['sides'].values()))['version'] == 2
                            for job in rollouts))

    def test_freeze_schedule_is_write_once(self):
        jobs = [dict(id='one'), dict(id='two')]
        path = self.directory / 'schedules' / 'unit.json'
        digest = schedule.freeze_schedule(path, jobs)
        self.assertEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(schedule.freeze_schedule(path, jobs), digest)
        with self.assertRaisesRegex(ValueError, 'refusing to alter an existing frozen schedule'):
            schedule.freeze_schedule(path, [dict(id='other')])

    def test_lite_experiment_rewrites_baseline_jobs(self):
        experiment = FormatExperiment.__new__(FormatExperiment)
        experiment.directory = self.directory
        from learning.tasks import TASK_ID
        experiment.config = dict(engine='lite', allow_approximate=False,task_id=TASK_ID)
        experiment.teachers = ['/x/gpt6astra.zip']
        experiment.controller = SimpleNamespace(freeze=lambda: helpers.config())
        collected = []
        experiment.collector = lambda pending, log: collected.extend(pending)
        jobs = [dict(id='job-a', bots=['baseline', 'control'],
                     meta=dict(format='team2v2', context='baseline_partner'))]
        returned, results = experiment.execute(jobs, 'unit')
        self.assertEqual(returned[0]['bots'], ['/x/gpt6astra.zip', 'control'])
        self.assertEqual(returned[0]['meta']['context'], 'astra_partner')
        self.assertEqual(returned[0]['engine'], 'lite')
        self.assertEqual(returned[0]['meta']['engine_id'], 'lite')
        self.assertTrue(collected)
        self.assertEqual(results, [])


