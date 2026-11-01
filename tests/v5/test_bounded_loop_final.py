"""A successful subprocess exit cannot substitute for a completed final panel."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tests import bounded_training_loop as loop


class BoundedLoopFinalTests(unittest.TestCase):
    def run_loop(self, *, control_changes=None, state_changes=None, missing_report=False):
        snapshot = {fmt: dict(batch=1, stage='bc_complete', effective=True,
                             history=[], pending_train=None, error=None)
                    for fmt in loop.FORMATS}
        calls = []

        def stage(name, args, seconds, batch_limit=None):
            calls.append(name)
            if name.startswith('ppo_'):
                for state in snapshot.values():
                    state['batch'] += 1
                    state['stage'] = 'ppo_complete'
                    state['history'].append(dict(method='ppo', updates=1))
            if name == 'evaluate':
                for fmt, state in snapshot.items():
                    state['stage'] = 'finished'
                    control = dict(status='inconclusive', blocks=30, planned_blocks=30,
                                   missing_blocks=0, fault_games=0,
                                   distinct_scenarios=12, min_distinct=12)
                    if fmt == 'team2v2':
                        control.update(control_changes or {})
                        state.update(state_changes or {})
                        if missing_report:
                            continue
                    report = loop.RUN/fmt/'report/summary.json'
                    report.parent.mkdir(parents=True)
                    report.write_text(json.dumps(dict(format=fmt, error=None, controls={'astra': control})))
            return True

        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(loop, 'OUT', Path(tmp)/'observed'), \
             mock.patch.object(loop, 'RUN', Path(tmp)/'run'), \
             mock.patch.object(loop, 'ROOT', Path(tmp)), \
             mock.patch.object(loop, 'states', side_effect=lambda: copy.deepcopy(snapshot)), \
             mock.patch.object(loop, 'stage', side_effect=stage), \
             mock.patch.object(loop, 'phase'), \
             mock.patch.dict('os.environ', SOURCE_COMMIT='fixture', WESNOTH_EXE='unused'):
            (Path(tmp)/'runs').mkdir()
            code = loop.main()
            return code, calls, json.loads((loop.OUT/'result.json').read_text())

    def test_missing_and_underfilled_final_panels_stop_before_export(self):
        cases = [dict(missing_report=True),
                 dict(control_changes=dict(blocks=29, missing_blocks=1)),
                 dict(control_changes=dict(blocks=29, planned_blocks=29)),
                 dict(control_changes=dict(fault_games=1)),
                 dict(control_changes=dict(distinct_scenarios=11)),
                 dict(control_changes=dict(status='infrastructure_error'))]
        for case in cases:
            with self.subTest(case=case):
                code, calls, result = self.run_loop(**case)
                self.assertEqual(code, 1)
                self.assertNotIn('export', calls)
                self.assertIn('final', result['reason'])

    def test_failed_evaluation_state_stops_before_export(self):
        for state in (dict(stage='failed', error='trainer failed'),
                      dict(stage='final'), dict(pending_train={'method': 'ppo'})):
            with self.subTest(state=state):
                code, calls, _ = self.run_loop(state_changes=state)
                self.assertEqual(code, 1)
                self.assertNotIn('export', calls)

    def test_complete_panel_does_not_require_a_strength_pass(self):
        for status in ('passed', 'not_passed', 'inconclusive'):
            with self.subTest(status=status):
                code, calls, result = self.run_loop(control_changes=dict(status=status))
                self.assertEqual(code, 0)
                self.assertEqual(calls[-1], 'export')
                self.assertEqual(result['status'], 'OBSERVED')


if __name__ == '__main__':
    unittest.main()
