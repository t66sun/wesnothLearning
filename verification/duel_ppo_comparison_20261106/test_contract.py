"""Admission and paired-evidence fixtures; no collection or training run."""
import gzip
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from learning.common import write_json
from tests import test_validation_cadence as cadence
from verification.duel_ppo_comparison_20261106 import contract, mc, panels


class DuelComparisonContractTests(unittest.TestCase):
    def test_zero_step_batches_count_fresh_and_rejected_work(self):
        state = dict(history=[dict(method='bc', planned_targets=100),
            dict(method='ppo', planned_targets=6001, updates=0, kl_stopped=True,
                 planned_steps=8, committed_steps=0, inspected_decisions=64, committed_decisions=0),
            dict(method='ppo', planned_targets=5000, updates=2, kl_stopped=False,
                 planned_steps=2, committed_steps=2, inspected_decisions=128, committed_decisions=128)])
        budget = dict(history_start=1, fresh_targets=10000, admission_deadline=1800)
        value = contract.ledger(state, budget)
        self.assertEqual(value['fresh_targets'], 11001)
        self.assertEqual(value['overshoot'], 1001)
        self.assertTrue(value['budget_complete'])
        self.assertEqual((value['rejected_steps'], value['never_attempted_steps']), (1, 7))
        self.assertEqual(value['rejected_decision_visits'], 64)
        self.assertEqual(contract.admission_deadline(state, budget, 2100, 1000), 0)

    def test_pending_training_and_validation_keep_hard_settlement_deadline(self):
        budget = dict(history_start=0, fresh_targets=10000, admission_deadline=1800)
        state = dict(history=[dict(method='ppo', planned_targets=12000)])
        for pending in ('pending_train', 'pending_validation'):
            with self.subTest(pending=pending):
                running = state | {pending: {'frozen': True}}
                self.assertEqual(contract.admission_deadline(running, budget, 2100, 1900), 2100)
                self.assertEqual(running[pending], {'frozen': True})
        empty = dict(history=[])
        self.assertEqual(contract.admission_deadline(empty, budget, 2100, 1799), 2100)
        self.assertEqual(contract.admission_deadline(empty, budget, 2100, 1800), 0)

    def test_real_learn_boundary_keeps_whole_batches_and_admits_no_next_batch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runner = cadence.ValidationCadenceTests().runner(root/'duel')
            runner.__class__ = contract.BoundedExperiment
            runner.clock = dict(started=0, deadline=4000000000, update_deadline=4000000000)
            runner.state.update(phase='ppo', stage='ppo', effective=True, policy_shards=[])
            runner.state['counters'].update(environment_games=0, collection_batches=0)
            runner.controller.boundary = Mock()
            runner.save = Mock()
            write_json(root/'budget.json', dict(history_start=0, fresh_targets=10000,
                       admission_deadline=4000000000, hard_deadline=4000000000))
            admissions, passed = [], []
            rows = [{'target': index} for index in range(6001)]

            def schedule(*args, **kwargs):
                self.assertLess(len(admissions), 2, 'admitted a batch after the fresh threshold')
                job = dict(id=str(len(admissions)), shard=str(root/(str(len(admissions))+'.jsonl.gz')),
                           learning={}, meta={})
                admissions.append(job)
                return [job]

            runner.execute = lambda jobs, label: (jobs, [dict(id=j['id'], status='complete', result={}) for j in jobs])

            def settle(prepared_bc=None, *, prepared_ppo=None):
                self.assertIs(prepared_ppo, rows)
                passed.append(len(prepared_ppo))
                runner.state['history'].append(dict(method='ppo', planned_targets=len(prepared_ppo), updates=0))
                runner.state.update(pending_train=None, batch=runner.state['batch']+1)
                return True

            runner.finish_train = settle
            with patch('learning.experiment.rollout_jobs', side_effect=schedule), \
                    patch('learning.experiment.read_shards', return_value=rows):
                runner.learn()
            self.assertEqual(passed, [6001, 6001])
            self.assertEqual(contract.fresh_targets(runner.state), 12002)
            self.assertIsNone(runner.state['pending_train'])

    def test_fixed_opponent_adapter_preserves_current_learner(self):
        with patch.object(contract, 'production_rollouts', return_value=['planned']) as call:
            result = contract.fixed_rollouts('directory', 'current-learner', ['old-self'], ['frozen-Astra'],
                'support', 'v1', 1, 13, 2100, 'unused', current='new-self')
        self.assertEqual(result, ['planned'])
        self.assertEqual(call.call_args.args[1:4], ('current-learner', ['frozen-Astra'], ['frozen-Astra']))
        self.assertEqual(call.call_args.kwargs['current'], 'frozen-Astra')

    def panel(self):
        jobs, results = [], []
        for key in ('bc-weights', 'new-weights'):
            for scene in ('s1', 's2'):
                for rotation in (0, 1):
                    ident = f'{key}-{scene}-{rotation}'
                    jobs.append(dict(id=ident, seed=17 if scene == 's1' else 19, scenario_family=scene,
                        meta=dict(weights_sha256=key, map='map', rotation=rotation, policy_sides=[rotation+1])))
                    results.append(dict(id=ident, status='complete', result=dict(bots=['a','b'],
                        winner=rotation+1 if key == 'new-weights' else 0, faults=[])))
        return dict(jobs=jobs, blocks=2, aliases={'bc':'bc-weights', 'latest':'new-weights', 'selected':'new-weights'}), results

    def test_equal_weight_roles_share_physical_results(self):
        unique, mapping = contract.aliases({'bc': {'weights_sha256':'x'},
            'latest': {'weights_sha256':'y'}, 'selected': {'weights_sha256':'y'}})
        self.assertEqual(len(unique), 2)
        self.assertEqual(mapping['latest'], mapping['selected'])
        plan, results = self.panel()
        scored = panels.panel_scores(plan, results)
        self.assertTrue(scored['complete'])
        self.assertIs(scored['roles']['selected'], scored['roles']['latest'])
        self.assertEqual(scored['roles']['latest'], {'s1':1., 's2':1.})
        self.assertEqual(scored['roles']['bc'], {'s1':1/3, 's2':1/3})

    def test_incomplete_or_unmatched_panels_cannot_become_a_complete_comparison(self):
        plan, results = self.panel()
        self.assertFalse(panels.panel_scores(plan, results[:-1])['complete'])
        plan['jobs'][-1]['seed'] += 1
        with self.assertRaisesRegex(ValueError, 'unmatched'):
            panels.panel_scores(plan, results)
        plan, results = self.panel()
        plan['jobs'] = [j for j in plan['jobs'] if j['scenario_family'] != 's2']
        with self.assertRaisesRegex(ValueError, 'complete scenario roster'):
            panels.panel_scores(plan, results)

    def test_incomplete_validation_cannot_report_an_observed_experiment(self):
        report = dict(validation=dict(complete=False), holdout=dict(complete=True))
        result = contract.completion(True, report, 0)
        self.assertEqual(result['status'], 'incomplete')
        self.assertFalse(result['panels_complete'])
        report['validation']['complete'] = True
        self.assertEqual(contract.completion(True, report, 0)['status'], 'observed')

    def test_crossed_scenario_draw_is_shared_by_all_seeds_and_bc(self):
        bc = dict(s0=.1, s1=.9, s2=.2, s3=.8)
        a = {seed: dict(bc) for seed in (11,12,13)}
        b = {seed: {key:value+.05 for key,value in bc.items()} for seed in a}
        maps = dict(s0='map1', s1='map1', s2='map2', s3='map2')
        rng = Mock()
        rng.choices.side_effect = [[13,11,13], ['s1','s1'], ['s2','s2']]
        with patch.object(contract.random, 'Random', return_value=rng):
            result = contract.crossed_statistics(a, b, bc, maps, samples=1)
        self.assertEqual(rng.choices.call_count, 3)
        for endpoint in result['interval95']['b_minus_bc']:
            self.assertAlmostEqual(endpoint, .05)
        self.assertEqual(result['interval95']['a_minus_bc'], [0.,0.])

    def test_inferior_to_a_and_noninferior_to_bc_are_both_reported(self):
        a = {s: {'x':.7, 'y':.7} for s in (1,2,3)}
        b = {s: {'x':.6, 'y':.6} for s in (1,2,3)}
        result = contract.crossed_statistics(a, b, dict(x=.59,y=.59), dict(x='m',y='m'), samples=20)
        self.assertTrue(result['predicates']['inferior_to_a'])
        self.assertTrue(result['predicates']['noninferior_to_bc_margin_05'])
        self.assertFalse(result['predicates']['superior_to_a'])

    def test_mc_deduplicates_identical_behavior_and_never_uses_teacher_returns(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shard = root/'game.jsonl.gz'
            row = dict(schema=6, source='policy', side=1, choice=0, value=-.2,
                       reward_step=-1/3, terminal_reward=-1/3, version='v38')
            with gzip.open(shard, 'wt') as stream:
                stream.write(json.dumps(row)+'\n')
            write_json(root/'duel/schedules/ppo-batch-000038.json', [dict(shard=str(shard), scenario_family='physical')])
            cell = dict(name='a1', run=str(root), ledger=dict(history=[dict(batch=38,policy_sha256_before='bc')]))
            result = mc.diagnose([cell, cell | dict(name='b1')])
            self.assertEqual(result['unique_trajectories'], 1)
            self.assertEqual(result['aliased_trajectories'], 3)
            self.assertAlmostEqual(result['pooled_unique_trajectories']['bias'], 1/3-.2)
            row['source'] = 'astra'
            with gzip.open(shard, 'wt') as stream:
                stream.write(json.dumps(row)+'\n')
            with self.assertRaisesRegex(ValueError, 'policy behavior'):
                mc.diagnose([cell])


if __name__ == '__main__':
    unittest.main()
