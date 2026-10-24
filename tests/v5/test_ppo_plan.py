"""P3/P4: deterministic window plans and logical-batch PPO updates."""
import random
import time
import unittest
from unittest import mock

import torch

from learning import ppo
from learning.model import batch
from learning.sequences import attach_histories
from learning.data import split as helpers_split
from learning.train import checkpoint, restore_rng
from tests.v5 import helpers


def _bc():
    rows = helpers.sequence_rows(turns=1, source='astra', game_id='bc-1', game_family='bc-1')
    for row in rows:
        row['split'] = helpers_split(row['game_family'])
    return rows


def _records(specs):
    records = []
    for game_id, turns, delta in specs:
        part = helpers.sequence_rows(turns=turns, decisions_per_turn=1, source='policy',
                                     game_id=game_id, game_family=game_id)
        for row in part:
            row['split'] = helpers_split(row['game_family'])
            row['version'] = 7
            row['value'] = .2
            row['reward'] = 0.
            row['reward_after'] = dict(row['reward_raw'])
            row['truncated'] = False
        part[-1]['reward'] = 1.
        part[-1]['reward_after'] = dict(part[-1]['reward_raw'])
        records.extend(part)
    records = attach_histories(records)
    model = helpers.model(seed=41)
    with torch.no_grad():
        logits, _ = model(*batch(records))
        chosen = torch.tensor([row['choice'] for row in records])
        logp = torch.distributions.Categorical(logits=logits).log_prob(chosen)
    for row, value, (_, _, delta) in zip(records, logp.tolist(),
                                         [spec for spec in specs for _ in range(spec[1])]):
        row['log_probability'] = value - delta
    return records


def _run(records, *, epochs=1, deadline=float('inf'), progress=None, seed=13):
    model = helpers.model(seed=41)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    random.seed(seed)
    torch.manual_seed(0)
    return model, optimizer, ppo.update(model, optimizer, records, bc_records=_bc(), epochs=epochs,
                                        minibatch=2, deadline=deadline, progress=progress, plan_seed=5)


class PpoPlanTests(unittest.TestCase):
    def test_each_window_visited_once_per_epoch(self):
        records = _records([('b', 2, 0.), ('c', 3, 0.), ('d', 4, 0.)])
        model, _, result = _run(records, epochs=2)
        self.assertEqual(result['planned_windows'], 3)
        self.assertEqual(result['planned_targets'], 9)
        self.assertEqual(result['repeated_targets'], 0)
        self.assertEqual(result['updates'], 2)
        self.assertEqual(result['decisions_seen'], 18)
        self.assertEqual(result['inspected_decisions'], 18)
        self.assertEqual(result['committed_decisions'], 18)
        self.assertEqual(result['exit'], 'completed')
        order = ppo._epoch_order(5, 0, 5)
        self.assertEqual(sorted(order), list(range(5)))
        self.assertNotEqual(order, ppo._epoch_order(5, 1, 5))

    def test_batch_kl_stop_rejects_before_stepping(self):
        records = _records([('b', 4, .5)])
        model, optimizer, result = _run(records)
        self.assertTrue(result['kl_stopped'])
        self.assertFalse(result['interrupted'])
        self.assertEqual(result['exit'], 'kl_stop')
        self.assertEqual(result['updates'], 0)
        self.assertEqual(result['committed_decisions'], 0)
        self.assertEqual(result['inspected_decisions'], 4)
        self.assertEqual(result['policy_sha256_before'], result['policy_sha256_after'])
        self.assertTrue(all(parameter.grad is None or torch.count_nonzero(parameter.grad) == 0
                            for parameter in model.parameters()))

    def test_batch_kl_is_window_equal_not_chunk_early_stop(self):
        records = _records([('b', 1, .26), ('c', 3, 0.)])
        _, _, result = _run(records)
        self.assertFalse(result['kl_stopped'])
        self.assertEqual(result['exit'], 'completed')
        self.assertEqual(result['updates'], 1)
        self.assertLess(result['approx_kl'], .02)
        self.assertAlmostEqual(result['approx_kl'], (pow(2.718281828459045, .26) - 1 - .26) / 2, places=4)

    def test_deadline_before_batch_changes_nothing(self):
        records = _records([('b', 3, 0.), ('c', 2, 0.)])
        model, optimizer, result = _run(records, deadline=0.)
        self.assertTrue(result['interrupted'])
        self.assertEqual(result['exit'], 'deadline')
        self.assertEqual(result['updates'], 0)
        self.assertEqual(result['committed_decisions'], 0)
        self.assertEqual(result['inspected_decisions'], 0)
        self.assertEqual(result['policy_sha256_before'], result['policy_sha256_after'])
        self.assertEqual(result['cursor']['epoch'], 0)
        self.assertEqual(result['cursor']['step'], 0)
        self.assertEqual(result['cursor']['plan_version'], 2)

    def test_mid_batch_deadline_discards_gradients_and_restores_rng(self):
        records = _records([('b', 3, 0.), ('c', 2, 0.)])
        before = None
        calls = []

        def clock():
            calls.append(None)
            return 0. if len(calls) < 3 else 10.

        model = helpers.model(seed=41)
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
        random.seed(13)
        torch.manual_seed(0)
        before = random.getstate()
        with mock.patch('learning.ppo.time.time', side_effect=clock):
            result = ppo.update(model, optimizer, records, bc_records=_bc(), epochs=1,
                                minibatch=32, deadline=1., plan_seed=5)
        self.assertEqual(result['exit'], 'deadline')
        self.assertEqual(result['updates'], 0)
        self.assertEqual(result['committed_decisions'], 0)
        self.assertEqual(result['inspected_decisions'], 3)
        self.assertEqual(result['policy_sha256_before'], result['policy_sha256_after'])
        self.assertTrue(all(parameter.grad is None or torch.count_nonzero(parameter.grad) == 0
                            for parameter in model.parameters()))
        self.assertEqual(random.getstate(), before)

    def test_resume_from_saved_boundary_matches_uninterrupted(self):
        records = _records([('b', 2, 0.), ('c', 3, 0.), ('d', 4, 0.), ('e', 2, 0.)])
        model_a, _, result_a = _run(records, epochs=2)
        model_b, optimizer_b, first = _run(records, epochs=1)
        with helpers.temporary_directory() as directory:
            path = directory / 'state.pt'
            checkpoint(path, model_b, optimizer_b, runner={})
            state = torch.load(path, weights_only=False)
        resumed = helpers.model(seed=41)
        resumed.load_state_dict(state['model'])
        optimizer = torch.optim.Adam(resumed.parameters(), lr=1e-3)
        optimizer.load_state_dict(state['optimizer'])
        restore_rng(state)
        progress = dict(first['cursor'], loss_sum=first['loss'] * first['updates'],
                        updates=first['updates'], decisions_seen=first['decisions_seen'])
        second = ppo.update(resumed, optimizer, records, bc_records=_bc(), epochs=2, minibatch=2,
                            progress=progress, plan_seed=5)
        self.assertEqual(second['exit'], 'completed')
        self.assertEqual(second['updates'], result_a['updates'])
        self.assertEqual(second['decisions_seen'], result_a['decisions_seen'])
        self.assertEqual(ppo._digest(resumed), result_a['policy_sha256_after'])
        self.assertAlmostEqual(second['loss'], result_a['loss'], places=5)

    def test_changed_plan_is_rejected(self):
        records = _records([('b', 2, 0.), ('c', 3, 0.), ('d', 4, 0.), ('e', 2, 0.), ('g', 3, 0.)])
        progress = {'epoch': 0, 'step': 1, 'plan_version': 2, 'plan_hash': 'not-the-plan'}
        with self.assertRaisesRegex(ValueError, 'window plan changed'):
            _run(records, epochs=2, progress=progress)

    def test_legacy_cursor_is_migrated_at_a_boundary(self):
        records = _records([('b', 2, 0.), ('c', 3, 0.), ('d', 4, 0.), ('e', 2, 0.), ('g', 3, 0.)])
        progress = {'epoch': 0, 'step': 1, 'updates': 1, 'decisions_seen': 4}
        _, _, result = _run(records, epochs=2, progress=progress)
        self.assertTrue(result['plan_migrated'])
        self.assertEqual(result['exit'], 'completed')
        self.assertEqual(result['updates'], 4)
