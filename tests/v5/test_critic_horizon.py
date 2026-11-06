"""Hand-computable horizon contracts and diagnostic targets; no learning run."""
import copy
import gzip
import unittest

from learning.data import advantages, write_shard
from learning.rewards import RewardConfig, row_transition
from learning.rowpack import unpack_line
from verification.team_critic_horizon_20261106.probe import Metrics, completed_return_bounds, critic_return_bounds, returns


def row(turn, value, *, gamma=1., lam=.5, outcome=1.):
    raw = dict(economy=0., control=0., explored=0.)
    return dict(schema=6, game_id='hand', side=1, turn=turn, decision=turn,
                value=value, terminal_reward=outcome, truncated=False,
                reward_raw=raw, reward_after=raw,
                reward_config=RewardConfig(economy=.1, control=.1, explore=.1,
                                           gamma=gamma, gae_lambda=lam).to_dict())


class CriticHorizonTests(unittest.TestCase):
    def assertValues(self, values, expected):
        self.assertEqual(len(values), len(expected))
        for value, wanted in zip(values, expected):
            self.assertAlmostEqual(value, wanted, places=12)

    def test_same_turn_does_not_attenuate_gae_but_two_turn_gap_does(self):
        rows = [row(1, .2), row(1, .3), row(3, .4)]
        rows[1]['decision'] = 2
        adv, target = advantages(rows)
        self.assertValues(adv, [.35, .25, .6])
        self.assertValues(target, [.55, .55, 1.])
        self.assertValues(returns(rows), [1., 1., 1.])

    def test_gamma_and_lambda_both_follow_elapsed_own_turns(self):
        rows = [row(1, .2, gamma=.9), row(1, .3, gamma=.9), row(3, .4, gamma=.9)]
        rows[1]['decision'] = 2
        adv, target = advantages(rows)
        # delta at the middle row is .9**2*.4-.3=.024;
        # its trace coefficient is (.9*.5)**2=.2025.
        self.assertValues(adv, [.2455, .1455, .6])
        self.assertValues(target, [.4455, .4455, 1.])
        self.assertValues(returns(rows), [.81, .81, 1.])

    def test_truncated_tail_uses_boundary_gap_and_ignores_outcome_label(self):
        tail = row(3, .4, gamma=.9)
        tail.update(truncated=True, bootstrap_turn=5, bootstrap_value=.8,
                    reward_raw=dict(economy=.2, control=.4, explored=.3),
                    bootstrap_raw=dict(economy=.5, control=.6, explored=.4))
        for outcome in (-1., 0., 1.):
            with self.subTest(outcome=outcome):
                tail['terminal_reward'] = outcome
                self.assertValues(row_transition(tail), [.0391, 2])
                self.assertValues(advantages([tail])[0], [.2871])
                self.assertValues(advantages([tail])[1], [.6871])
                self.assertValues(returns([tail]), [.6871])

    def test_finite_cap_counterfactual_is_a_different_boundary_condition(self):
        tail = row(60, -2., outcome=0.)
        tail.update(truncated=True, bootstrap_turn=61, bootstrap_value=-2.1,
                    reward_raw=dict(economy=.2, control=.4, explored=.3),
                    bootstrap_raw=dict(economy=.5, control=.6, explored=.4),
                    reward_after=dict(economy=.3, control=.5, explored=.35))
        self.assertValues(returns([tail]), [-2.04])
        self.assertValues(returns([tail], cap_terminal=True), [-.05])
        self.assertTrue(tail['truncated'])  # Diagnostic does not rewrite inputs.
        self.assertEqual(tail['bootstrap_value'], -2.1)

    def test_natural_terminal_zeros_potentials_and_never_bootstraps(self):
        tail = row(60, .4)
        tail.update(bootstrap_turn=61, bootstrap_value=-200.,
                    reward_raw=dict(economy=.2, control=.4, explored=.3),
                    reward_after=dict(economy=.5, control=.6, explored=.4))
        self.assertValues(advantages([tail])[1], [.95])
        self.assertValues(returns([tail]), [.95])

    def test_missing_truncation_value_fails_instead_of_becoming_zero(self):
        tail = row(60, .4)
        tail.update(truncated=True, bootstrap_turn=61, bootstrap_value=None,
                    bootstrap_raw=tail['reward_raw'])
        with self.assertRaisesRegex(ValueError, 'requires a bootstrap value'):
            advantages([tail])

    def test_dead_learner_with_living_teammate_still_has_truncated_team_outcome(self):
        from tests.v5 import helpers

        rows = helpers.sequence_rows(turns=1, decisions_per_turn=1, format_name='team2v2', source='policy')
        rows = [copy.deepcopy(rows[0])]
        self.assertEqual(rows[0]['side'], 1)
        bootstrap = dict(value=.3, turn=11, reward_raw=rows[0]['reward_raw'], potential=0.)
        with helpers.temporary_directory() as directory:
            path = directory / 'team.jsonl.gz'
            write_shard(path, 'team', rows, dict(bots=['a', 'b', 'a', 'b'], teams=[1, 2, 1, 2],
                        winning_team=0, reason='turn_limit', survivors=[2, 3, 4], faults=[]),
                        bootstraps={'1': bootstrap})
            with gzip.open(path, 'rt', encoding='utf-8') as stream:
                recorded = unpack_line(next(stream))[0]
        self.assertTrue(recorded['truncated'])
        self.assertFalse(recorded['value_valid'])
        self.assertEqual(row_transition(recorded)[1], 10)
        self.assertEqual(recorded['terminal_reward'], 0.)

    def test_metric_bias_and_explained_variance_have_distinct_meanings(self):
        metric = Metrics()
        metric.add(0., 0.)
        metric.add(0., 1.)
        result = metric.result()
        self.assertEqual(result['bias'], -.5)
        self.assertEqual(result['mse'], .5)
        self.assertEqual(result['explained_variance'], 0.)
        constant = Metrics()
        constant.add(0., 1.)
        constant.add(2., 1.)
        self.assertIsNone(constant.result()['explained_variance'])
        self.assertEqual(constant.result()['mse'], 1.)

    def test_partial_observation_critic_bound_does_not_use_hidden_state_potential(self):
        config = RewardConfig().to_dict()
        self.assertValues(critic_return_bounds(config), [-1.25, 1.25])
        realized = completed_return_bounds(dict(economy=-1., control=0., explored=0.), config)
        self.assertValues(realized, [-.85, 1.25])
        # A view shared with other hidden economy states can correctly have
        # value -1 even though this particular state's lower return is -.85.
        self.assertLess(-1., realized[0])
        self.assertGreaterEqual(-1., critic_return_bounds(config)[0])


if __name__ == '__main__':
    unittest.main()
