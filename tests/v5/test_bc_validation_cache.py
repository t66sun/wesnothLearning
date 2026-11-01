"""BC validation reuses unchanged history without retaining it across evaluations."""
import unittest
from unittest.mock import patch

import torch

from learning.bc import imitation_quality
from learning.model import Policy
from tests.v5.test_replay_optimization import row, samples


class UncachedPolicy(Policy):
    def forward(self, *tensors):
        payload = dict(tensors[-1])
        payload.pop('history_cache', None)
        return super().forward(*tensors[:-1], payload)


def validation_rows():
    history = samples()[-2]['_history']  # Includes the 32-slot memory rollover.
    result = []
    for index in range(130):
        record = row(500 + index, 37)
        for candidate, kind in zip(record['candidates'], ('recruit', 'move')):
            candidate['kind'] = kind
        record.update(format='duel', split='validation', choice=index % 2, _history=history)
        result.append(record)
    return result


class BCValidationCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)

    def test_gate_encodes_shared_history_once_and_matches_uncached_metrics(self):
        torch.manual_seed(29)
        model = Policy('duel')
        reference = UncachedPolicy('duel')
        reference.load_state_dict(model.state_dict())
        records = validation_rows()
        with patch.object(model, 'encode_scene', wraps=model.encode_scene) as encoder:
            actual = imitation_quality(model, records)
            encoded = sum(call.args[0].shape[0] for call in encoder.call_args_list)
        expected = imitation_quality(reference, records)
        self.assertEqual(encoded, 166)  # 130 current scenes plus 36 distinct history rows.
        self.assertEqual(actual['effective'], expected['effective'])
        left, right = actual['formats']['duel'], expected['formats']['duel']
        for key in ('samples', 'kinds', 'accuracy', 'uniform_accuracy', 'uniform_entropy'):
            self.assertEqual(left[key], right[key], key)
        self.assertAlmostEqual(left['cross_entropy'], right['cross_entropy'], places=6)

    def test_new_gate_recomputes_history_for_changed_weights(self):
        torch.manual_seed(31)
        model = Policy('duel')
        records = validation_rows()
        first = imitation_quality(model, records)
        with torch.no_grad():
            model.gru.bias_ih.add_(.25)
            model.scorer[-1].weight.mul_(2)
        reference = UncachedPolicy('duel')
        reference.load_state_dict(model.state_dict())
        with patch.object(model, 'encode_scene', wraps=model.encode_scene) as encoder:
            actual = imitation_quality(model, records)
            encoded = sum(call.args[0].shape[0] for call in encoder.call_args_list)
        expected = imitation_quality(reference, records)
        self.assertEqual(encoded, 166)
        self.assertAlmostEqual(actual['formats']['duel']['cross_entropy'],
                               expected['formats']['duel']['cross_entropy'], places=6)
        self.assertNotEqual(first['formats']['duel']['cross_entropy'],
                            actual['formats']['duel']['cross_entropy'])


if __name__ == '__main__':
    unittest.main()
