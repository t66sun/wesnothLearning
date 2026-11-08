"""Trace the branch's frozen lambda into actual PPO targets and resumed updates."""
from contextlib import redirect_stderr
from io import StringIO
import json
import time
import unittest
from unittest.mock import Mock, patch

import torch

from learning import experiment, ppo
from learning.bc_anchor import weights_sha256
from learning.branch import prepare
from learning.common import read_json, sha256, write_json
from learning.data import write_shard
from learning.phases import request_phase
from learning.tasks import bind_result, reward_config, value_target
from learning.train import restore_rng
from tests.v5 import helpers
from tests.v5.test_ppo_plan import _records
from verification.ppo_batch_contract_20261107.driver import PairedExperiment


class FrozenGaeTests(unittest.TestCase):
    def test_run_cli_freezes_lambda_only_on_new_runs(self):
        from learning.__main__ import main

        root = self.enterContext(helpers.temporary_directory())
        write_json(root/'manifest.json', dict(config=experiment.default_config('cpu')))
        self.assertEqual(experiment.default_config('cpu')['gae_lambda'], .95)
        with patch('learning.coordinator.Experiment') as launch:
            launch.return_value.run.return_value = dict(status='stage_complete')
            main(['run', '--run-dir', 'runs/new', '--gae-lambda', '1.0'])
            self.assertEqual(launch.call_args.kwargs['config']['gae_lambda'], 1.)
            launch.reset_mock()
            errors = StringIO()
            with redirect_stderr(errors), self.assertRaises(SystemExit):
                main(['run', '--resume', str(root), '--gae-lambda', '1.0'])
            self.assertIn('resume keeps the frozen GAE lambda', errors.getvalue())
            launch.assert_not_called()
        for value in (-.1, 1.1, float('nan')):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'invalid discount'):
                experiment.validate_config(experiment.default_config('cpu') | dict(gae_lambda=value))

    def test_branch_rollout_targets_and_pending_resume(self):
        root = self.enterContext(helpers.temporary_directory())
        self.enterContext(patch.object(experiment.FormatExperiment, 'ensure_export', return_value='policy'))
        self.enterContext(patch.object(experiment, 'Policy',
                                     side_effect=lambda fmt: helpers.model(format_name=fmt, seed=41)))
        deadline = time.time() + 120
        clock = dict(started=time.time(), update_deadline=deadline, deadline=deadline)
        config = experiment.default_config('cpu') | dict(formats=['duel'], phase='bc',
            reward_mode='fixed', seed=19, rollout_games=8, epochs=2, minibatch=2, human_data=str(root))

        def manifest(folder, settings):
            folder.mkdir()
            value = dict(config=settings, baseline=dict(path='unused'), opponents=[dict(path='gpt6astra.zip')])
            write_json(folder/'manifest.json', value)
            write_json(folder/'clock.json', clock)
            return value

        # An existing BC manifest has no run-level lambda and a complete checkpoint.
        parent = root/'parent'
        old = manifest(parent, {key: value for key, value in config.items() if key != 'gae_lambda'})
        bc = experiment.FormatExperiment(parent/'duel', 'duel', old, clock, Mock())
        self.assertEqual(bc.controller.freeze(), reward_config(mode='fixed'))
        for param in bc.model.parameters():
            param.grad = torch.zeros_like(param)
        bc.optimizer.step()
        bc.state.update(effective=True, version=7, batch=38, history=[dict(method='bc', updates=1)])
        bc.save()
        bc._write_checkpoint(parent/'duel/last_bc.pt')
        parent_pin = sha256(parent/'duel/latest.pt')

        def collect(jobs, log):
            self.assertEqual(len(jobs), 8)
            with log.open('a', encoding='utf-8') as stream:
                for i, job in enumerate(jobs):
                    rows = _records([(job['id'], 2, 0.)])
                    for j, row in enumerate(rows):
                        row.update(task_id=job['task_id'], reward_config=job['reward_config'],
                            reward_formula_id=job['reward_config']['reward_formula_id'],
                            game_family=job['game_family'], scenario_family=job['scenario_family'],
                            split='train', split_rule='scenario-v2', version=job['meta']['version'],
                            value=.25 - j*.75)
                    cap = i % 2 == 0
                    result = bind_result(dict(bots=job['bots'], winner=0 if cap else 1, faults=[],
                        reason='turn_limit' if cap else 'victory', turns=31 if cap else 2), job)
                    report = write_shard(job['shard'], job['id'], rows, result)
                    self.assertEqual(report['written'], 2)
                    stream.write(json.dumps(dict(id=job['id'], status='complete', result=result,
                                                 training_eligible=True)) + '\n')

        def branch(name, lam):
            folder = root/name
            child = manifest(folder, config | dict(gae_lambda=lam))
            lineage = prepare(parent, folder, ['duel'], seed=config['seed'], reset_optimizer=True)
            write_json(folder/'branch.json', lineage | dict(parent=str(parent), parent_clock=clock,
                                                           parent_manifest_sha256=sha256(parent/'manifest.json')))
            collector = Mock(side_effect=collect)
            runner = PairedExperiment(folder/'duel', 'duel', child, clock, collector, branch=True)
            self.assertEqual(weights_sha256(runner.model.state_dict()), weights_sha256(bc.model.state_dict()))
            self.assertFalse(runner.optimizer.state)
            write_json(folder/'budget.json', dict(first_batch=38, history_start=1,
                       admission_deadline=deadline-10, hard_deadline=deadline))
            request_phase(folder, 'ppo', ppo_batches=1)
            return runner

        def observe(lam, *, interrupt=False):
            def targets(rows, **kwargs):
                adv, returns = ppo_advantages(rows, **kwargs)
                self.assertEqual({row['reward_config']['gae_lambda'] for row in rows}, {lam})
                self.assertEqual({row['terminal_reward'] for row in rows}, {2/3-1, 1.})
                self.assertTrue(all(row['value_valid'] and not row['truncated'] for row in rows))
                if lam == 1.:
                    for row, value, advantage in zip(rows, returns, adv):
                        self.assertAlmostEqual(value, value_target(row))
                        self.assertAlmostEqual(advantage, value_target(row)-row['value'])
                else:
                    self.assertTrue(any(abs(value-value_target(row)) > .01 for row, value in zip(rows, returns)))
                return adv, returns

            def train(*args, **kwargs):
                stopped = False
                callback = kwargs['on_step']

                def stop(cursor):
                    nonlocal stopped
                    callback(cursor)
                    stopped = True

                if interrupt:
                    kwargs.update(on_step=stop, deadline=1.)
                    with patch('learning.ppo.time.time', side_effect=lambda: 2. if stopped else 0.):
                        return runner_train(*args, **kwargs)
                return runner_train(*args, **kwargs)

            return patch.object(ppo, 'advantages', side_effect=targets), patch.object(experiment, 'train', train)

        ppo_advantages, runner_train = ppo.advantages, experiment.train
        baseline, control, interrupted = (branch(name, lam) for name, lam in
                                          [('baseline', .95), ('control', 1.), ('interrupted', 1.)])
        for runner, lam in ((baseline, .95), (control, 1.), (interrupted, 1.)):
            # Each real arm starts in its own trainer process with the saved branch RNG.
            restore_rng(torch.load(runner.directory/'latest.pt', weights_only=False))
            target_patch, train_patch = observe(lam, interrupt=runner is interrupted)
            with target_patch as targets, train_patch:
                runner.learn()
            targets.assert_called_once()
            runner.collector.assert_called_once()
            schedule = read_json(runner.directory/'schedules/ppo-batch-000038.json')
            self.assertEqual({job['reward_config']['gae_lambda'] for job in schedule}, {lam})

        folder = interrupted.directory.parent
        budget = (folder/'budget.json').read_bytes()
        saved = torch.load(interrupted.directory/'latest.pt', weights_only=False)['runner']
        pending = saved['pending_train']
        self.assertEqual(pending['cursor']['updates'], 1)
        self.assertEqual(pending['reward_config']['gae_lambda'], 1.)
        collector = Mock(side_effect=AssertionError('pending update must not recollect'))
        resumed = PairedExperiment(interrupted.directory, 'duel', read_json(folder/'manifest.json'),
                                   read_json(folder/'clock.json'), collector, resume=True)
        target_patch, train_patch = observe(1.)
        with target_patch as targets, train_patch:
            resumed.learn()
        targets.assert_called_once()
        collector.assert_not_called()
        self.assertEqual((folder/'budget.json').read_bytes(), budget)
        self.assertEqual(resumed.state['phase_deadline'], saved['phase_deadline'])
        self.assertIsNone(resumed.state['pending_train'])
        self.assertEqual(ppo._digest(resumed.model), ppo._digest(control.model))
        self.assertNotEqual(ppo._digest(resumed.model), ppo._digest(baseline.model))
        self.assertEqual(resumed.state['counters'], control.state['counters'])
        self.assertEqual(sha256(parent/'duel/latest.pt'), parent_pin)
