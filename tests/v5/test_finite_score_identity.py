"""New-task initialization and strict training identity, without collection."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import torch

from learning.__main__ import main, parser, run_config
from learning.branch import validate_bc_inputs
from learning.checkpoints import checkpoint, validate_checkpoint
from learning.common import ROOT, read_json, sha256, write_json
from learning.coordinator import Experiment
from learning.experiment import FormatExperiment, default_config
from learning.manifest import verify_frozen
from learning.maps import scenario_family
from learning.tasks import LEGACY_TASK, TASK_ID, reward_config
from tests.v5 import helpers


class FiniteScoreIdentityTests(unittest.TestCase):
    def test_legacy_manifest_cannot_resume_or_branch_as_the_same_task(self):
        with self.assertRaisesRegex(ValueError, 'training task differs'):
            verify_frozen(dict(config=dict(training_max_turns=60)))
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            parent = Path(temporary)/'parent'
            write_json(parent/'manifest.json', dict(config=default_config('cpu') | dict(task_id=LEGACY_TASK)))
            write_json(parent/'clock.json', {})
            with self.assertRaisesRegex(ValueError, '--branch-weights-only'):
                Experiment(Path(temporary)/'child', config=default_config('cpu'), branch_from=parent)
            self.assertFalse((Path(temporary)/'child').exists())

    def test_checkpoint_task_checked_for_training_but_legacy_inference_loads(self):
        from learning.export import load_model
        with tempfile.TemporaryDirectory() as temporary:
            model = helpers.model()
            path = Path(temporary)/'legacy.pt'
            checkpoint(path, model, torch.optim.Adam(model.parameters()))
            _, old = load_model(path, 'duel')
            with self.assertRaisesRegex(ValueError, 'checkpoint training task differs'):
                validate_checkpoint(old, 'duel', expected_task=TASK_ID)
            validate_checkpoint(dict(old, task_id=TASK_ID), 'duel', expected_task=TASK_ID)

    def test_task_identity_preserves_physical_scenario_partitions(self):
        from learning.sample import opening_map
        job = dict(bots=['a','b'], factions=['Rebels','Loyalists'], map_override=opening_map(2),
                   max_turns=30, meta=dict(format='duel'))
        legacy = scenario_family(job)
        self.assertEqual(legacy, scenario_family(job | dict(task_id=TASK_ID)))
        self.assertNotEqual(legacy, scenario_family(job | dict(max_turns=60)))
        self.assertEqual(legacy, scenario_family(copy.deepcopy(job)))

    def test_restart_bc_rejects_legacy_supervision_contract(self):
        old = dict(row_schema=6, batch_contract='scenario-v2/no-drop-v1', teacher={},
                   opponents=[], config=dict(training_max_turns=30))
        new = old | dict(task_id=TASK_ID)
        with self.assertRaisesRegex(ValueError, 'matching task_id'):
            validate_bc_inputs(old, new)

    def test_weights_only_cli_is_explicit_and_selects_last_bc(self):
        args = parser().parse_args(['run', '--branch-from', 'parent', '--branch-weights-only',
                                   '--branch-checkpoint', 'last_bc', '--phase', 'bc'])
        self.assertTrue(args.branch_weights_only)
        self.assertEqual(args.branch_checkpoint, 'last_bc')
        for config in (dict(branch_weights_only=True),
                       dict(branch_weights_only=True, phase='bc', branch_restart_bc=True),
                       dict(branch_checkpoint='last_bc', phase='bc')):
            with self.subTest(config=config), self.assertRaises(ValueError):
                Experiment(ROOT/'unused-new-task', config=config, branch_from=ROOT/'unused-parent')

    def test_old_bc_actor_initializes_fresh_task_without_inheriting_training_state(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            parent, child = Path(temporary)/'parent', Path(temporary)/'child'
            config = default_config('cpu') | dict(formats=['duel'], phase='bc', human_data=str(parent/'empty'))
            old_config = config | dict(task_id=LEGACY_TASK, training_max_turns=60,
                                       formats=['duel','ffa4','team2v2'])
            old_manifest = dict(config=old_config, opponents=[dict(path='gpt6astra.zip', sha256='astra')],
                                rules=dict(rules_sha256='fixture'), baseline=dict(path='unused'))
            write_json(parent/'manifest.json', old_manifest)
            write_json(parent/'clock.json', dict(started=1, update_deadline=2, deadline=3))
            model = helpers.model(seed=31)
            with torch.no_grad():
                model.value[-1].bias.fill_(123.)
            state = dict(format='duel', version=17, clock={'old': 1}, stage='bc_complete',
                         effective=True, teacher_shards=['old-teacher'], dagger_shards=['old-dagger'],
                         policy_shards=['old-policy'], pending_train=None, pending_validation=None,
                         reward_controller=dict(config=helpers.config()), counters=dict(optimizer_steps=99),
                         snapshots=['old'], history=['old'], frozen_bc_anchor={'old': 'anchor'})
            old_identity = object.__new__(FormatExperiment)
            old_identity.config = old_config
            source = parent/'duel/last_bc.pt'
            checkpoint(source, model, torch.optim.Adam(model.parameters(), lr=.02), runner=state,
                       manifest_sha256=sha256(parent/'manifest.json'), **old_identity.identity())
            original = sha256(source)
            def freeze(directory, opponents, wesnoth, requested):
                manifest = old_manifest | dict(config=requested, task_id=TASK_ID)
                write_json(directory/'manifest.json', manifest)
                return manifest, []
            with mock.patch('learning.coordinator.freeze', side_effect=freeze):
                run = Experiment(child, config=config | dict(branch_weights_only=True, branch_checkpoint='last_bc'),
                                 branch_from=parent)
            branch = read_json(child/'branch.json')
            self.assertTrue(branch['reset_optimizer'])
            self.assertTrue(branch['weights_only'])
            self.assertEqual(set(branch['checkpoints']), {'duel'})
            self.assertEqual(branch['checkpoints']['duel']['source'], str(source))
            self.assertEqual(branch['checkpoints']['duel']['sha256'], original)
            collector = mock.Mock(side_effect=AssertionError('fixture must not collect'))
            with mock.patch.object(FormatExperiment, 'ensure_export', return_value='unused'):
                runner = FormatExperiment(child/'duel', 'duel', run.manifest, run.clock, collector, branch=True)
                for key, tensor in model.state_dict().items():
                    if not key.startswith('value.'):
                        self.assertTrue(torch.equal(tensor, runner.model.state_dict()[key]), key)
                self.assertNotEqual(runner.model.value[-1].bias.item(), 123.)
                self.assertEqual(runner.optimizer.state_dict()['state'], {})
                self.assertEqual(runner.state['stage'], 'calibration')
                self.assertFalse(runner.state['effective'])
                for key in ('teacher_shards', 'dagger_shards', 'policy_shards', 'snapshots', 'history'):
                    self.assertEqual(runner.state[key], [])
                self.assertNotIn('frozen_bc_anchor', runner.state)
                self.assertEqual(runner.state['counters']['optimizer_steps'], 0)
                self.assertEqual(runner.controller.freeze()['task_id'], TASK_ID)
                self.assertEqual(runner.controller.freeze()['explore'], 0.)
                self.assertEqual(runner.state['initialized_from']['task_id'], LEGACY_TASK)
                before = copy.deepcopy(runner.model.state_dict())
                resumed = FormatExperiment(child/'duel', 'duel', run.manifest, run.clock, collector, resume=True)
                self.assertTrue(all(torch.equal(value, resumed.model.state_dict()[key]) for key,value in before.items()))
                self.assertEqual(resumed.state, runner.state)
            self.assertEqual(sha256(source), original)
            self.assertFalse((child/'duel/last_bc.pt').exists())
            collector.assert_not_called()

    def test_only_weights_initialization_allows_a_parent_format_subset(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            parent = Path(temporary)/'parent'
            config = default_config('cpu') | dict(phase='bc')
            write_json(parent/'manifest.json', dict(config=config, task_id=TASK_ID))
            write_json(parent/'clock.json', {})
            with self.assertRaisesRegex(ValueError, 'keep the parent formats'):
                Experiment(Path(temporary)/'same-task-child', config=config | dict(formats=['duel']),
                           branch_from=parent)
            write_json(parent/'manifest.json', dict(config=config | dict(formats=['duel']), task_id=TASK_ID))
            with self.assertRaisesRegex(ValueError, 'subset of the parent formats'):
                Experiment(Path(temporary)/'invalid-child', config=config | dict(
                    formats=['ffa4'], branch_weights_only=True), branch_from=parent)


if __name__ == '__main__':
    unittest.main()
