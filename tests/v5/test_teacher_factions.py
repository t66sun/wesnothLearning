"""The teacher must learn every faction at every team seat."""
from collections import Counter
from itertools import combinations
import unittest

import params
from learning.data import split
from learning.schedule import teacher_jobs, scenario_factions


def jobs(count, batch=0, stride=None):
    return teacher_jobs('.', ['gpt6astra'], ['baseline'], 'support', batch,
                        20261101, 1000, 'unused', formats=['team2v2'],
                        count=count, index_stride=stride)


class TeacherFactionTests(unittest.TestCase):
    def test_non_team_teacher_designs_remain_unchanged(self):
        for fmt, players in [('duel', 2), ('ffa4', 4)]:
            schedule = teacher_jobs('.', ['gpt6astra'], ['baseline'], 'support', 0,
                20261101, 1000, 'unused', formats=[fmt], count=60)
            self.assertEqual([j['factions'] for j in schedule],
                             [scenario_factions(i, players, fmt) for i in range(60)])

    def test_each_team_seat_teaches_every_faction_in_24_games(self):
        for start in (0, 1, 4):
            with self.subTest(block=start):
                counts = Counter((j['meta']['seat'], j['factions'][j['meta']['seat']-1])
                                 for j in jobs(24, start, 24))
                self.assertEqual(counts, Counter({(s, f): 1
                    for s in range(1, 5) for f in params.FACTIONS}))

    def test_short_team_corpus_has_training_examples_of_every_faction(self):
        training = [j for j in jobs(32) if split(j['scenario_family']) == 'train']
        self.assertEqual({j['factions'][j['meta']['seat']-1] for j in training},
                         set(params.FACTIONS))

    def test_batching_preserves_design_and_all_ally_pairs(self):
        whole = jobs(120)
        batched = [j for batch in range(15) for j in jobs(8, batch, 8)]
        for a, b in zip(whole, batched):
            self.assertEqual((a['factions'], a['scenario_family'], a['meta']['seat']),
                             (b['factions'], b['scenario_family'], b['meta']['seat']))
        pairs = {tuple(sorted((j['factions'][s], j['factions'][s+2])))
                 for j in whole for s in (0, 1)}
        self.assertEqual(pairs, {tuple(sorted(p)) for p in combinations(params.FACTIONS, 2)})
        self.assertTrue(all(len(set(j['factions'])) == 4 for j in whole))


if __name__ == '__main__':
    unittest.main()
