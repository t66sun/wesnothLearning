"""Public native cells, visibility, and non-square convolution boundaries."""
from collections import deque
from copy import deepcopy
import runpy
import unittest

import numpy as np
import torch

from learning.common import ROOT
from learning.data import validate_record
from learning.features import SPATIAL_CHANNELS, TERRAIN_TYPES
from learning.model import batch
from learning.rewards import hex_neighbors
from tests.v5 import helpers


FIXTURES = runpy.run_path(ROOT / 'verification/representation_information_20261106/fixtures.py')


def actor(spec):
    return FIXTURES['actor_row'](FIXTURES['capture'](spec)[1])


def route_length(known, terrain, start=(4, 8), goal=(28, 8)):
    height, width = known.shape
    open_cells = {(x+1, y+1) for y in range(height) for x in range(width)
                  if known[y, x] and terrain[y, x] != 'Ww'}
    queue = deque([(start, 0)])
    open_cells.remove(start)
    while queue:
        cell, length = queue.popleft()
        if cell == goal:
            return length
        for neighbor in hex_neighbors(cell):
            if neighbor in open_cells:
                open_cells.remove(neighbor)
                queue.append((neighbor, length+1))
    return None


class NativeSpatialGridTests(unittest.TestCase):
    def test_public_terrain_cells_recover_route_connectivity(self):
        specs = FIXTURES['pairs']()['resampling_connectivity']
        left, right = [actor(spec) for spec in specs]
        self.assertTrue(left['spatial']['board'] != right['spatial']['board'],
                        'the two public routes produced the same board input')
        self.assertEqual({k: v for k, v in left.items() if k != 'spatial'},
                         {k: v for k, v in right.items() if k != 'spatial'})
        self.assertEqual(left['spatial']['entities'], right['spatial']['entities'])
        distances = []
        for row, spec in zip((left, right), specs):
            spatial = row['spatial']
            self.assertEqual((spatial['width'], spatial['height']), (32, 16))
            channels = dict(zip(SPATIAL_CHANNELS, np.asarray(spatial['board'])))
            known = channels['known']
            self.assertTrue(np.all(known == 1))
            indices = np.rint(channels['terrain_identity'] * (len(TERRAIN_TYPES)-1)).astype(int)
            terrain = np.asarray(TERRAIN_TYPES)[indices]
            self.assertEqual(terrain.ravel().tolist(), spec['terrain'])
            distances.append(route_length(known, terrain))
        self.assertEqual(distances, [24, None])

    def test_unknown_cells_and_last_seen_entities_follow_public_knowledge(self):
        pairs = FIXTURES['pairs']()
        left, right = pairs['hidden_truth_control']
        right = deepcopy(right)
        right['units'].append(FIXTURES['unit']('unseen', 'Fighter', 2, 25, 5, 32))
        self.assertEqual(actor(left), actor(right))
        known, shrouded = [actor(spec) for spec in pairs['knowledge_mask_compensation']]
        known_cell, unknown_cell = [np.asarray(r['spatial']['board'])[:, 7, 19] for r in (known, shrouded)]
        self.assertEqual(known_cell[:2].tolist(), [1, 0])
        self.assertGreater(known_cell[-1], 0)
        self.assertFalse(unknown_cell.any())

        left, right = FIXTURES['last_seen_pair']()
        self.assertEqual(left['spatial']['board'], right['spatial']['board'])
        self.assertEqual([next(e['x'] for e in r['spatial']['entities'] if e['side'] == 2)
                          for r in (left, right)], [6, 7])

    def test_padding_keeps_valid_convolution_readout_and_gradients(self):
        small = helpers.synthetic_decision_row()
        big = actor(FIXTURES['pairs']()['resampling_connectivity'][0])
        height, width = (small['spatial'][key] for key in ('height', 'width'))
        model = helpers.model(seed=67).double()
        with torch.no_grad():
            model.conv1.weight.fill_(.02)
            model.conv1.bias.fill_(.2)
            model.conv2.weight.fill_(.01)
            model.conv2.bias.fill_(.05)
            model.board_readout.weight[:, 16:32] = .125 * torch.eye(16)
            model.board_readout.weight[:, 32:] = -.25 * torch.eye(16)

        def evaluate(rows):
            tensors = batch(rows, dtype=torch.float64)
            board = tensors[-1]['board'].requires_grad_()
            activations = []

            def observe(module, args, output):
                activations.append(output[0].detach())

            handles = [layer.register_forward_hook(observe) for layer in (model.conv2, model.board_readout)]
            try:
                logits, value = model(*tensors)
            finally:
                for handle in handles:
                    handle.remove()
            policy = logits[0, :len(small['candidates'])]
            weights = [weight for module in (model.conv1, model.conv2, model.board_readout)
                       for weight in module.parameters()]
            grad_board, *grads = torch.autograd.grad(policy.sum() + value[0], [board, *weights])
            return (activations[0][:, :height, :width], activations[1], policy, value[0],
                    grad_board[0, :, :height, :width], grads)

        self.assertNotEqual(height, width)
        torch.testing.assert_close(evaluate([small]), evaluate([small, big]), rtol=1e-10, atol=1e-11)

    def test_old_rows_and_mismatched_memory_dimensions_are_rejected(self):
        row = helpers.synthetic_decision_row()
        for legacy in (5, 6):
            with self.assertRaisesRegex(ValueError, 'feature schema mismatch'):
                validate_record(dict(row, schema=legacy))
        old = {k: v for k, v in row['spatial'].items() if k not in ('width', 'height')}
        with self.assertRaisesRegex(ValueError, 'map dimensions'):
            batch([dict(row, spatial=old)])
        big = actor(FIXTURES['pairs']()['resampling_connectivity'][0])
        with self.assertRaisesRegex(ValueError, 'memory write spatial grid'):
            validate_record(dict(row, memory_write={'spatial': big['spatial']}))
