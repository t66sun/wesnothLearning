"""P1: extracted learners keep the historical update behavior and imports."""
import random
import unittest
from unittest import mock

import torch

from learning import bc, ppo
from learning.data import split
from learning.model import batch
from learning.sequences import attach_histories
from learning.train import checkpoint, restore_rng, train, auxiliary_loss, imitation_quality
from tests.v5 import helpers


def _rows(**kw):
    rows = helpers.sequence_rows(turns=2, decisions_per_turn=2, **kw)
    for row in rows:
        row['split'] = split(row['game_family'])
    return rows


def _ppo_rows():
    rows = _rows(source='policy', game_id='ppo-1', game_family='family-1')
    for row in rows:
        row['value'] = .3
        row['reward'] = 0.
        row['reward_after'] = dict(row['reward_raw'])
        row['truncated'] = False
    rows[-1]['reward'] = 1.
    rows[-1]['reward_after'] = dict(rows[-1]['reward_raw'])
    rows = attach_histories(rows)
    model = helpers.model(seed=41)
    with torch.no_grad():
        logits, _ = model(*batch(rows))
        chosen = torch.tensor([r['choice'] for r in rows])
        logp = torch.distributions.Categorical(logits=logits).log_prob(chosen)
    for row, value in zip(rows, logp.tolist()):
        row['log_probability'] = value
    return rows, model


class LearnerExtractionTests(unittest.TestCase):
    def test_bc_update_matches_recorded_baseline(self):
        random.seed(7)
        torch.manual_seed(0)
        rows = _rows()
        model = helpers.model(seed=51)
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
        before = [p.detach().clone() for p in model.parameters()]
        result = train(model, optimizer, rows, method='bc', epochs=1, minibatch=4)
        self.assertEqual(result['updates'], 1)
        self.assertEqual(result['decisions_seen'], 16)
        self.assertAlmostEqual(result['loss'], 4.353553771972656, places=5)
        self.assertTrue(any(not torch.equal(a, b.detach()) for a, b in zip(before, model.parameters())))

    def test_ppo_update_matches_recorded_baseline(self):
        rows, model = _ppo_rows()
        random.seed(13)
        torch.manual_seed(0)
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
        result = train(model, optimizer, rows, method='ppo', epochs=1, minibatch=4, bc_records=_rows())
        self.assertEqual(result['updates'], 1)
        self.assertEqual(result['decisions_seen'], 16)
        self.assertAlmostEqual(result['loss'], 0.9339953809976578, places=5)
        self.assertFalse(result['kl_stopped'])

    def test_train_dispatches_to_extracted_modules(self):
        with mock.patch.object(bc, 'update', return_value='bc') as bc_update, \
                mock.patch.object(ppo, 'update', return_value='ppo') as ppo_update:
            self.assertEqual(train('m', 'o', [], method='bc'), 'bc')
            self.assertEqual(train('m', 'o', [], method='ppo', bc_records=['r']), 'ppo')
            self.assertEqual(bc_update.call_count, 1)
            self.assertEqual(ppo_update.call_count, 1)

    def test_legacy_helpers_remain_importable(self):
        self.assertTrue(all(callable(f) for f in (checkpoint, restore_rng, auxiliary_loss, imitation_quality)))
