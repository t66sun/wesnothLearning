"""Score synthetic replies on the exact frozen #349 schedule."""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from learning.common import read_json
from learning.tasks import TASK_ID

from panel import PPO, NUM_JOBS, recount, verify_schedule, verdict


def fixture(jobs):
    winners = {name: outcome for name, outcome in zip(PPO, ('win', 'draw', 'loss'))}
    replies = []
    for job in jobs:
        meta = job['meta']
        seat, = meta['policy_sides']
        outcome = winners.get(meta['role'], 'draw')
        winner = seat if outcome == 'win' else 3-seat if outcome == 'loss' else 0
        result = dict(bots=job['bots'], factions=job['factions'], faults=[], winner=winner,
                      teams=None, task_id=TASK_ID, task_terminal=True,
                      reason='victory' if winner else 'turn_limit', turns=19 if winner else 31)
        replies.append(dict(id=job['id'], status='complete', meta=meta, engine='lite', result=result))
    return replies


class PanelTests(unittest.TestCase):
    def test_full_integer_recount(self):
        scored = recount(JOBS, fixture(JOBS))
        self.assertEqual(scored['games'], NUM_JOBS)
        self.assertEqual(scored['paired_slots'], 180)
        self.assertEqual(scored['raw_max'], 1620)
        self.assertEqual(scored['raw_difference'], 180)
        self.assertEqual(scored['point'], 1/9)
        self.assertEqual(scored['per_role']['bc'], 1/3)
        self.assertEqual(list(scored['per_seed'].values()), [2/3, 0, -1/3])
        self.assertEqual(scored['verdict'], 'inconclusive')

    def test_strict_useful_gain_threshold(self):
        self.assertEqual(verdict(81, (1, 123), 1620), 'passed')
        self.assertEqual(verdict(81, (0, 123), 1620), 'inconclusive')
        self.assertEqual(verdict(80, (1, 81), 1620), 'inconclusive')
        self.assertEqual(verdict(69, (1, 80), 1620), 'five_point_gain_excluded')

    def test_missing_or_mispaired_reply_is_rejected(self):
        replies = fixture(JOBS)
        with self.assertRaisesRegex(ValueError, 'missing, duplicate or unexpected reply'):
            recount(JOBS, replies[:-1])
        changed = copy.deepcopy(replies[0])
        changed['meta']['policy_sides'] = [3-changed['meta']['policy_sides'][0]]
        with self.assertRaisesRegex(ValueError, 'invalid or mispaired reply'):
            recount(JOBS, [changed, *replies[1:]])

    def test_seed_mismatch_is_rejected_before_scoring(self):
        job = dict(JOBS[0], seed=JOBS[0]['seed']+1)
        with self.assertRaisesRegex(ValueError, 'unpaired schedule entry'):
            verify_schedule([job, *JOBS[1:]])


if __name__ == '__main__':
    JOBS = read_json(Path(sys.argv.pop(1)))
    with patch('learning.sample.collect', side_effect=AssertionError('synthetic tests must not start games')):
        unittest.main(verbosity=2)
