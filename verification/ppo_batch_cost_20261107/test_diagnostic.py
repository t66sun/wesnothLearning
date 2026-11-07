"""Cross-run frozen splices must keep PPO decision keys independent."""
import unittest

from learning.ppo import _target_key
from timing import namespace_added_games


class BatchCostTest(unittest.TestCase):
    def test_cross_run_job_ids_keep_distinct_ppo_targets(self):
        target = dict(game_id='rollout-00038-duel-g0', side=1, turn=1, decision=0)
        rows = [dict(target, game_family='first'), dict(target, game_family='second')]
        namespace_added_games(rows, {'second': 'a2'})
        self.assertEqual([_target_key(row) for row in rows], [
            ('rollout-00038-duel-g0', 1, 1, 0),
            ('a2/rollout-00038-duel-g0', 1, 1, 0),
        ])


if __name__ == '__main__':
    unittest.main()
