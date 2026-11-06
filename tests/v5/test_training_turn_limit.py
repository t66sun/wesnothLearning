"""The finite task uses one 30-round horizon across training and evaluation."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from learning.__main__ import parser, run_config
from learning.common import sha256, write_json
from learning.data import split
from learning.experiment import FormatExperiment, default_config, validate_config
from learning.formats import FORMATS, PLAYERS
from learning.maps import scenario_family
from learning.sample import opening_map
from learning.schedule import teacher_jobs, rollout_jobs, evaluation_jobs
from learning.updates import BATCH_CONTRACT
from learning.tasks import TASK_ID


def runner(directory, config):
    result = object.__new__(FormatExperiment)
    result.directory = Path(directory)
    result.config = config
    result.controller = SimpleNamespace(freeze=lambda: {})
    result.teachers = ['gpt6astra.zip']
    result.collector = mock.Mock()
    return result


def jobs(directory, fmt):
    teacher = teacher_jobs(directory, ['gpt6astra.zip'], ['gpt6astra.zip'], 'support',
                           0, 19, 1000, 'unused', formats=[fmt], count=2)
    policy = rollout_jobs(directory, 'policy', ['policy'], ['gpt6astra.zip'], 'support',
                          'v1', 0, 19, 1000, 'unused', formats=[fmt])
    policy[-1]['meta']['phase'] = 'dagger_refresh'
    return teacher + policy


class TrainingTurnLimitTests(unittest.TestCase):
    def test_default_cli_and_invalid_limits(self):
        config = default_config('cpu')
        self.assertEqual(config['training_max_turns'], 30)
        self.assertEqual(config['task_id'], TASK_ID)
        requested = run_config(parser().parse_args(['run', '--training-max-turns', '11']))
        with self.assertRaisesRegex(ValueError, 'training_max_turns'):
            validate_config(requested)
        self.assertEqual(requested['training_max_turns'], 11)
        self.assertEqual(requested['bc_accuracy'], config['bc_accuracy'])
        self.assertEqual(requested['final_blocks'], 30)
        for limit in (0, -1, 29, 31, 60):
            with self.assertRaisesRegex(ValueError, 'training_max_turns'):
                validate_config(config | dict(training_max_turns=limit))
        del config['training_max_turns']
        with self.assertRaisesRegex(ValueError, 'training_max_turns'):
            validate_config(config)

    def test_teacher_ppo_and_refresh_use_actual_limit_and_partition(self):
        for engine in ('lite', 'native'):
            for fmt in FORMATS:
                with self.subTest(engine=engine, format=fmt), tempfile.TemporaryDirectory() as tmp, \
                     mock.patch('learning.maps.frozen_map', return_value=(opening_map(PLAYERS[fmt]), '0'*64)):
                    experiment = runner(tmp, default_config('cpu', engine=engine))
                    scheduled, _ = experiment.execute(jobs(tmp, fmt), 'training')
                    self.assertEqual({job['max_turns'] for job in scheduled}, {30})
                    self.assertEqual({job['task_id'] for job in scheduled}, {TASK_ID})
                    self.assertEqual(json.loads((Path(tmp)/'schedules/training.json').read_text()), scheduled)
                    self.assertEqual(experiment.collector.call_args.args[0], scheduled)
                    for job in scheduled:
                        self.assertEqual(job['scenario_family'], scenario_family(job))
                        self.assertNotEqual(job['scenario_family'], scenario_family(job | dict(max_turns=60)))
                        if job.get('training_scenario'):
                            self.assertEqual(split(job['scenario_family']), 'train')

    def test_default_evaluation_and_existing_frozen_schedule(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch('learning.maps.frozen_map', return_value=(opening_map(2), '0'*64)):
            config = default_config('cpu')
            experiment = runner(tmp, config)
            initial = jobs(tmp, 'duel')
            scheduled, _ = experiment.execute(copy.deepcopy(initial), 'current')
            self.assertEqual({job['max_turns'] for job in scheduled}, {30})
            scheduled, _ = experiment.execute(copy.deepcopy(initial), 'bounded')
            self.assertEqual({job['max_turns'] for job in scheduled}, {30})
            frozen = (Path(tmp)/'schedules/bounded.json').read_bytes()
            resumed, _ = experiment.execute(copy.deepcopy(initial), 'bounded')
            self.assertEqual(resumed, scheduled)
            self.assertEqual((Path(tmp)/'schedules/bounded.json').read_bytes(), frozen)
            evaluation = evaluation_jobs(tmp, 'policy', 'gpt6astra.zip', ['gpt6astra.zip'],
                                          1, 19, 1000, 'unused', formats=['duel'])
            evaluated, _ = experiment.execute(evaluation, 'evaluation')
            self.assertEqual({job['max_turns'] for job in evaluated}, {30})

    def test_resume_restores_frozen_limit(self):
        from learning.coordinator import Experiment
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            baseline = directory/'baseline.engine'
            baseline.write_bytes(b'fixture')
            config = default_config('cpu')
            write_json(directory/'manifest.json', dict(config=config, task_id=TASK_ID, opponents=[], source={}, batch_contract=BATCH_CONTRACT,
                baseline=dict(path=str(baseline), sha256=sha256(baseline))))
            write_json(directory/'clock.json', dict(started=1000., update_deadline=2000., deadline=3000.))
            requested = run_config(parser().parse_args(['run', '--resume', tmp, '--training-max-turns', '11']))
            resumed = Experiment(directory, config=requested, resume=True)
            self.assertEqual(resumed.config['training_max_turns'], 30)

    def test_opening_probe_keeps_its_five_turn_limit(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch('learning.maps.frozen_map', return_value=(opening_map(2), '0'*64)):
            experiment = runner(tmp, default_config('cpu'))
            probe = jobs(tmp, 'duel')[-1]
            probe.pop('training_scenario')
            probe['max_turns'] = 5
            probe['meta']['opening'] = True
            scheduled, _ = experiment.execute([probe], 'opening')
            self.assertEqual(scheduled[0]['max_turns'], 5)
            self.assertEqual(scheduled[0]['scenario_family'], scenario_family(scheduled[0]))

    def test_manual_loop_passes_the_declared_turn_limit(self):
        from tests import bounded_training_loop as loop
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(loop, 'OUT', Path(tmp)/'observed'), \
             mock.patch.object(loop, 'RUN', Path(tmp)/'run'), \
             mock.patch.object(loop, 'stage', return_value=False) as stage, \
             mock.patch.dict('os.environ', SOURCE_COMMIT='fixture', WESNOTH_EXE='unused'):
            self.assertEqual(loop.main(), 1)
            plan = json.loads((loop.OUT/'plan.json').read_text())
            args = stage.call_args.args[1]
            config = run_config(parser().parse_args(args[4:]))
            self.assertEqual(config.get('training_max_turns', 60), plan['turn_limit'])


if __name__ == '__main__':
    unittest.main()
