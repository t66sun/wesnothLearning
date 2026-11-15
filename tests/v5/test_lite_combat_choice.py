"""Archived combat-choice schedules must run with their original source."""
import unittest

from learning.lite_host import play_lite_job


class RetiredCombatChoiceTests(unittest.TestCase):
    def test_archived_routes_do_not_run_as_ordinary_greedy_jobs(self):
        for route in ('greedy', 'astra'):
            with self.subTest(route=route):
                result = play_lite_job(dict(id='archived', combat_choice=route, deadline=0))
                self.assertEqual(result, dict(id='archived', status='infrastructure_error', engine='lite',
                                              error='archived combat_choice jobs require their frozen source'))
