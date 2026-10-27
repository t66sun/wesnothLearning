"""R3: KL-stopped work is explicit; only interruptions defer frozen work."""
import unittest
from unittest.mock import patch

import torch

from learning import ppo
from tests.v5.test_ppo_plan import _records, _run, _bc


class KlAccountingTests(unittest.TestCase):
    def test_partial_kl_stop_is_settled_once_without_pending_retry(self):
        from learning.common import write_json
        from learning.data import split
        from learning.experiment import FormatExperiment
        from learning.updates import setup
        from tests.test_validation_cadence import ValidationCadenceTests
        from tests.v5 import helpers
        from tests.v5.test_rehearsal_source import human_rows

        families = [f'probe-{i}' for i in range(30) if split(f'probe-{i}') == 'train'][:5]
        rows = _records([(family, 1, 0.) for family in families])
        model = helpers.model(seed=41)
        _, windows, per_step, _, _ = setup(model, rows, 2)
        for index in ppo._epoch_order(5, 0, len(windows))[per_step:]:
            for row in windows[index]:
                row['log_probability'] -= 1.
        with helpers.temporary_directory() as root:
            write_json(root/'manifest.json', dict(test='R3'))
            directory = root/'duel'
            directory.mkdir()
            runner = ValidationCadenceTests().runner(directory)
            runner.config.update(engine='lite', epochs=1, seed=5, minibatch=2)
            runner.model = model
            runner.optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)
            runner.controller.state_dict = lambda: {}
            runner.state.update(phase='evaluate', pending_train=dict(method='ppo', paths=['policy'], cursor={}))
            runner.save = lambda: FormatExperiment.save(runner)
            runner.update_deadline = lambda: float('inf')
            with patch('learning.experiment.read_shards', side_effect=lambda paths, **kw: rows if paths == ['policy'] else human_rows()):
                self.assertTrue(runner.finish_train())
            self.assertIsNone(runner.state['pending_train'])
            self.assertEqual(runner.state['version'], 1)
            self.assertEqual(runner.state['counters']['planned_steps'], 2)
            self.assertEqual(runner.state['counters']['committed_steps'], 1)
            self.assertEqual(runner.state['counters']['stopped_by_kl_steps'], 1)
            saved = torch.load(directory/'latest.pt', weights_only=False)
            self.assertEqual(saved['runner']['counters'], runner.state['counters'])
            self.assertIsNone(saved['runner']['pending_train'])

    def test_kl_rejection_accounts_for_all_remaining_work(self):
        rows = _records([('b', 1, 1.)])
        model, _, result = _run(rows, epochs=2)
        self.assertEqual(result['stopped_by_kl_steps'], 2)
        self.assertEqual(result['stopped_by_kl_windows'], 2)
        self.assertEqual(result['deferred_steps'], 0)
        self.assertEqual(result['committed_steps'], 0)
        self.assertEqual(result['scope'], 'batch')
        self.assertEqual(result['policy_sha256_before'], ppo._digest(model))
        self.assertEqual(result['planned_steps'], result['committed_steps'] +
                         result['stopped_by_kl_steps'] + result['deferred_steps'])

    def test_deadline_defers_without_recounting_completed_work(self):
        rows = _records([('b', 2, 0.), ('c', 3, 0.)])
        model, optimizer, first = _run(rows, epochs=1)
        stopped = ppo.update(model, optimizer, rows, bc_records=_bc(), epochs=2,
                             deadline=0., progress=first['cursor'], plan_seed=5)
        self.assertEqual(stopped['scope'], 'deferred')
        self.assertEqual(stopped['cursor']['scope'], 'deferred')
        self.assertEqual(stopped['planned_steps'], 2)
        self.assertEqual(stopped['committed_steps'], 1)
        self.assertEqual(stopped['deferred_steps'], 1)
        self.assertEqual(stopped['deferred_windows'], 2)
        resumed = ppo.update(model, optimizer, rows, bc_records=_bc(), epochs=2,
                             progress=stopped['cursor'], plan_seed=5)
        self.assertEqual(resumed['planned_steps'], resumed['committed_steps'] +
                         resumed['stopped_by_kl_steps'] + resumed['deferred_steps'])
        self.assertEqual(resumed['deferred_steps'], 0)
        self.assertEqual(resumed['committed_decisions'], 10)

    def test_twenty_batches_have_conserved_work_totals(self):
        totals = dict(planned=0, committed=0, stopped=0, deferred=0)
        for batch in range(20):
            rows = _records([('b', 1, 1. if batch % 2 else 0.)])
            _, _, result = _run(rows, epochs=1)
            totals['planned'] += result['planned_steps']
            totals['committed'] += result['committed_steps']
            totals['stopped'] += result['stopped_by_kl_steps']
            totals['deferred'] += result['deferred_steps']
        self.assertEqual(totals, dict(planned=20, committed=10, stopped=10, deferred=0))


if __name__ == '__main__':
    unittest.main()
