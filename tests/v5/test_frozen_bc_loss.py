"""Frozen BC forward KL uses the existing legal support, windows and histories."""
import copy
import random
import unittest
from unittest.mock import patch

import torch

from learning import ppo
from learning.bc_anchor import forward_kl
from learning.data import BCSampler
from learning.model import batch
from tests.v5 import helpers
from tests.v5.test_ppo_plan import _bc, _records
from tests.v5.test_rehearsal_source import human_rows


class FrozenBcLossTests(unittest.TestCase):
    def test_matching_distribution_zero_gradient_and_hard_action_difference(self):
        logits = torch.tensor([[1., -2., -torch.inf], [3., 1., 0.]], requires_grad=True)
        loss = forward_kl(logits, logits, torch.isfinite(logits)).mean()
        loss.backward()
        self.assertEqual(float(loss.detach()), 0.)
        torch.testing.assert_close(logits.grad, torch.zeros_like(logits), atol=1e-7, rtol=0)
        hard = logits.detach().clone().requires_grad_(True)
        torch.nn.functional.cross_entropy(hard, torch.tensor([0, 0])).backward()
        self.assertGreater(float(hard.grad.norm()), .01)

    def test_forward_direction_finite_padding_and_frozen_target(self):
        anchor = torch.tensor([[0., 3., -torch.inf], [1., -1., 0.]], requires_grad=True)
        student = torch.tensor([[1., 0., -torch.inf], [0., 2., 1.]], requires_grad=True)
        loss = forward_kl(anchor, student, torch.isfinite(student)).mean()
        expected = torch.distributions.kl_divergence(torch.distributions.Categorical(logits=anchor),
                                                    torch.distributions.Categorical(logits=student)).mean()
        reverse = forward_kl(student, anchor, torch.isfinite(student)).mean()
        torch.testing.assert_close(loss, expected)
        self.assertNotAlmostEqual(float(loss.detach()), float(reverse.detach()), places=3)
        loss.backward()
        self.assertIsNone(anchor.grad)
        self.assertTrue(bool(torch.isfinite(student.grad).all()))
        torch.testing.assert_close(student.grad, (student.softmax(-1) - anchor.softmax(-1)) / 2)
        self.assertEqual(float(student.grad[0, 2]), 0.)

    def test_policy_only_pool_filters_before_sampling_and_preserves_control_exclusion(self):
        policy = _records([('b', 2, 0.)])
        for row in policy:
            row['policy_sha256'] = 'student'
        renamed = copy.deepcopy(_bc())
        for row in renamed:
            row['source'] = 'policy'  # A source rename cannot launder Astra labels.
        hashed = copy.deepcopy(policy)
        for row in hashed:
            row['policy_sha256'] = 'control'
            row['game_id'] = 'control-policy'
        teacher = _bc()
        for row in teacher:
            row['teacher_source_sha256'] = 'control'
        sampler = BCSampler(teacher + renamed + hashed + human_rows() + policy, allow_policy=True,
                            exclude_teacher_impl='gpt6astra', exclude_teacher_sha='control', policy_only=True)
        self.assertEqual(sampler.rows_excluded, 8)
        self.assertEqual(sampler.source_identities, [dict(source='policy', teacher_impl=None, sha256='student')])
        self.assertEqual({row['game_id'] for row in sampler.sample(20)}, {'b'})
        with self.assertRaisesRegex(ValueError, 'eligible policy/train'):
            BCSampler(teacher + renamed + hashed + human_rows(), allow_policy=True,
                      exclude_teacher_impl='gpt6astra', exclude_teacher_sha='control', policy_only=True)

    def test_full_raw_history_is_replayed_by_each_models_own_weights(self):
        rows = _records([('b', 1, 0.)])
        rehearsal = _records([('c', 12, 0.)])[-1:]
        self.assertEqual(len(rehearsal[0]['_history']), 11)
        model = helpers.model(seed=41)
        anchor = helpers.model(seed=77).requires_grad_(False)
        before = ppo._digest(anchor)
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)
        contexts = {'student': [], 'anchor': []}
        student_context, anchor_context = model.context, anchor.context
        def observed(name, original):
            def context(scene, histories, turns, cache=None):
                contexts[name].append((max(map(len, histories)), cache))
                return original(scene, histories, turns, cache)
            return context
        expected = []
        def measured_kl(target, current, mask):
            with torch.no_grad():
                direct, _ = anchor(*batch(rehearsal))
                torch.testing.assert_close(target, direct)
            expected.append(True)
            return forward_kl(target, current, mask)
        with patch.object(model, 'context', side_effect=observed('student', student_context)), \
             patch.object(anchor, 'context', side_effect=observed('anchor', anchor_context)), \
             patch('learning.ppo.forward_kl', side_effect=measured_kl):
            result = ppo.update(model, optimizer, rows, bc_records=rehearsal, epochs=1,
                                allow_policy_rehearsal=True, ppo_aux_target='frozen_bc_kl', bc_anchor=anchor)
        self.assertEqual(result['committed_steps'], 1)
        self.assertTrue(expected)
        self.assertTrue(any(length == 11 for length, _ in contexts['student']))
        self.assertTrue(any(length == 11 for length, _ in contexts['anchor']))
        student_caches = [cache for _, cache in contexts['student'] if cache is not None]
        anchor_caches = [cache for _, cache in contexts['anchor'] if cache is not None]
        self.assertTrue(student_caches and anchor_caches)
        self.assertFalse(any(left is right for left in student_caches for right in anchor_caches))
        self.assertEqual(ppo._digest(anchor), before)
        self.assertTrue(all(parameter.grad is None for parameter in anchor.parameters()))

    def test_real_model_auxiliary_ignores_value_head(self):
        rows = _records([('b', 3, 0.)])
        student = helpers.model(seed=41)
        anchor = copy.deepcopy(student).requires_grad_(False)
        with torch.no_grad():
            for parameter in anchor.value.parameters():
                parameter.add_(100.)
            target, _ = anchor(*batch(rows))
        logits, _ = student(*batch(rows))
        loss = forward_kl(target, logits, batch(rows)[4]).mean()
        loss.backward()
        self.assertLess(abs(float(loss.detach())), 1e-7)
        self.assertLess(float(torch.cat([p.grad.flatten() for p in student.parameters() if p.grad is not None]).norm()), 1e-6)
        self.assertTrue(all(p.grad is None for p in student.value.parameters()))

    def test_logical_window_and_micro_weights_are_unchanged(self):
        rows = _records([('b', 3, 0.), ('c', 1, 0.)])
        base = helpers.model(seed=41)
        anchor = helpers.model(seed=77).requires_grad_(False)
        outputs = []
        for coefficient in (0., .1):
            model = copy.deepcopy(base)
            optimizer = torch.optim.SGD(model.parameters(), lr=0.)
            random.seed(9)
            # A constant auxiliary value isolates exactly the existing window/micro weights.
            with patch('learning.ppo.forward_kl', side_effect=lambda target, current, mask: current[:, 0] * 0 + 2.):
                outputs.append(ppo.update(model, optimizer, rows, bc_records=rows, epochs=1, minibatch=2,
                    allow_policy_rehearsal=True, ppo_aux_target='frozen_bc_kl', bc_anchor=anchor, bc_aux=coefficient))
        self.assertAlmostEqual(outputs[1]['loss'] - outputs[0]['loss'], .2, places=6)
        self.assertEqual(outputs[1]['committed_decisions'], 4)
        self.assertEqual(outputs[1]['planned_windows'], 2)

    def test_new_mode_keeps_no_drop_and_kl_stop_settlement(self):
        model = helpers.model(seed=41)
        anchor = copy.deepcopy(model).requires_grad_(False)
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)
        rows = _records([('b', 2, 1.)])
        before = ppo._digest(model)
        random.seed(4)
        rng = random.getstate()
        result = ppo.update(model, optimizer, rows, bc_records=rows, epochs=2,
                            allow_policy_rehearsal=True, ppo_aux_target='frozen_bc_kl', bc_anchor=anchor)
        self.assertEqual(result['exit'], 'kl_stop')
        self.assertEqual(result['committed_steps'], 0)
        self.assertEqual(result['stopped_by_kl_steps'], 2)
        self.assertEqual(ppo._digest(model), before)
        self.assertEqual(random.getstate(), rng)
        heldout = _records([('b', 1, 0.)])
        from learning.data import split
        family = next(str(i) for i in range(100) if split(str(i)) == 'validation')
        heldout[0].update(game_family=family, split='validation')
        with self.assertRaisesRegex(ValueError, 'excluded by split'):
            ppo.update(model, optimizer, heldout, bc_records=rows, allow_policy_rehearsal=True,
                       ppo_aux_target='frozen_bc_kl', bc_anchor=anchor)


if __name__ == '__main__':
    unittest.main()
