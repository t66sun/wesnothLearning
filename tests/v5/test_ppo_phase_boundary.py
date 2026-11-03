"""Stop a requested PPO phase at the format's own committed boundary."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from learning.__main__ import main
from learning.common import ROOT, read_json, write_json
from learning.phases import apply_phase, request_phase
from tests import test_validation_cadence as cadence


class PpoPhaseBoundaryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.runner = cadence.ValidationCadenceTests().runner(self.root / 'duel')
        self.runner.state.update(stage='ppo', phase='ppo', effective=True, policy_shards=[])
        self.runner.save()
        write_json(self.root / 'manifest.json', dict(config=dict(formats=['duel'])))
        write_json(self.root / 'clock.json', dict(update_deadline=3000000000, deadline=3000000000))

    def test_cli_and_api_pin_only_positive_ppo_batch_counts(self):
        for phase, count in [('bc', 1), ('evaluate', 2), ('ppo', 0), ('ppo', -1), ('ppo', 1.5)]:
            with self.subTest(phase=phase, count=count), self.assertRaises(ValueError):
                request_phase(self.root, phase, ppo_batches=count)
        with patch('builtins.print'):
            main(['phase', 'ppo', '--run-dir', str(self.root), '--ppo-batches', '2'])
        pending = read_json(self.root / 'phase/duel.pending.json')
        self.assertEqual(pending['ppo_batches'], 2)

    def test_next_request_at_a_clean_boundary_needs_another_applied_batch(self):
        r = self.runner
        r.controller.boundary = Mock(side_effect=LookupError('next rollout'))
        for batch in range(2):
            request_phase(self.root, 'ppo', ppo_batches=1)
            apply_phase(r)
            with self.assertRaisesRegex(LookupError, 'next rollout'):
                r.learn()
            r.state['history'].append(dict(batch=batch, method='ppo', updates=1))
            r.state['batch'] += 1
            r.run()
            self.assertEqual(r.state['stage'], 'ppo_complete')

    def test_resume_counts_only_new_applied_batches_and_finishes_due_validation(self):
        r = self.runner
        r.state.update(pending_train=dict(method='ppo'), batch=4,
                       history=[dict(batch=3, method='ppo', updates=9)])
        r.save()
        command = request_phase(self.root, 'ppo')['duel']
        write_json(self.root / 'phase/duel.pending.json', dict(command, ppo_batches=2))
        apply_phase(r)
        r.state = read_json(r.directory / 'state.json')
        updates = iter([3, 0, 4, 1])  # inherited, KL rejection, two new commits
        r.state['counters'].update(environment_games=0, collection_batches=0)
        r.controller.boundary = Mock()
        r.execute = Mock(return_value=([], []))

        def finish(prepared_bc=None):
            steps = next(updates, None)
            self.assertIsNotNone(steps, 'scheduled a rollout after reaching the PPO target')
            r.state['history'].append(dict(batch=r.state['batch'], method='ppo', updates=steps))
            r.state.update(batch=r.state['batch'] + 1, pending_train=None,
                           pending_validation='ppo' if steps == 1 else None)
            return True

        r.finish_train = finish
        r.validate_model = Mock(side_effect=lambda _: r.state.update(pending_validation=None))
        with patch('learning.experiment.rollout_jobs', return_value=[]), patch('learning.experiment.read_shards', return_value=[{}]):
            summary = r.run()
        self.assertEqual(summary['status'], 'stage_complete')
        self.assertEqual(r.state['stage'], 'ppo_complete')
        self.assertEqual(r.execute.call_count, 3)
        r.validate_model.assert_called_once_with('ppo')
        self.assertIsNone(r.state['pending_validation'])
        self.assertIsNone(r.state['pending_train'])
        request_phase(self.root, 'ppo')
        apply_phase(r)
        with patch.object(r.controller, 'boundary', side_effect=LookupError('next rollout')):
            with self.assertRaisesRegex(LookupError, 'next rollout'):
                r.learn()
