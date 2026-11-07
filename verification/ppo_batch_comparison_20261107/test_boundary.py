"""Evidence regression for equal-wall checkpoint selection at batch boundaries."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from learning.common import write_json
from verification.ppo_batch_comparison_20261107 import arm


class WallBoundaryTests(unittest.TestCase):
    def test_first_crossings_and_last_wall_checkpoint_survive_pending_or_late_work(self):
        root = Path(self.enterContext(TemporaryDirectory()))
        runner = arm.WallExperiment.__new__(arm.WallExperiment)
        runner.directory = root/'duel'
        runner.directory.mkdir()
        runner.clock = dict(started=0, update_deadline=85, deadline=90)
        runner.state = dict(phase='ppo', batch=38,
                            history=[dict(method='bc')], pending_train=None, pending_validation=None)
        write_json(root/'budget.json', dict(history_start=1, first_batch=38,
                   admission_deadline=85, hard_deadline=90))
        latest = runner.directory/'latest.pt'
        endpoints = runner.directory/'endpoints'

        def batch(targets, finished_at, weights, *, settled=True, updates=1):
            state = runner.state
            state['pending_train'] = dict(method='ppo')

            def production_finish(*_args, **_kwargs):
                if settled:
                    state['history'].append(dict(method='ppo', batch=state['batch'],
                                            planned_targets=targets, updates=updates))
                    state['batch'] += 1
                    state['pending_train'] = None
                next_checkpoint = latest.with_suffix('.next')
                next_checkpoint.write_bytes(weights)
                next_checkpoint.replace(latest)
                return settled

            with patch.object(arm.paired.PairedExperiment, 'finish_train', side_effect=production_finish), \
                    patch.object(arm.time, 'time', return_value=finished_at):
                self.assertIs(runner.finish_train(), settled)

        batch(9_990, 30, b'prior')
        self.assertFalse((endpoints/'fresh-10000.pt').exists())
        # A zero-step KL rejection updates latest.pt without writing last_ppo.pt.
        batch(25, 50, b'zero-step boundary', updates=0)
        batch(19_980, 60, b'below 30000')
        batch(23, 70, b'second crossing')
        with patch.object(arm.time, 'time', return_value=80):
            self.assertEqual(runner.update_deadline(), 90)
        batch(7, 85, b'last settled tail')
        with patch.object(arm.time, 'time', return_value=85):
            self.assertEqual(runner.update_deadline(), 0)
        batch(100, 89, b'partial weights', settled=False)
        self.assertEqual((endpoints/'wall.pt').read_bytes(), b'last settled tail')
        batch(100, 91, b'outside budget')
        self.assertEqual((endpoints/'wall.pt').read_bytes(), b'last settled tail')
        self.assertEqual((endpoints/'fresh-10000.pt').read_bytes(), b'zero-step boundary')
        self.assertEqual((endpoints/'fresh-30000.pt').read_bytes(), b'second crossing')
