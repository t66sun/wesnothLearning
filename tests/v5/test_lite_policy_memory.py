"""Frozen inference reuses history encoding without changing actions or values."""
import copy
import math
from pathlib import Path
import random
import tempfile
import unittest
from unittest import mock

import torch

from learning.features import ACTION, ENTITY, GEOMETRY, GLOBAL, SPATIAL_CHANNELS, schema
from learning.lite_policy import FrozenPolicies
from learning.model import ARCHITECTURE, Policy, batch


def row(turn, value=0.0):
    rng = random.Random(turn)
    entity = dict(id='own', type_index=1, features=[rng.random() for _ in ENTITY])
    return dict(turn=turn, **{'global': [value] * len(GLOBAL)}, opponents=[],
                spatial=dict(board=[[[0.0] * 16 for _ in range(16)] for _ in SPATIAL_CHANNELS],
                             entities=[entity]),
                candidates=[dict(features=[rng.random() for _ in ACTION[:-1]] + [1],
                                 actor=entity, local=[0.0] * (19 * len(SPATIAL_CHANNELS)),
                                 geometry=[0.0] * len(GEOMETRY)) for _ in range(3)])


class FrozenMemoryTests(unittest.TestCase):
    def setUp(self):
        previous = torch.get_num_threads()
        torch.set_num_threads(1)
        self.addCleanup(torch.set_num_threads, previous)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        addon = root / 'Student'
        (addon / 'lua').mkdir(parents=True)
        (addon / 'lua/config.lua').write_text('return {["mode"]="sample"}', encoding='utf-8')
        torch.manual_seed(173)
        model = Policy('duel').eval()
        torch.save(dict(model=model.state_dict(), architecture=ARCHITECTURE,
                        features=schema(), format='duel'), root / 'model.pt')
        self.job = dict(bots=[str(addon), str(addon)], seed=29, format='duel')
        self.policy = FrozenPolicies(self.job)
        self.reference = copy.deepcopy(self.policy.models[1])
        self.rng = random.Random(self.job['seed'] + 100003)

    def expected(self, record, history, bootstrap=False):
        with torch.no_grad():
            logits, value = self.reference(*batch([dict(record, _history=history)]))
        if bootstrap:
            return float(value[0])
        scores = logits[0, :len(record['candidates'])].tolist()
        best = max(range(len(scores)), key=scores.__getitem__)
        probabilities = [math.exp(score-scores[best]) for score in scores]
        total = sum(probabilities)
        probabilities = [p/total for p in probabilities]
        choice = self.rng.choices(range(len(scores)), weights=probabilities, k=1)[0]
        return dict(choice=choice, log_probability=math.log(probabilities[choice]), value=float(value[0]))

    def assert_result(self, actual, expected):
        self.assertEqual(actual['choice'], expected['choice'])
        self.assertAlmostEqual(actual['log_probability'], expected['log_probability'], places=7)
        self.assertAlmostEqual(actual['value'], expected['value'], places=7)

    def test_real_policy_parity_and_one_replay_until_history_or_turn_changes(self):
        first = row(1)
        self.policy.histories[1].append(row(0))
        model = self.policy.models[1]
        with mock.patch.object(model, 'context', wraps=model.context) as context:
            for current in (first, row(1, 0.2)):
                self.assert_result(self.policy.choose(current, 1),
                                   self.expected(current, self.policy.histories[1]))
            rng_state = self.policy.rng[1].getstate()
            history = list(self.policy.histories[1])
            self.assertAlmostEqual(self.policy.choose(first, 1, bootstrap=True),
                                   self.expected(first, history, bootstrap=True), places=7)
            self.assertEqual(self.policy.histories[1], history)
            self.assertEqual(self.policy.rng[1].getstate(), rng_state)
            self.assertEqual(context.call_count, 1)

            self.policy.commit(1, first, dict(committed=True, memory_write=copy.deepcopy(first)))
            self.assert_result(self.policy.choose(first, 1),
                               self.expected(first, self.policy.histories[1]))
            self.assertEqual(context.call_count, 2)
            next_turn = row(2)
            self.assert_result(self.policy.choose(next_turn, 1),
                               self.expected(next_turn, self.policy.histories[1]))
            self.assertEqual(context.call_count, 3)

    def test_memory_cache_is_separate_for_sides_and_new_jobs(self):
        model = self.policy.models[1]
        with mock.patch.object(model, 'context', wraps=model.context) as context:
            self.policy.choose(row(1), 1)
            self.policy.choose(row(1), 2)
            another = FrozenPolicies(self.job)
            another.choose(row(1), 1)
            self.assertEqual(context.call_count, 3)
            self.assertEqual(another.histories[1], [])
