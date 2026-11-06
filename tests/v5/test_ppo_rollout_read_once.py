"""A fresh PPO batch reuses one complete read; resumed batches reread shards."""
import copy
import gzip
import random
import unittest
from unittest.mock import Mock, patch

import torch

from learning import experiment, ppo
from learning.common import write_json
from learning.data import advantages, read_shards, split
from learning.experiment import FormatExperiment
from learning.rowpack import pack_line
from learning.tasks import FORMULA_ID, TASK_ID, reward_config
from learning.train import restore_rng, train
from learning.updates import rollout_identity
from tests import test_validation_cadence as cadence
from tests.v5 import helpers
from tests.v5.test_ppo_plan import _records


def write_rows(path, rows):
    with gzip.open(path, 'wt', encoding='utf-8') as stream:
        for row in rows:
            raw = {key: value for key, value in row.items()
                   if key not in ('_history', '_sequence_complete')}
            stream.write(pack_line(raw) + '\n')


def runner(directory, paths, *, epochs=1):
    directory.mkdir()
    write_json(directory.parent / 'manifest.json', dict(test='rollout-read-once'))
    result = cadence.ValidationCadenceTests().runner(directory)
    result.config.update(engine='lite', epochs=epochs, seed=5, minibatch=2, bc_records=2)
    result.model = helpers.model(seed=41)
    result.optimizer = torch.optim.Adam(result.model.parameters(), lr=1e-4)
    result.state.update(phase='ppo', stage='ppo', effective=True, policy_shards=[])
    result.state['counters'].update(environment_games=0, collection_batches=0)
    result.controller.boundary = Mock()
    result.controller.state_dict = lambda: {}
    result.save = lambda: FormatExperiment.save(result)
    result.update_deadline = lambda: float('inf') if result.state['batch'] == 0 else 0.
    jobs = [dict(id=f'job-{index}', shard=str(path), learning={}) for index, path in enumerate(paths)]
    results = [dict(id=job['id'], status='complete', result=dict(faults={})) for job in jobs]
    result.execute = Mock(return_value=(jobs, results))
    return result, jobs


class RolloutReadOnceTests(unittest.TestCase):
    def setUp(self):
        self.directory = self.enterContext(helpers.temporary_directory())
        self.rows = _records([('b', 12, 0.)])
        for row in self.rows:
            row.update(schema=6, task_id=TASK_ID, reward_config=reward_config(),
                       reward_formula_id=FORMULA_ID, terminal_reward=1.,
                       reward_step=row['reward'])
        # An uncovered committed first turn is context for every later target.
        self.rows[0]['choice'] = -1
        self.path = self.directory / 'policy.jsonl.gz'
        write_rows(self.path, self.rows)
        self.paths = [str(self.path)]

    def fresh(self, name='fresh', *, epochs=1, paths=None):
        return runner(self.directory / name, paths or self.paths, epochs=epochs)

    def learn(self, result, jobs):
        with patch('learning.experiment.rollout_jobs', return_value=jobs):
            result.learn()

    def test_new_batch_reads_once_without_truncating_tail_or_raw_prefix(self):
        result, jobs = self.fresh()
        complete = read_shards(self.paths, format_name='duel')
        calls, targets = [], []

        def read(paths, **kwargs):
            rows = read_shards(paths, **kwargs)
            calls.append((list(paths), kwargs, rows))
            return rows

        def update(model, optimizer, rows, method, **kwargs):
            targets.extend(rows)
            self.assertEqual(result.state['pending_train']['identity']['train'], rollout_identity(complete))
            return train(model, optimizer, rows, method, **kwargs)

        with patch('learning.experiment.read_shards', side_effect=read), \
                patch('learning.experiment.train', side_effect=update):
            self.learn(result, jobs)
        rollout_calls = [call for call in calls if 'stats' not in call[1]]
        self.assertEqual(len(rollout_calls), 1, 'fresh rollout must be read exactly once')
        self.assertEqual(rollout_calls[0][1], dict(format_name='duel', expected_task=TASK_ID))
        self.assertEqual(len(calls), 2, 'the separate rehearsal read remains unchanged')
        self.assertGreater(len(targets), result.config['bc_records'])
        self.assertEqual(len(targets), 11)
        self.assertEqual([ppo._target_key(row) for row in targets], [ppo._target_key(row) for row in complete])
        self.assertEqual(targets[-1]['turn'], 12)
        self.assertEqual([row['turn'] for row in targets[-1]['_history']], list(range(1, 12)))
        self.assertEqual(result.state['history'][-1]['planned_targets'], 11)
        self.assertEqual(result.state['history'][-1]['repeated_targets'], 0)

    def test_empty_batch_keeps_existing_skip_behavior(self):
        write_rows(self.path, [])
        result, jobs = self.fresh()
        with patch('learning.experiment.read_shards', wraps=read_shards) as read, \
                patch('learning.experiment.train') as update:
            self.learn(result, jobs)
        read.assert_called_once_with(self.paths, format_name='duel', expected_task=TASK_ID)
        update.assert_not_called()
        self.assertEqual(result.state['batch'], 1)
        self.assertEqual(result.state['version'], 0)
        self.assertEqual(result.state['history'], [])
        self.assertIsNone(result.state['pending_train'])

    def test_nontraining_rows_are_rejected_before_identity_or_training(self):
        family = next(f'heldout-{i}' for i in range(100) if split(f'heldout-{i}') == 'validation')
        heldout = copy.deepcopy(self.rows[1:])
        for row in heldout:
            row.update(game_id=family, game_family=family, split='validation', sequence_start=True)
        validation = self.directory / 'validation.jsonl.gz'
        write_rows(validation, heldout)
        for label, paths in [('mixed', self.paths + [str(validation)]), ('all-heldout', [str(validation)])]:
            with self.subTest(label=label):
                result, jobs = self.fresh(label, paths=paths)
                with patch('learning.experiment.train') as update, \
                        self.assertRaisesRegex(ValueError, 'batch row excluded by split'):
                    self.learn(result, jobs)
                update.assert_not_called()
                self.assertNotIn('identity', result.state['pending_train'])
                self.assertEqual(result.state['version'], 0)

    def trace(self, result, invoke):
        captured = dict(gradients=[], identities=[], targets=[], advantages=[])
        original_clip = torch.nn.utils.clip_grad_norm_

        def clip(parameters, *args, **kwargs):
            parameters = list(parameters)
            captured['gradients'].append([p.grad.detach().clone() if p.grad is not None else None
                                          for p in parameters])
            return original_clip(parameters, *args, **kwargs)

        def update(model, optimizer, rows, method, **kwargs):
            captured['identities'].append(copy.deepcopy(result.state['pending_train']['identity']))
            captured['targets'].append([ppo._target_key(row) for row in rows])
            captured['advantages'].append(advantages(rows))
            metrics = train(model, optimizer, rows, method, **kwargs)
            captured['metrics'] = metrics
            return metrics

        random.seed(13)
        torch.manual_seed(0)
        with patch('learning.experiment.train', side_effect=update), \
                patch('learning.ppo.torch.nn.utils.clip_grad_norm_', side_effect=clip):
            invoke()
        captured['rng'] = random.getstate()
        captured['torch_rng'] = torch.get_rng_state()
        return captured

    def legacy(self, result):
        # Previous new-batch sequence: discard bounded pre-read, then finish
        # from paths. Rehearsal quotas and every downstream operation are real.
        self.assertTrue(read_shards(self.paths, partition='train', limit=result.config['bc_records'], format_name='duel'))
        result.state['policy_shards'] = self.paths
        result.state['pending_train'] = dict(method='ppo', paths=self.paths,
            cursor=dict(epoch=0, step=0), reward_config=result.controller.freeze())
        self.assertTrue(result.finish_train())

    def test_prepared_and_reread_paths_have_identical_targets_loss_gradients_and_rng(self):
        fresh, jobs = self.fresh()
        legacy, _ = self.fresh('legacy')
        actual = self.trace(fresh, lambda: self.learn(fresh, jobs))
        expected = self.trace(legacy, lambda: self.legacy(legacy))
        for key in ('identities', 'targets', 'advantages', 'metrics', 'rng'):
            self.assertEqual(actual[key], expected[key], key)
        self.assertTrue(torch.equal(actual['torch_rng'], expected['torch_rng']))
        self.assertEqual(len(actual['gradients']), 1)
        for actual_step, expected_step in zip(actual['gradients'], expected['gradients']):
            for actual_grad, expected_grad in zip(actual_step, expected_step):
                if expected_grad is None:
                    self.assertIsNone(actual_grad)
                else:
                    torch.testing.assert_close(actual_grad, expected_grad, rtol=0, atol=0)
        self.assertEqual(ppo._digest(fresh.model), ppo._digest(legacy.model))

    def test_kl_stop_cursor_is_identical_for_prepared_and_reread_paths(self):
        for row in self.rows:
            row['log_probability'] -= .5
        write_rows(self.path, self.rows)
        fresh, jobs = self.fresh()
        legacy, _ = self.fresh('legacy')
        actual = self.trace(fresh, lambda: self.learn(fresh, jobs))
        expected = self.trace(legacy, lambda: self.legacy(legacy))
        self.assertTrue(actual['metrics']['kl_stopped'])
        self.assertEqual(actual['metrics']['updates'], 0)
        self.assertEqual(actual['metrics'], expected['metrics'])
        self.assertEqual(actual['rng'], expected['rng'])
        self.assertEqual(ppo._digest(fresh.model), ppo._digest(legacy.model))

    def test_pending_resume_rereads_and_matches_uninterrupted_checkpoint(self):
        control, control_jobs = self.fresh('control', epochs=2)
        expected = self.trace(control, lambda: self.learn(control, control_jobs))
        resumed, resumed_jobs = self.fresh('resumed', epochs=2)
        stopped = [False]

        def interrupt(*args, **kwargs):
            callback = kwargs['on_step']

            def step(cursor):
                callback(cursor)
                stopped[0] = True

            kwargs.update(on_step=step, deadline=1.)
            with patch('learning.ppo.time.time', side_effect=lambda: 2. if stopped[0] else 0.):
                return train(*args, **kwargs)

        random.seed(13)
        torch.manual_seed(0)
        with patch('learning.experiment.train', side_effect=interrupt):
            self.learn(resumed, resumed_jobs)
        saved = torch.load(resumed.directory / 'latest.pt', weights_only=False)
        self.assertEqual(saved['runner']['pending_train']['cursor']['updates'], 1)
        resumed.model.load_state_dict(saved['model'])
        resumed.optimizer.load_state_dict(saved['optimizer'])
        resumed.state = copy.deepcopy(saved['runner'])
        restore_rng(saved)
        with patch('learning.experiment.read_shards', wraps=read_shards) as read:
            resumed.learn()
        full_reads = [call for call in read.call_args_list if 'stats' not in call.kwargs]
        self.assertEqual(len(full_reads), 1)
        self.assertEqual(full_reads[0].kwargs, dict(format_name='duel', expected_task=TASK_ID))
        self.assertEqual(ppo._digest(resumed.model), ppo._digest(control.model))
        self.assertEqual(resumed.state['counters'], control.state['counters'])
        self.assertEqual(resumed.state['history'][-1]['cursor'], expected['metrics']['cursor'])
        self.assertEqual(resumed.state['history'][-1]['loss'], expected['metrics']['loss'])
        self.assertEqual(random.getstate(), expected['rng'])

    def test_pending_resume_rejects_changed_target_or_raw_prefix_content(self):
        for label in ('target', 'raw-prefix'):
            with self.subTest(label=label):
                write_rows(self.path, self.rows)
                result, jobs = self.fresh(label)
                real_train = experiment.train

                def pause(*args, **kwargs):
                    return real_train(*args, **dict(kwargs, deadline=0.))

                with patch('learning.experiment.train', side_effect=pause):
                    self.learn(result, jobs)
                self.assertIsNotNone(result.state['pending_train']['identity'])
                changed = copy.deepcopy(self.rows)
                if label == 'target':
                    changed[-1]['value'] += .125
                else:
                    changed[0]['global'][0] += .125
                write_rows(self.path, changed)
                with patch('learning.experiment.train') as update, \
                        self.assertRaisesRegex(ValueError, 'scheduled rollout changed since the checkpoint'):
                    result.learn()
                update.assert_not_called()


if __name__ == '__main__':
    torch.set_num_threads(1)
    unittest.main()
