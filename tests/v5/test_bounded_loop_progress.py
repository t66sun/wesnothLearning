"""Manual-loop progress checks without collection or optimizer execution."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tests import bounded_training_loop as loop


class BoundedLoopProgressTests(unittest.TestCase):
    def run_loop(self, *, bc_updates=1, resume_updates=1, pending=False, pending_validation=False, failed=False):
        initial_batches = dict(duel=5, ffa4=2, team2v2=1)
        snapshot = {fmt: dict(batch=batch, stage='bc_complete', effective=True,
                             history=[dict(method='bc', updates=bc_updates)], pending_train=None, error=None)
                    for fmt, batch in initial_batches.items()}
        calls = []

        def stage(name, args, seconds, batch_limit=None):
            calls.append((name, batch_limit))
            if name.startswith('ppo_'):
                for state in snapshot.values():
                    state['batch'] += 1
                    state['stage'] = 'ppo_complete'
                    updates = 2 if name == 'ppo_first' else resume_updates
                    if updates:
                        state['history'].append(dict(method='ppo', updates=updates))
                    if name == 'ppo_resume':
                        state['pending_train'] = {'method': 'ppo'} if pending else None
                        state['pending_validation'] = 'ppo' if pending_validation else None
                        if failed:
                            state.update(stage='failed', error='trainer failed')
            return name != 'evaluate'  # Stop before any real evaluation/export.

        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(loop, 'OUT', Path(tmp)/'observed'), \
             mock.patch.object(loop, 'RUN', Path(tmp)/'run'), \
             mock.patch.object(loop, 'states', side_effect=lambda: copy.deepcopy(snapshot)), \
             mock.patch.object(loop, 'stage', side_effect=stage), \
             mock.patch.object(loop, 'phase') as phase, \
             mock.patch.dict('os.environ', SOURCE_COMMIT='fixture', WESNOTH_EXE='unused'):
            self.assertEqual(loop.main(), 1)
            result = json.loads((loop.OUT/'result.json').read_text())
            boundaries = {p.name: json.loads(p.read_text()) for p in loop.OUT.glob('*-boundary.json')}
            return calls, phase.call_args_list, result, boundaries

    def test_each_format_gets_its_own_ppo_batch_allowance(self):
        calls, phases, _, boundaries = self.run_loop()
        limits = dict(calls)
        self.assertEqual(limits['ppo_first'], dict(duel=9, ffa4=6, team2v2=5))
        self.assertEqual(limits['ppo_resume'], dict(duel=10, ffa4=7, team2v2=6))
        self.assertEqual(boundaries['ppo_first-boundary.json']['before'], dict(duel=5, ffa4=2, team2v2=1))
        self.assertEqual([call.args[2:] for call in phases if call.args[0] == 'ppo'],
                         [('--ppo-batches', 1)] * 2)

    def test_passed_bc_gate_requires_new_bc_work(self):
        calls, _, result, _ = self.run_loop(bc_updates=0)
        self.assertEqual([name for name, _ in calls], ['bc'])
        self.assertIn('BC update', result['reason'])

    def test_resume_must_commit_new_updates(self):
        calls, phases, result, _ = self.run_loop(resume_updates=0)
        self.assertNotIn('evaluate', dict(calls))
        self.assertEqual([call.args[0] for call in phases], ['ppo', 'ppo'])
        self.assertIn('ppo_resume', result['reason'])

    def test_resume_must_finish_at_a_committed_boundary(self):
        for options in (dict(pending=True), dict(pending_validation=True), dict(failed=True)):
            with self.subTest(options=options):
                calls, _, result, _ = self.run_loop(**options)
                self.assertNotIn('evaluate', dict(calls))
                self.assertIn('ppo_resume', result['reason'])

    def test_stage_enforces_each_formats_limit(self):
        for batches, stopped in (([5, 2, 1], False), ([8, 6, 4], True)):
            with self.subTest(batches=batches), tempfile.TemporaryDirectory() as tmp, \
                 mock.patch.object(loop, 'OUT', Path(tmp)), \
                 mock.patch.object(loop, 'states', return_value={
                     fmt: dict(batch=batch) for fmt, batch in zip(loop.FORMATS, batches)}), \
                 mock.patch.object(loop.subprocess, 'Popen') as popen, \
                 mock.patch.object(loop.os, 'killpg') as kill, \
                 mock.patch.object(loop.time, 'sleep'):
                popen.return_value.poll.side_effect = [None, 0]
                popen.return_value.wait.return_value = -15 if stopped else 0
                result = loop.stage('ppo', ['unused'], 100,
                                    batch_limit=dict(duel=9, ffa4=6, team2v2=5))
                self.assertEqual(result, not stopped)
                self.assertEqual(kill.call_count, int(stopped))
                report = json.loads((Path(tmp)/'ppo.json').read_text())
                self.assertEqual(report['stop_reason'], 'committed_batch_limit' if stopped else None)


if __name__ == '__main__':
    unittest.main()
