"""PPO must balance public scenario strata, not just seed-bearing games."""
from collections import Counter
from itertools import permutations
from math import perm
import unittest

import params
from learning.common import ROOT
from learning.data import split
from learning.formats import FORMATS, PLAYERS
from learning.maps import SPLITS, decorate
from learning.schedule import base_job, compose_training_scenario, rollout_jobs


def scheduled(fmt, batches, *, first=0, seed=19, policy='student'):
    for batch in range(first, first+batches):
        yield from rollout_jobs(ROOT, policy, ['history'], ['gpt6astra.zip'],
                                'support', 'v1', batch, seed, 1000, 'unused', formats=[fmt])


class PPOScenarioCoverageTests(unittest.TestCase):
    def test_complete_cycles_balance_maps_seats_and_focal_factions(self):
        for fmt in FORMATS:
            n = PLAYERS[fmt]
            native_maps = SPLITS[fmt]['train']
            cycle_games = n * len(params.FACTIONS) * 2 * len(native_maps)
            expected = Counter({(name, side, faction): len(native_maps) if name == f'arena{n}' else 1
                                for name in (f'arena{n}', *native_maps)
                                for side in range(1, n+1) for faction in params.FACTIONS})
            for first in (0, 38, 53):
                with self.subTest(format=fmt, first_batch=first):
                    actual = Counter()
                    for job in scheduled(fmt, cycle_games//4, first=first):
                        side = job['meta']['seat']
                        actual[job['meta']['map'], side, job['factions'][side-1]] += 1
                        self.assertEqual(split(job['scenario_family']), 'train')
                        self.assertEqual(job['bots'][side-1], 'student')
                        self.assertEqual(set(job['learning']['sides']), {str(side)})
                    self.assertEqual(actual, expected)

    def test_all_eligible_ordered_rosters_and_seats_are_reachable(self):
        for fmt in FORMATS:
            with self.subTest(format=fmt):
                n = PLAYERS[fmt]
                expected = set()
                for index in (0, *(2*i+1 for i in range(len(SPLITS[fmt]['train'])))):
                    for roster in permutations(params.FACTIONS, n):
                        job = base_job(ROOT, 'enumerated', ['student']*n, 19, 1000, 'unused',
                                       format_name=fmt, faction_list=roster)
                        decorate(job, fmt, index, 'train')
                        if split(job['scenario_family']) == 'train':
                            expected.update((job['meta']['map'], roster, side) for side in range(1, n+1))
                cycle_games = n * len(params.FACTIONS) * 2 * len(SPLITS[fmt]['train'])
                # A fixed map/seat/faction has at most (F-1)P(N-1) possible rosters.
                rounds = perm(len(params.FACTIONS)-1, n-1)
                actual = set()
                families = set()
                games = set()
                for job in scheduled(fmt, cycle_games*rounds//4, first=53):
                    self.assertEqual(split(job['scenario_family']), 'train')
                    self.assertEqual(len(set(job['factions'])), n)
                    self.assertNotIn(job['meta']['map'], SPLITS[fmt]['validation']+SPLITS[fmt]['holdout'])
                    actual.add((job['meta']['map'], tuple(job['factions']), job['meta']['seat']))
                    families.add(job['scenario_family'])
                    games.add(job['game_family'])
                self.assertEqual(actual, expected)
                self.assertGreater(len(games), len(families))

    def test_scenarios_ignore_seed_policy_paths_and_version(self):
        for fmt in FORMATS:
            first = list(scheduled(fmt, 6, first=53))
            other = list(scheduled(fmt, 6, first=53, seed=71, policy='other-policy'))
            self.assertNotEqual([j['game_family'] for j in first], [j['game_family'] for j in other])
            for a, b in zip(first, other):
                with self.subTest(format=fmt, game=a['id']):
                    b['learning']['sides'][str(b['meta']['seat'])]['version'] = 'other-version'
                    compose_training_scenario(b)
                    self.assertEqual(a['scenario_family'], b['scenario_family'])
                    self.assertEqual(a['factions'], b['factions'])
                    self.assertEqual(a['meta']['map'], b['meta']['map'])


if __name__ == '__main__':
    unittest.main()
