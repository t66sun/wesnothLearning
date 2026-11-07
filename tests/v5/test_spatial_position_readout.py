"""Position moments on the recorded distant-hill pair."""
import unittest
from unittest.mock import patch

import torch

from learning.features import SPATIAL_CHANNELS
from learning.model import Policy, batch
from tests.v5.test_spatial_native_grid import FIXTURES


def _hill_rows():
    pair = FIXTURES['pairs']()['pooling_location']
    return [FIXTURES['actor_row'](FIXTURES['capture'](spec)[1]) for spec in pair]


def _terrain_model():
    torch.manual_seed(31)
    model = Policy('duel').double()
    with torch.no_grad():
        for layer in (model.conv1, model.conv2):
            layer.weight.zero_()
            layer.bias.zero_()
        model.conv1.weight[0, SPATIAL_CHANNELS.index('terrain_identity'), 1, 1] = 1
        model.conv2.weight[0, 0, 1, 1] = 1
    return model


class SpatialPositionReadoutTests(unittest.TestCase):
    def test_distant_hill_changes_position_feature_with_equal_global_mean(self):
        model = _terrain_model()
        g, opponents, _, mask, _, payload = batch(_hill_rows(), dtype=torch.float64)
        channel = SPATIAL_CHANNELS.index('terrain_identity')
        terrain_delta = payload['board'][0, channel, 4, 7] - payload['board'][1, channel, 4, 7]
        with torch.no_grad():
            original, _ = model.encode_scene(g, opponents, mask, payload)
            # The chosen coefficient is absent when this assertion runs against mean pooling.
            if hasattr(model, 'board_readout'):
                model.board_readout.weight[0, 32] = 1
            weighted, _ = model.encode_scene(g, opponents, mask, payload)
        torch.testing.assert_close(original[0], original[1], rtol=0, atol=1e-15)
        self.assertGreater(abs(float(terrain_delta)), 0.1)
        self.assertAlmostEqual(float(weighted[1, -16] - weighted[0, -16]),
                               float(terrain_delta) * (2 * 6 / 16) / 256, places=14)

    def test_identity_preserves_mean_forward_and_moments_receive_gradients(self):
        model = _terrain_model()
        left, right = _hill_rows()
        tensors = batch([dict(right, turn=2, _history=[left])], dtype=torch.float64)
        encode_scene = model.encode_scene

        def mean_scene(g, opponents, mask, payload):
            scene, entities = encode_scene(g, opponents, mask, payload)
            h = torch.relu(model.conv2(torch.relu(model.conv1(payload['board']))))
            return torch.cat((scene[:, :-16], h.mean((-1, -2))), dim=-1), entities

        with torch.no_grad():
            with patch.object(model, 'encode_scene', side_effect=mean_scene):
                baseline = model(*tensors)
            torch.testing.assert_close(model(*tensors), baseline, rtol=0, atol=0)

        g, opponents, _, mask, _, payload = tensors
        scene, _ = model.encode_scene(g, opponents, mask, payload)
        self.assertEqual(scene.shape, (1, g.shape[-1] + 32 + 64 + 16))
        self.assertEqual((model.gru.input_size, model.gru.hidden_size), (scene.shape[-1], 128))
        scene[:, -16:].sum().backward()
        grad = model.board_readout.weight.grad
        self.assertTrue(grad[:, 16:32].abs().any())
        self.assertTrue(grad[:, 32:].abs().any())
