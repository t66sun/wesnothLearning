"""One launch fixture for ordinary BC shortfalls and independent route progress."""
from pathlib import Path
import signal
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from learning.common import read_json, sha256, write_json
from verification.ppo_batch_comparison_20261107 import driver, panels


class QualificationTests(unittest.TestCase):
    def test_bc_shortfall_keeps_independent_frozen_comparisons(self):
        for failed in ('gate_not_qualified', 'deadline', 'trainer_failed'):
            with self.subTest(failed=failed), TemporaryDirectory() as temporary:
                self.exercise(Path(temporary), failed)

    def exercise(self, root, failed):
        initializer = root/'actor/duel/last_bc.pt'
        initializer.parent.mkdir(parents=True)
        initializer.write_bytes(b'frozen actor')
        endpoint = dict(version=1, checkpoint_sha256='checkpoint', weights_sha256='weights')
        launch = dict(
            actor_initializer=str(initializer.parents[1]), base_bc_parent=str(root/'base-bc'),
            seconds=dict(total=100_000, native=0, preflight=100, validation=100, holdout=100, report=100),
            contracts={name: {'source': str(root/name)} for name in driver.CONTRACTS},
        )
        launch_path = root/'launch.json'
        write_json(launch_path, launch)
        called = []
        gate = dict(status='insufficient_design', distinct_scenarios=0, min_distinct=12)

        def train_bc(parent, **_):
            is_b = parent == root/'b/runs/output/bc'
            status = 'trainer_failed' if is_b and failed == 'trainer_failed' else 'stage_complete'
            if is_b:
                write_json(parent/'duel/bc_gate.json', gate)
            report = dict(status=status, phase='bc', pretraining_complete=not is_b)
            return SimpleNamespace(run=lambda: dict(status=status, formats={'duel': report}))

        def stage(output, label, contract, kind, deadline, **options):
            called.append(label)
            result = output/f'{label}-result'
            outcome = dict(timed_out=False, exit_code=0, wall_seconds=1)
            if kind == 'preflight':
                write_json(result, dict(result=dict(bc=dict(endpoint=endpoint))))
            elif kind == 'bc':
                if label == 'bc-b' and failed == 'deadline':
                    parent = Path(options['parent'])
                    write_json(parent/'duel/bc_gate.json', gate)
                    return result, dict(outcome, timed_out=True, exit_code=-signal.SIGTERM)
                driver.stage(dict(options, stage=kind, contract=contract, deadline=deadline, output=str(result)))
            elif kind == 'ppo':
                self.assertEqual(deadline-options['admission'],
                                 driver.INPUTS['seconds']['ppo_hard']-driver.INPUTS['seconds']['ppo_admission'])
                write_json(Path(options['run'])/'budget.json', {})
            elif kind in ('validation', 'holdout'):
                view = dict(design=[('scene', 17, 0, (1,))], scenario_maps={'scene': 'map'}, missing=[])
                full = dict(view, roles={role: {'scene': .5} for role in options['full']})
                small = dict(view, roles={role: {'scene': .5} for role in options['small']})
                write_json(result/'summary.json', dict(full=full, small=small, actual_games=0))
            return result, outcome

        output = root/'output'
        with patch.object(driver, 'check_launch'), patch.object(driver, 'freeze_board'), \
                patch.object(driver, 'worker_identity'), patch.object(driver, 'run_stage', side_effect=stage), \
                patch.object(driver.coordinator, 'Experiment', side_effect=train_bc), \
                patch.object(driver, 'bc_endpoint', return_value=dict(endpoint=endpoint)), \
                patch.object(driver, 'check_first_online', return_value={}), \
                patch.object(driver.arm, 'summarize', return_value=dict(
                    roles={'wall': endpoint}, ledger=dict(error=None, settled_batches=1))), \
                patch.dict(driver.INPUTS, actor_initializer_sha256=sha256(initializer)), \
                patch.dict(panels.INPUTS, bootstrap_samples=5):
            self.assertFalse(driver.run(output, launch_path))

        report = read_json(output/'result.json')
        if failed == 'trainer_failed':
            self.assertEqual(report['status'], 'incomplete')
            self.assertIn('BC trainer failed', report['reason'])
            self.assertNotIn('bc-c', called)
            return
        self.assertEqual(report['status'], 'incomplete_bc')
        bc = read_json(output/'bc-b-qualification.json')
        self.assertEqual((bc['reason'], bc['gate']), (failed, gate))
        self.assertEqual(report['bc_shortfalls'], {'b': failed})
        self.assertEqual(called[3:5], ['bc-b', 'bc-c'])
        self.assertEqual(called[5:-6], [f'{route}-{seed}' for route, seed in driver.INPUTS['cell_order']
                                       if route != 'b'])
        self.assertEqual(called[-6:], ['validation-base', 'validation-c', 'holdout-base', 'holdout-c',
                                       'mc-base', 'mc-c'])
        for partition in ('validation', 'holdout'):
            contrasts = report[partition]['contrasts']
            self.assertEqual(contrasts['a']['wall']['status'], 'observed')
            self.assertEqual(contrasts['c']['wall']['status'], 'observed')
            self.assertEqual(contrasts['b']['wall'],
                             dict(status='bc_unqualified', reason=failed, matched_seeds=[]))
