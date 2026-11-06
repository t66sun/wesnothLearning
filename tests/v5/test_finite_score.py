"""Finite-score arithmetic and real engine boundary fixtures; no training run."""
import copy
import gzip
import json
import time
import unittest
from pathlib import Path
from unittest import mock

import torch
from lupa import LuaRuntime

from learning import features
from learning.data import advantages, read_shards, validate_record, write_shard
from learning.evaluate import official_score
from learning.rewards import RewardConfig, terminal_rewards, transition_reward
from learning.rowpack import pack_line, row_meta, unpack_line
from learning.tasks import (FORMULA_ID, LEGACY_TASK, TASK_ID, bind_result, is_truncated,
                            job_reward, require_rows_task, reward_config, value_target)
from tests.v5 import helpers


def finite_rows(*, turns=3, source='policy', fmt='duel', lam=1.):
    rows = helpers.sequence_rows(turns=turns, decisions_per_turn=1, source=source,
                                format_name=fmt, game_id='b', game_family='b')
    config = reward_config(economy=.1, control=.1, gae_lambda=lam)
    for index, row in enumerate(rows):
        row.update(task_id=TASK_ID, reward_config=config, reward_formula_id=FORMULA_ID,
                   reward_raw=dict(economy=.2+index*.1, control=.4, explored=.1+index*.1),
                   reward_after=dict(economy=.7, control=.8, explored=.9), value=.2,
                   log_probability=0.)
    return rows


def written(directory, rows, *, cap=30, result=None, bootstraps=None):
    result = result or dict(bots=['a', 'b'], winner=0, faults=[], survivors=[1, 2],
                            reason='turn_limit', turns=cap)
    result = bind_result(copy.deepcopy(result), dict(task_id=TASK_ID, max_turns=cap))
    path = directory/'game.jsonl.gz'
    report = write_shard(path, 'b', rows, result, bootstraps)
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        return [unpack_line(line)[0] for line in stream], report, path


class FiniteScoreArithmeticTests(unittest.TestCase):
    def test_own_official_points_have_one_positive_affine_normalization(self):
        for winner in (0, 1, 2):
            result = dict(bots=['a', 'b'], winner=winner)
            rewards = terminal_rewards(result, TASK_ID)
            for side in (1, 2):
                self.assertAlmostEqual(rewards[side], 2*official_score(result, side)/3-1)
        self.assertAlmostEqual(terminal_rewards(dict(bots=['a', 'b'], winner=0), TASK_ID)[1], -1/3)
        # A half-win/half-loss lottery has higher own points than a certain draw.
        self.assertGreater((1.+(-1.))/2, -1/3)

    def test_team_outcome_includes_the_previously_eliminated_teammate(self):
        for winner, expected in ((0, -1/3), (1, 1.), (2, -1.)):
            result = dict(bots=['a']*4, teams=[1, 2, 1, 2], winning_team=winner,
                          survivors=[2, 3, 4])
            rewards = terminal_rewards(result, TASK_ID)
            self.assertEqual(rewards[1], rewards[3])
            self.assertAlmostEqual(rewards[1], expected)

    def test_ffa_uses_fixed_own_rank_scale_not_per_game_centering(self):
        for ranks in ({'1': 0., '2': 1., '3': 2., '4': 3.},
                      {'1': 0., '2': 2., '3': 2., '4': 2.}):
            result = dict(bots=['a']*4, rank_points=ranks)
            rewards = terminal_rewards(result, TASK_ID)
            for side in range(1, 5):
                self.assertAlmostEqual(rewards[side], 2*official_score(result, side)-1)
        self.assertAlmostEqual(rewards[2], 1/3)
        self.assertEqual(rewards[1], -1.)

    def test_new_config_rejects_discount_and_exploration_changes(self):
        config = reward_config()
        self.assertEqual((config['gamma'], config['explore']), (1., 0.))
        for change in (dict(gamma=.99), dict(explore=.01), dict(reward_formula_id='v5-potential-1')):
            with self.subTest(change=change), self.assertRaises(ValueError):
                RewardConfig(**(config | change))
        from learning.control import _changed
        with self.assertRaisesRegex(ValueError, 'explore=0'):
            _changed(RewardConfig(**config), dict(explore=.01))
        with self.assertRaisesRegex(ValueError, 'gamma=1'):
            transition_reward(dict(economy=0., control=0., explored=0.),
                              dict(economy=0., control=0., explored=0.), config, gamma=.9)

    def test_legacy_configuration_is_never_implicitly_relabelled(self):
        old = RewardConfig().to_dict()
        old.pop('task_id')
        self.assertEqual(RewardConfig(**old).task_id, LEGACY_TASK)
        self.assertEqual(RewardConfig(**old).explore, .1)
        self.assertEqual(terminal_rewards(dict(bots=['a', 'b'], winner=0))[1], 0.)
        with self.assertRaisesRegex(ValueError, 'job task'):
            job_reward(dict(task_id=TASK_ID, reward_config=old))

    def test_completed_draw_telescopes_and_bc_matches_mc_and_ppo(self):
        with helpers.temporary_directory() as directory:
            rows, report, _ = written(directory, finite_rows(), bootstraps={
                '1': dict(value=-200., turn=31, reward_raw=dict(economy=.9, control=.9, explored=1.))})
        self.assertEqual(report['written'], 3)
        self.assertTrue(all(r['value_valid'] and not r['truncated'] for r in rows))
        self.assertTrue(all(r['bootstrap_value'] is None and r['bootstrap_raw'] is None for r in rows))
        self.assertAlmostEqual(sum(r['reward_step'] for r in rows), -1/3-.06)
        targets = advantages(rows)[1]
        for index, row in enumerate(rows):
            mc = sum(r['reward_step'] for r in rows[index:])
            self.assertAlmostEqual(mc, -1/3 - .1*row['reward_raw']['economy']-.04)
            self.assertAlmostEqual(targets[index], mc)
            self.assertAlmostEqual(value_target(row), mc)

    def test_natural_wins_and_losses_clear_endpoint_potential(self):
        for winner, expected in ((1, 1.), (2, -1.)):
            result = dict(bots=['a', 'b'], winner=winner, faults=[], reason='victory', turns=3)
            with self.subTest(winner=winner), helpers.temporary_directory() as directory:
                rows, _, _ = written(directory, finite_rows(), result=result)
                self.assertAlmostEqual(sum(r['reward_step'] for r in rows), expected-.06)
                self.assertTrue(all(r['value_valid'] for r in rows))

    def test_same_turn_actions_and_multiturn_gap_keep_own_turn_lambda_clock(self):
        raw = dict(economy=0., control=0., explored=0.)
        rows = [dict(schema=6, task_id=TASK_ID, game_id='b', side=1, turn=turn, decision=i,
                     value=value, terminal_reward=-1/3, reward_raw=raw, reward_after=raw,
                     reward_config=reward_config(gae_lambda=.5))
                for i, (turn, value) in enumerate(((1, .2), (1, .3), (3, .4)))]
        adv, target = advantages(rows)
        for actual, expected in zip(adv, [1/60, -1/12, -11/15]):
            self.assertAlmostEqual(actual, expected)
        self.assertAlmostEqual(target[0], target[1])
        self.assertAlmostEqual(target[-1], -1/3)

    def test_early_external_cut_retains_potential_and_bootstrap(self):
        bootstrap = dict(value=.8, turn=5, reward_raw=dict(economy=.5, control=.6, explored=.9))
        with helpers.temporary_directory() as directory:
            rows, _, _ = written(directory, finite_rows(), cap=4, bootstraps={'1': bootstrap})
        self.assertTrue(all(r['truncated'] and not r['value_valid'] for r in rows))
        self.assertAlmostEqual(rows[-1]['reward_step'], .03)
        self.assertAlmostEqual(advantages(rows)[1][-1], .83)
        self.assertAlmostEqual(advantages(rows)[1][0], .85)
        changed = [dict(r, terminal_reward=99.) for r in rows]
        self.assertEqual(advantages(rows), advantages(changed))

    def test_cap_29_lite_round_30_is_still_external(self):
        result = bind_result(dict(reason='turn_limit', turns=30, survivors=[1, 2]),
                             dict(task_id=TASK_ID, game_spec=dict(max_turns=29)))
        self.assertFalse(result['task_terminal'])
        self.assertTrue(is_truncated(result, 1))
        with self.assertRaisesRegex(ValueError, 'precedes'):
            bind_result(dict(reason='turn_limit', turns=29), dict(task_id=TASK_ID, max_turns=30))

    def test_eliminated_side_keeps_team_external_bootstrap_then_scores_final(self):
        raw = finite_rows(turns=1, fmt='team2v2')
        result = dict(bots=['a']*4, teams=[1, 2, 1, 2], winning_team=0,
                      reason='turn_limit', turns=30, survivors=[2, 3, 4], faults=[])
        bootstrap = {'1': dict(value=.5, turn=30, reward_raw=raw[0]['reward_raw'])}
        with helpers.temporary_directory() as directory:
            early, _, _ = written(directory, raw, result=result | dict(turns=10), cap=10, bootstraps=bootstrap)
        self.assertTrue(early[0]['truncated'])
        with helpers.temporary_directory() as directory:
            final, _, _ = written(directory, raw, result=result, bootstraps=bootstrap)
        self.assertFalse(final[0]['truncated'])
        self.assertTrue(final[0]['value_valid'])
        self.assertAlmostEqual(final[0]['terminal_reward'], -1/3)

    def test_raw_rowpack_and_training_reader_preserve_task_and_reject_old_data(self):
        with helpers.temporary_directory() as directory:
            rows, _, path = written(directory, finite_rows())
            self.assertEqual(len(read_shards([path], expected_task=TASK_ID)), 3)
            raw = row_meta(pack_line(rows[0]))
            self.assertEqual(raw['task_id'], TASK_ID)
            self.assertEqual(raw['reward_config']['task_id'], TASK_ID)
            self.assertEqual(raw['reward_formula_id'], FORMULA_ID)
            self.assertAlmostEqual(raw['terminal_reward'], -1/3)
        old = helpers.sequence_rows(turns=1, game_id='b', game_family='b')
        with helpers.temporary_directory() as directory:
            path = directory/'old.jsonl.gz'
            write_shard(path, 'b', old, dict(bots=['a', 'b'], winner=1, faults=[]))
            self.assertTrue(read_shards([path]))  # Historical diagnostics remain readable.
            with self.assertRaisesRegex(ValueError, 'training data task'):
                read_shards([path], expected_task=TASK_ID)
        with self.assertRaisesRegex(ValueError, 'sample task'):
            validate_record(dict(rows[0], task_id=LEGACY_TASK))
        from learning.updates import prepare
        with self.assertRaisesRegex(ValueError, 'mixes tasks'):
            prepare(helpers.model(), rows+old)

    def test_bc_optimizer_supervises_the_same_shaped_value_target(self):
        from learning.train import train
        with helpers.temporary_directory() as directory:
            rows, _, _ = written(directory, finite_rows(turns=1, source='astra'))
        model = helpers.model()
        model.requires_grad_(False)
        output = model.value[-1]
        output.weight.zero_()
        output.bias.fill_(.75)
        output.bias.requires_grad_(True)
        optimizer = torch.optim.SGD([output.bias], lr=1.)
        self.assertEqual(train(model, optimizer, rows, 'bc', epochs=1)['updates'], 1)
        self.assertAlmostEqual(output.bias.item(), -1/3-.06, places=6)


class FiniteScoreEngineTests(unittest.TestCase):
    def setUp(self):
        context = helpers.temporary_directory()
        self.directory = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        rules = helpers.rules()
        rules['units']['Fighter']['weapons'][0].update(damage=100, accuracy=100)
        self.rules = helpers.write_rules_dir(self.directory/'rules', rules, complete=True,
                                             native_accepted=True, performance_accepted=True)
        path = self.rules/'catalog.json'
        catalog = json.loads(path.read_text()) | dict(rules_version='synthetic-v5')
        path.write_text(json.dumps(catalog))

    def run_fixture(self, cap=30, *, sides=2, attack_side=None, dagger=False):
        from learning.lite_host import play_lite_job
        spec = helpers.spec(sides=sides, max_turns=cap)
        spec['units'] = [u for u in spec['units'] if u['leader']]
        observed, bootstrap_calls = [], []
        def policy(row):
            self.assertFalse({'reward_raw', 'reward_after', 'teacher_action'} & row.keys())
            observed.append((row['side'], row['turn']))
            kind = 'attack' if row['side'] == attack_side and row['turn'] == 1 else 'end_turn'
            choice = next((i for i,c in enumerate(row['candidates']) if c['kind'] == kind), 0)
            return dict(choice=choice, log_probability=0., value=.2)
        def bootstrap(row):
            bootstrap_calls.append(row['side'])
            return .8
        job = dict(id='fixture', task_id=TASK_ID, reward_config=reward_config(gae_lambda=1.),
                   game_spec=spec, max_turns=cap, rules_dir=str(self.rules),
                   bots=['policy']*sides, policy=policy, bootstrap_policy=bootstrap,
                   learning=dict(sides={str(s): {} for s in range(1, sides+1)}),
                   deadline=time.time()+120, game_family='b',
                   meta=dict(format='team2v2' if sides==4 else 'duel'),
                   shard=str(self.directory/'fixture.jsonl.gz'))
        if dagger: job['learning']['dagger_teacher']=True
        with mock.patch.object(features, 'RULES_PATH', self.rules/'catalog.json'):
            result = play_lite_job(job)
        self.assertEqual(result['status'], 'complete', result)
        with gzip.open(job['shard'], 'rt') as stream:
            rows = [unpack_line(line)[0] for line in stream]
        return result, rows, observed, bootstrap_calls, job

    def test_complete_round_30_scores_both_sides_without_bootstrap(self):
        result, rows, observed, bootstraps, _ = self.run_fixture()
        self.assertEqual(observed, [(side, turn) for turn in range(1,31) for side in (1,2)])
        self.assertEqual(result['result']['turns'], 31)
        self.assertTrue(result['result']['task_terminal'])
        self.assertEqual(bootstraps, [])
        self.assertTrue(all(r['value_valid'] and not r['truncated'] for r in rows))
        self.assertTrue(all(abs(r['terminal_reward']+1/3)<1e-12 for r in rows))

    def test_real_external_cut_still_queries_and_records_bootstrap(self):
        result, rows, observed, bootstraps, _ = self.run_fixture(cap=29)
        self.assertFalse(result['result']['task_terminal'])
        self.assertEqual(max(turn for _,turn in observed), 29)
        self.assertEqual(sorted(bootstraps), [1,2])
        self.assertTrue(all(r['truncated'] and r['bootstrap_value']==.8 for r in rows))
        self.assertTrue(all(not r['value_valid'] for r in rows))

    def test_real_natural_terminal_scores_without_tail_bootstrap(self):
        result, rows, _, bootstraps, _ = self.run_fixture(attack_side=1)
        self.assertEqual(result['result']['reason'], 'victory')
        self.assertEqual(result['result']['winner'], 1)
        self.assertEqual(bootstraps, [])
        self.assertEqual(rows[-1]['terminal_reward'], 1.)
        self.assertTrue(rows[-1]['value_valid'])

    def test_early_eliminated_teammate_receives_final_draw(self):
        result, rows, observed, bootstraps, _ = self.run_fixture(sides=4, attack_side=2)
        self.assertNotIn(1, result['result']['survivors'])
        self.assertIn(3, result['result']['survivors'])
        self.assertEqual([turn for side,turn in observed if side==1], [1])
        learner = next(r for r in rows if r['side']==1)
        self.assertTrue(learner['value_valid'])
        self.assertFalse(learner['truncated'])
        self.assertAlmostEqual(learner['terminal_reward'], -1/3)
        self.assertEqual(bootstraps, [])

    def test_dagger_queries_share_finite_outcome_and_value_valid(self):
        _, _, _, _, job = self.run_fixture(dagger=True)
        path = Path(job['shard']).with_name('fixture.dagger.jsonl.gz')
        with gzip.open(path, 'rt') as stream:
            rows = [unpack_line(line)[0] for line in stream]
        queried = [r for r in rows if r.get('query_only') and r['choice']>=0]
        self.assertTrue(queried)
        self.assertTrue(all(r['value_valid'] and r['task_id']==TASK_ID for r in queried))
        self.assertTrue(all(abs(r['terminal_reward']+1/3)<1e-12 for r in queried))

    def test_native_runtime_suppresses_only_finite_scored_cap_bootstrap(self):
        source = (helpers.ROOT/'vendor/arena/runtime/runtime.lua').read_text(encoding='utf-8')
        for task, cap, expected in ((TASK_ID,30,0), (TASK_ID,29,1), (LEGACY_TASK,30,1)):
            with self.subTest(task=task, cap=cap):
                lua = LuaRuntime(unpack_returned_tuples=True)
                lua.execute("""
                    calls=0;std_print=function() end;wml={variables={}}
                    wesnoth={current={turn=31},sides={{gold=1},{gold=1}},
                      units={find_on_map=function() return {{hitpoints=1}} end},
                      game_events={add=function() end},wml_actions={endlevel=function() end}}
                """)
                lua.globals().runtime = lua.execute(source)
                lua.globals().task_id, lua.globals().cap = task, cap
                lua.execute("""
                    runtime.setup{token='fixture',max_turns=cap,learning={['1']={task_id=task_id}}}
                    runtime.snapshot=function() return {} end
                    runtime.states[1]={data={},module={bootstrap=function() calls=calls+1;return {} end}}
                    runtime.finish('turn_limit')
                """)
                self.assertEqual(lua.globals().calls, expected)

    def test_native_event_ingestion_keeps_scored_and_external_boundary_identity(self):
        from learning.sample import play_job
        for cap in (29, 30):
            with self.subTest(cap=cap):
                row = helpers.sequence_rows(turns=1, source='policy', game_id='b', game_family='b')[0]
                native_keys = ('global', 'opponents', 'spatial', 'candidates', 'choice', 'actual',
                               'turn', 'side', 'timing', 'source', 'value', 'version', 'schema',
                               'reward_raw', 'reward_after')
                row = {key: value for key,value in row.items() if key in native_keys}
                row.setdefault('value', .2)
                row.setdefault('reward_after', row['reward_raw'])
                output = self.directory/f'native-{cap}.json'
                events = [dict(event='LEARN', data=row), dict(event='BOOTSTRAP', data=dict(
                    side=1, value=-99., turn=cap+1, reward_raw=row['reward_raw']))]
                with gzip.open(output.with_suffix('.events.jsonl.gz'), 'wt') as stream:
                    stream.write(''.join(json.dumps(e)+'\n' for e in events))
                job = dict(id=f'native-{cap}', output=str(output), engine='native', task_id=TASK_ID,
                           max_turns=cap, reward_config=reward_config(), seed=1, factions=['a','b'],
                           bots=['policy','policy'], wesnoth='unused', deadline=time.time()+30,
                           learning=dict(support='unused', sides={'1': dict(teacher=False)}),
                           shard=str(self.directory/f'native-{cap}.jsonl.gz'))
                result = dict(bots=job['bots'], winner=0, reason='turn_limit', turns=cap,
                              survivors=[1,2], faults=[], factions=job['factions'])
                with mock.patch('learning.sample._priority_set', True), \
                     mock.patch('learning.sample.match.play_game', return_value=result) as native:
                    outcome = play_job(job)
                self.assertEqual(outcome['status'], 'complete')
                self.assertEqual(native.call_args.kwargs['learning']['sides']['1']['task_id'], TASK_ID)
                self.assertEqual(outcome['result']['task_terminal'], cap==30)
                with gzip.open(job['shard'], 'rt') as stream:
                    row = unpack_line(next(stream))[0]
                self.assertEqual(row['task_id'], TASK_ID)
                self.assertEqual(row['truncated'], cap<30)
                self.assertEqual(row['value_valid'], cap==30)
                self.assertEqual(row['bootstrap_value'], None if cap==30 else -99.)
                self.assertAlmostEqual(row['terminal_reward'], -1/3)


if __name__ == '__main__':
    unittest.main()
