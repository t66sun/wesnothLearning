"""Compare replay optimization with the original per-sample implementation."""
import unittest
from unittest.mock import patch

import numpy as np
import torch

from learning.features import ACTION, ENTITY, GEOMETRY, GLOBAL, OPPONENT, SPATIAL_CHANNELS
from learning.model import Policy, batch


class ReferencePolicy(Policy):
    def context(self, scene, histories, current_turns):
        output = []
        for i, history in enumerate(histories):
            h = scene.new_zeros(1, 128)
            slots, turns = [], []
            for j, row in enumerate(history):
                tensors = batch([row], scene.device, include_history=False)
                s, _ = self.encode_scene(tensors[0], tensors[1], tensors[3], tensors[5])
                h = self.gru(s, h)
                slots.append(torch.tanh(self.summary(s)))
                turns.append(row['turn'])
                slots, turns = slots[-32:], turns[-32:]
                if j < len(history) - 8:
                    h = h.detach()
                    slots = [v.detach() for v in slots]
            read = self.memory_read(h, slots, [current_turns[i] - t for t in turns])
            output.append(torch.cat([scene[i:i+1], h, read], -1))
        return torch.cat(output)


def row(seed, turn, game='a'):
    rng = np.random.default_rng(seed)
    values = lambda size: rng.normal(0, .1, size).astype(np.float32)
    entity = dict(id=game, type_index=1, features=values(len(ENTITY)))
    candidates = [dict(features=values(len(ACTION)), local=values(19*len(SPATIAL_CHANNELS)),
                       geometry=values(len(GEOMETRY)), actor=entity, target=None)
                  for _ in range(2)]
    for candidate in candidates:
        candidate['features'][-1] = 1
    return dict(turn=turn, game_id=game, opponents=[values(len(OPPONENT))],
                spatial=dict(board=values((len(SPATIAL_CHANNELS), 16, 16)), entities=[entity]),
                candidates=candidates, **{'global': values(len(GLOBAL))})


def samples():
    first = [row(i, i+1) for i in range(36)]
    second = [row(100+i, i+1, 'b') for i in range(12)]
    result = []
    for index, length in enumerate((0, 1, 8, 9, 12, 35, 36, 36)):
        result.append(dict(row(200+index, length+1), _history=first[:length]))
    result.append(dict(row(300, 13, 'b'), _history=second))
    return result


class ReplayOptimizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_shared_replay_matches_reference_outputs_gradients_and_recomputes(self):
        torch.manual_seed(8)
        model = Policy('duel')
        reference = ReferencePolicy('duel')
        reference.load_state_dict(model.state_dict())
        rows = samples()
        tensors = batch(rows)
        expected_unique = len({id(r) for sample in rows for r in sample['_history']})
        original_count = len(rows) + sum(len(r['_history']) for r in rows)
        optimizer = torch.optim.SGD(model.parameters(), lr=.01)
        reference_optimizer = torch.optim.SGD(reference.parameters(), lr=.01)
        for update in range(2):
            model.zero_grad(); reference.zero_grad()
            with patch.object(model, 'encode_scene', wraps=model.encode_scene) as encoder:
                actual = model(*tensors)
                encoded_count = sum(call.args[0].shape[0] for call in encoder.call_args_list)
                self.assertEqual(encoded_count, len(rows)+expected_unique)
                self.assertLess(encoded_count, original_count)
            expected = reference(*tensors)
            for left, right in zip(actual, expected):
                torch.testing.assert_close(left, right, atol=2e-6, rtol=2e-5)
            loss = actual[0].square().mean()+actual[1].square().mean()
            expected_loss = expected[0].square().mean()+expected[1].square().mean()
            loss.backward(); expected_loss.backward()
            for (name, parameter), (_, original) in zip(model.named_parameters(), reference.named_parameters()):
                self.assertEqual(parameter.grad is None, original.grad is None, name)
                if parameter.grad is not None:
                    torch.testing.assert_close(parameter.grad, original.grad, atol=3e-6, rtol=3e-4, msg=name)
            optimizer.step(); reference_optimizer.step()
        with torch.no_grad():
            for left, right in zip(model(*tensors), reference(*tensors)):
                torch.testing.assert_close(left, right, atol=2e-6, rtol=2e-5)
        print(f'encoder rows per forward: {original_count} -> {len(rows)+expected_unique}; '
              'outputs/gradients equivalent across two optimizer updates')

    def test_bulk_batch_matches_numpy_and_list_records_and_optional_memory_context(self):
        rows = samples()[-2:]
        rows[1]['opponents'] = []
        rows[1]['candidates'] = rows[1]['candidates'][:1]
        rows[1]['spatial']['entities'] = []

        def lists(value):
            if isinstance(value, np.ndarray): return value.tolist()
            if isinstance(value, dict): return {k: lists(v) for k, v in value.items()}
            if isinstance(value, list): return [lists(v) for v in value]
            return value

        left, right = batch(rows), batch(lists(rows))
        for x, y in zip(left[:5], right[:5]): torch.testing.assert_close(x, y, rtol=0, atol=0)
        for key, value in left[5].items():
            if isinstance(value, torch.Tensor): torch.testing.assert_close(value, right[5][key], rtol=0, atol=0)
        self.assertEqual(left[2].dtype, torch.float32)
        self.assertEqual(left[3].dtype, torch.bool)
        self.assertEqual(left[5]['types'].dtype, torch.int64)
        self.assertFalse(left[4][1, 1])
        self.assertEqual(left[5]['actors_indices'][1, 0], -1)
        model = Policy('duel')
        with torch.no_grad():
            expected = model(*left)
            scene = torch.zeros(len(rows), model.scene_width)
            cached = model.context(scene, left[5]['histories'], left[5]['turns'])[:, model.scene_width:]
            left[5]['memory_context'] = cached
            for actual, original in zip(model(*left), expected):
                torch.testing.assert_close(actual, original, atol=1e-6, rtol=1e-5)


if __name__ == '__main__':
    unittest.main()
