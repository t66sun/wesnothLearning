"""Adaptive reward windows keep advancing after the third complete window."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from learning.control import RewardController


def blocks(start, count, *, control=.9, score=0.):
    return [dict(id=f'block-{i}', complete=True, faults=[], partition='validation',
                 fixed_score=score, native_score=None,
                 strata=[dict(map='map-a', faction='Rebels',
                              coverage5=.8, coverage10=1.,
                              astra_coverage5=1., astra_coverage10=1.,
                              control=control, astra_control=1.,
                              leader_survival=1., astra_leader_survival=1.,
                              loss=.1, astra_loss=.1)])
            for i in range(start, start + count)]


def metrics(rows):
    return dict(partition='validation', new_games=64, validation_blocks=rows)


class RewardWindowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.controller = RewardController(self.directory, 'duel')
        self.controller.boundary(50, metrics(blocks(0, 36)))
        self.assertEqual(len(self.controller.windows), 3)
        self.assertEqual(self.controller.freeze()['reward_version'], 0)

    def test_new_windows_change_decision_after_three_and_survive_resume(self):
        fresh = blocks(36, 29, control=.5)
        for block in fresh:
            block['strata'][0]['coverage10'] = .5
            block['strata'][0]['coverage5'] = .5
        config = self.controller.boundary(100, metrics(fresh))
        self.assertAlmostEqual(config['control'], .11)
        self.assertAlmostEqual(config['explore'], .11)
        self.assertEqual(config['reward_version'], 1)
        self.assertEqual(self.controller.blocks, fresh[24:])
        self.assertEqual(len(self.controller.windows), 3)
        self.assertTrue(all(w['low_control'] for w in self.controller.windows[-2:]))
        events = [json.loads(line) for line in
                  (self.directory / 'control/events.jsonl').read_text().splitlines()]
        self.assertEqual(len(events), 1)
        self.assertEqual((events[0]['source'], events[0]['batch']), ('adaptive', 100))

        resumed = RewardController(self.directory, 'duel')
        self.assertEqual(resumed.freeze(), config)
        self.assertEqual(resumed.windows, self.controller.windows)
        self.assertEqual(resumed.blocks, fresh[24:])
        resumed.boundary(100, metrics(fresh))  # replayed IDs cannot create windows/events
        self.assertEqual(resumed.freeze(), config)
        self.assertEqual(resumed.blocks, fresh[24:])
        self.assertEqual(len((self.directory / 'control/events.jsonl').read_text().splitlines()), 1)

    def test_backlog_retains_newest_three_windows_and_unfinished_tail(self):
        fresh = blocks(36, 55)
        for index, block in enumerate(fresh):
            block['fixed_score'] = index // 12
        expected = [self.controller._window(fresh[start:start + 12])
                    for start in (12, 24, 36)]
        self.controller.boundary(100, metrics(fresh))
        self.assertEqual(self.controller.windows, expected)
        self.assertEqual(self.controller.blocks, fresh[48:])
        self.assertEqual(len(self.controller.seen_blocks), 91)
        self.assertEqual(self.controller.freeze()['reward_version'], 0)

    def test_partial_window_waits_for_twelfth_block(self):
        old = copy.deepcopy(self.controller.windows)
        fresh = blocks(36, 12, score=3.)
        self.controller.boundary(100, metrics(fresh[:11]))
        self.assertEqual(self.controller.windows, old)
        self.assertEqual(self.controller.blocks, fresh[:11])
        self.controller.boundary(150, metrics(fresh[11:]))
        self.assertEqual(self.controller.windows, old[1:] + [self.controller._window(fresh)])
        self.assertEqual(self.controller.blocks, [])
        self.assertEqual(self.controller.freeze()['reward_version'], 0)


if __name__ == '__main__':
    unittest.main()
