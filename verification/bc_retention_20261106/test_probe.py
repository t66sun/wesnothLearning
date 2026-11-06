"""Assertions for the diagnostic's proposed policy-distribution objective."""
import importlib.util
from pathlib import Path
import unittest

import torch

spec = importlib.util.spec_from_file_location('retention_probe', Path(__file__).with_name('probe.py'))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class AnchorObjectiveTests(unittest.TestCase):
    def test_matching_distribution_has_zero_loss_and_gradient(self):
        logits = torch.tensor([[1., -2., -torch.inf], [3., 1., 0.]], requires_grad=True)
        mask = torch.isfinite(logits)
        loss = probe.forward_kl(logits, logits, mask).mean()
        loss.backward()
        self.assertAlmostEqual(float(loss), 0., places=7)
        torch.testing.assert_close(logits.grad, torch.zeros_like(logits), atol=1e-7, rtol=0)
        # A sampled hard action has a nonzero gradient at this same policy.
        hard = logits.detach().clone().requires_grad_(True)
        torch.nn.functional.cross_entropy(hard, torch.tensor([0, 0])).backward()
        self.assertGreater(float(hard.grad.norm()), .01)

    def test_soft_target_gradient_and_padding(self):
        anchor = torch.tensor([[0., 2., -torch.inf], [1., -1., 0.]], requires_grad=True)
        student = torch.tensor([[2., 0., -torch.inf], [0., 2., 1.]], requires_grad=True)
        loss = probe.forward_kl(anchor, student, torch.isfinite(student)).mean()
        loss.backward()
        self.assertGreater(float(loss), 0.)
        self.assertIsNone(anchor.grad)
        self.assertTrue(bool(torch.isfinite(student.grad).all()))
        torch.testing.assert_close(student.grad, (student.softmax(-1) - anchor.softmax(-1)) / 2)
        self.assertEqual(float(student.grad[0, 2]), 0.)

    def test_kl_direction_is_anchor_to_student(self):
        anchor = torch.tensor([0., 3.])
        student = torch.tensor([1., 0.])
        expected = torch.distributions.kl_divergence(
            torch.distributions.Categorical(logits=anchor),
            torch.distributions.Categorical(logits=student))
        actual = probe.forward_kl(anchor, student, torch.ones(2, dtype=torch.bool))
        torch.testing.assert_close(actual, expected)
        reverse = probe.forward_kl(student, anchor, torch.ones(2, dtype=torch.bool))
        self.assertNotAlmostEqual(float(actual), float(reverse), places=3)


if __name__ == '__main__':
    unittest.main()
