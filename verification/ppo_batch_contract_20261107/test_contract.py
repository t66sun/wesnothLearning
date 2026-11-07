"""Paired scheduling and whole-batch settlement using the real PPO runner."""
import json
from pathlib import Path
import random
import unittest
from unittest.mock import Mock, patch

import torch

from learning import ppo
from learning.bc_anchor import weights_sha256
from learning.common import read_json, write_json
from learning.data import read_shards
from learning.schedule import compose_training_scenario
from learning.tasks import FORMULA_ID, TASK_ID, reward_config
from learning.train import restore_rng, train
from tests.v5 import helpers
from tests.v5.test_ppo_plan import _records
from tests.v5.test_ppo_rollout_read_once import runner, write_rows
from verification.duel_ppo_comparison_20261106.contract import ledger
from verification.ppo_batch_contract_20261107.driver import PairedExperiment, ordinal_rollouts


class BatchContractTests(unittest.TestCase):
    def setUp(self):
        self.root = self.enterContext(helpers.temporary_directory())

    def test_same_ordinal_stream_with_different_boundaries(self):
        def schedule(arm, first_batch, batch, count, version):
            jobs = ordinal_rollouts(self.root / arm, version, ['past-policy'], ['gpt6astra.zip'],
                                   'support', version, batch, 19, 1000, 'unused', count,
                                   first_batch=first_batch)
            for job in jobs:
                compose_training_scenario(job, max_turns=30)
                seat = job['meta']['seat']
                self.assertEqual(job['bots'][seat - 1], version)
                self.assertEqual(job['bots'][2 - seat], 'gpt6astra.zip')
                self.assertEqual(job['learning']['sides'][str(seat)]['version'], version)
            return jobs

        def paired_keys(jobs):
            return [(j['training_scenario']['index'], j['meta']['map'], j['meta']['seat'],
                     j['factions'], j['scenario_family'], j['game_family'], j['seed'],
                     j['learning']['sides'][str(j['meta']['seat'])]['sampling_seed'])
                    for j in jobs]

        first = schedule('small', 38, 38, 4, 'v38')
        second = schedule('small', 38, 39, 4, 'v39')
        large = schedule('large', 53, 53, 8, 'v53')
        self.assertEqual((len(first), len(second), len(large)), (4, 4, 8))
        self.assertEqual([j['training_scenario']['index'] for j in large], list(range(8)))
        self.assertEqual(paired_keys(first + second), paired_keys(large))
        self.assertEqual(paired_keys(schedule('large', 53, 54, 8, 'v54')),
                         paired_keys(schedule('small', 38, 40, 4, 'v40')
                                     + schedule('small', 38, 41, 4, 'v41')))

    def arm(self, name):
        (self.root / name).mkdir()
        result, _ = runner(self.root / name / 'duel', [], epochs=2)
        result.__class__ = PairedExperiment
        del result.execute, result.update_deadline
        result.clock['deadline'] = result.clock['update_deadline']
        result.config.update(rollout_games=8, training_max_turns=30)
        result.state.update(batch=38, version=7)
        write_json(result.directory.parent / 'budget.json',
                   dict(first_batch=38, history_start=0, fresh_targets=15,
                        admission_deadline=result.clock['deadline'], hard_deadline=result.clock['deadline']))
        result.save()
        return result

    def collect_fixture(self, jobs, log, tail_status=None):
        self.assertEqual(len(jobs), 8)
        self.assertEqual({job['meta']['version'] for job in jobs}, {'v7'})
        records = _records([(job['id'], 2, 0.) for job in jobs])
        with log.open('a', encoding='utf-8') as stream:
            for index, job in enumerate(jobs):
                if index == 7 and tail_status == 'missing':
                    break
                rows = records[2 * index:2 * index + 2]
                for row in rows:
                    row.update(schema=6, task_id=TASK_ID, reward_config=reward_config(),
                               reward_formula_id=FORMULA_ID, terminal_reward=1., reward_step=row['reward'],
                               game_family=job['game_family'], scenario_family=job['scenario_family'],
                               split='train', split_rule='scenario-v2', version=job['meta']['version'])
                status = 'budget_interrupted' if index == 7 and tail_status == 'budget' else 'complete'
                eligible = status == 'complete' and not (index == 7 and tail_status == 'ineligible')
                if eligible:
                    path = Path(job['shard'])
                    path.parent.mkdir(exist_ok=True)
                    write_rows(path, rows)
                stream.write(json.dumps(dict(id=job['id'], status=status, result=dict(faults=[]),
                                             training_eligible=eligible)) + '\n')

    def test_eight_complete_trajectories_match_after_pending_train_resume(self):
        control = self.arm('control')
        resumed = self.arm('resumed')
        targets = {}

        def capture(label):
            def update(model, optimizer, rows, method, **kwargs):
                targets[label] = [ppo._target_key(row) for row in rows]
                self.assertEqual({row['version'] for row in rows}, {'v7'})
                if label != 'interrupted':
                    return train(model, optimizer, rows, method, **kwargs)

                callback = kwargs['on_step']
                stopped = False

                def stop_at_step(cursor):
                    nonlocal stopped
                    callback(cursor)
                    stopped = True

                kwargs.update(on_step=stop_at_step, deadline=1.)
                with patch('learning.ppo.time.time', side_effect=lambda: 2. if stopped else 0.):
                    return train(model, optimizer, rows, method, **kwargs)
            return update

        for label, result in [('control', control), ('interrupted', resumed)]:
            result.collector = Mock(side_effect=self.collect_fixture)
            random.seed(13)
            torch.manual_seed(0)
            with patch('learning.experiment.train', side_effect=capture(label)):
                result.learn()
            result.collector.assert_called_once()
        saved = torch.load(resumed.directory / 'latest.pt', weights_only=False)
        pending = saved['runner']['pending_train']
        self.assertEqual(len(pending['paths']), 8)
        self.assertEqual(pending['cursor']['updates'], 1)
        self.assertEqual(saved['runner']['counters']['optimizer_steps'], 0)
        self.assertFalse((resumed.directory / 'last_ppo.pt').exists())
        resumed.model = helpers.model(seed=41)
        resumed.model.load_state_dict(saved['model'])
        resumed.optimizer = torch.optim.Adam(resumed.model.parameters(), lr=1e-4)
        resumed.optimizer.load_state_dict(saved['optimizer'])
        resumed.state = saved['runner']
        restore_rng(saved)
        with patch('learning.experiment.read_shards', wraps=read_shards) as read, \
                patch('learning.experiment.train', side_effect=capture('resumed')):
            resumed.learn()
        resumed.collector.assert_called_once()
        self.assertEqual([call.args[0] for call in read.call_args_list if 'stats' not in call.kwargs],
                         [pending['paths']])
        self.assertEqual(targets['control'], targets['interrupted'])
        self.assertEqual(targets['control'], targets['resumed'])
        self.assertEqual(len(set(targets['resumed'])), 16)
        self.assertEqual(len({target[0] for target in targets['resumed']}), 8)
        final_weights = []
        for result in (control, resumed):
            final = torch.load(result.directory / 'last_ppo.pt', weights_only=False)
            self.assertIsNone(final['runner']['pending_train'])
            final_weights.append(weights_sha256(final['model']))
            self.assertEqual(final_weights[-1], weights_sha256(result.model.state_dict()))
            self.assertEqual(ppo._digest(result.model), final['runner']['history'][-1]['policy_sha256_after'])
            budget = read_json(result.directory.parent / 'budget.json')
            self.assertEqual(ledger(result.state, budget)['overshoot'], 1)
            self.assertEqual(result.state['counters']['environment_games'], 8)
        self.assertEqual(final_weights[0], final_weights[1])
        self.assertEqual(control.state['counters'], resumed.state['counters'])
        self.assertEqual(control.state['history'][-1]['cursor'], resumed.state['history'][-1]['cursor'])

    def test_incomplete_batch_keeps_previous_complete_checkpoint(self):
        for status in ('budget', 'missing', 'ineligible'):
            with self.subTest(status=status):
                result = self.arm(status)
                checkpoint = result.directory / 'latest.pt'
                previous = checkpoint.read_bytes()
                result.collector = Mock(side_effect=lambda jobs, log: self.collect_fixture(jobs, log, status))
                with patch('learning.experiment.train', side_effect=AssertionError('partial batch entered PPO')) as update:
                    if status == 'budget':
                        result.learn()
                        with patch('time.time', return_value=result.clock['deadline']):
                            result.learn()
                    else:
                        with self.assertRaisesRegex(RuntimeError, 'incomplete PPO batch'):
                            result.learn()
                    update.assert_not_called()
                result.collector.assert_called_once()
                self.assertEqual(checkpoint.read_bytes(), previous)
                self.assertEqual(result.state['counters']['environment_games'], 0)
                self.assertEqual(result.state['batch'], 38)
                self.assertFalse(result.state['policy_shards'])
                self.assertIsNone(result.state['pending_train'])


if __name__ == '__main__':
    torch.set_num_threads(1)
    unittest.main()
