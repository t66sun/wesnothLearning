"""A BC restart keeps its compatible supervision and earns its own phase result."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import torch

from learning.__main__ import main
from learning.checkpoints import checkpoint
from learning.common import ROOT, read_json, sha256, write_json
from learning.coordinator import Experiment
from learning.data import split, write_shard
from learning.experiment import FormatExperiment, default_config
from tests.v5 import helpers
from learning.tasks import TASK_ID, FORMULA_ID, reward_config


class BranchRestartBCTests(unittest.TestCase):
    def test_cli_requires_branch_bc_phase_and_new_optimizer(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            parent = Path(tmp)
            config = default_config('cpu')
            write_json(parent/'manifest.json', dict(config=config))
            args = ['run', '--run-dir', str(parent/'child'), '--branch-restart-bc']
            required = [['--branch-from', str(parent)], ['--phase', 'bc'], ['--branch-reset-optimizer']]
            for missing in required:
                flags = sum((items for items in required if items != missing), [])
                with self.subTest(missing=missing), self.assertRaisesRegex(SystemExit, '2'):
                    main(args + flags)
            with mock.patch('learning.coordinator.Experiment') as experiment:
                experiment.return_value.run.return_value = dict(status='stage_complete')
                main(args + sum(required, []))
                kwargs = experiment.call_args.kwargs
                self.assertEqual(kwargs['branch_from'], str(parent))
                self.assertTrue(kwargs['config']['branch_restart_bc'])
                self.assertTrue(kwargs['config']['branch_reset_optimizer'])
                self.assertEqual(kwargs['config']['phase'], 'bc')

    def test_rejects_incompatible_supervision_contracts(self):
        from learning.branch import validate_bc_inputs
        parent = dict(teacher={'teacher_profile': 'v6'}, row_schema=6, batch_contract='scenario-v2',
                      opponents=[dict(sha256='astra')], config=dict(training_max_turns=30))
        validate_bc_inputs(parent, parent)
        for key, other in dict(teacher={}, row_schema=5, batch_contract='legacy',
                               opponents=[dict(sha256='other')], config={}).items():
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'matching'):
                validate_bc_inputs(parent, parent | {key: other})

    def test_child_calibrates_trains_and_rechecks_its_own_gate(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            parent, child = Path(tmp)/'parent', Path(tmp)/'child'
            config = default_config('cpu') | dict(phase='bc', formats=['duel'], epochs=1, human_data=str(parent/'human'))
            config['bc_games']['duel'] = 2
            manifest = dict(config=config, task_id=TASK_ID, opponents=[dict(path='gpt6astra.zip', sha256='astra')],
                            baseline=dict(path='unused'), teacher=dict(teacher_profile='v6'),
                            rules=dict(rules_sha256='fixture'), row_schema=6, batch_contract='scenario-v2')
            write_json(parent/'manifest.json', manifest)
            model = helpers.model(seed=31)
            optimizer = torch.optim.Adam(model.parameters(), lr=.02)
            paths = []
            jobs = []
            for partition in ('train', 'validation'):
                family = next(str(i) for i in range(100) if split(str(i)) == partition)
                row = helpers.synthetic_decision_row(game_id=partition, game_family=family)
                row.update(split_rule='scenario-v2', scenario_family=family, task_id=TASK_ID,
                           reward_config=reward_config(), reward_formula_id=FORMULA_ID)
                path = parent/'duel/data'/(partition+'.jsonl.gz')
                write_shard(path, partition, [row], dict(bots=['astra', 'astra'], faults=[], winner=1,
                                                       task_id=TASK_ID, task_terminal=True))
                paths.append(str(path))
                kind = row['actual']['kind']
                jobs.append(dict(id=partition, meta=dict(phase='teacher'), status='complete',
                                 coverage=dict(total=1, matched=1, kinds={kind:dict(total=1, matched=1)})))
            (parent/'duel/jobs.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in jobs))
            parent_state = dict(format='duel', clock={'old': 1}, stage='bc_complete', phase='bc', version=37,
                                batch=37, effective=True, pending_train=None, pending_validation=None,
                                teacher_shards=paths, dagger_shards=[], snapshots=['parent snapshot'],
                                counters=dict(optimizer_steps=1824), history=[dict(method='bc', updates=1824)],
                                reward_controller=dict(games=48), bc_plateau=10, phase_deadline=1)
            write_json(parent/'clock.json', parent_state['clock'])
            identity = object.__new__(FormatExperiment)
            identity.config = config
            parent_checkpoint = parent/'duel/latest.pt'
            checkpoint(parent_checkpoint, model, optimizer, runner=parent_state,
                       manifest_sha256=sha256(parent/'manifest.json'), **identity.identity())
            parent_hash = sha256(parent_checkpoint)
            def freeze_fixture(directory, opponents, wesnoth, config):
                frozen = manifest | dict(config=config)
                write_json(directory/'manifest.json', frozen)
                return frozen, []
            with mock.patch('learning.coordinator.freeze', side_effect=freeze_fixture):
                experiment = Experiment(child, config=config | dict(branch_reset_optimizer=True, branch_restart_bc=True),
                                        branch_from=parent)
            self.assertTrue(read_json(child/'branch.json')['restart_bc'])
            clock = experiment.clock
            collector = mock.Mock(side_effect=AssertionError('parent corpus already meets the target'))
            with mock.patch.object(FormatExperiment, 'ensure_export', return_value='unused'):
                runner = FormatExperiment(child/'duel', 'duel', experiment.manifest, clock, collector, branch=True)
                self.assertTrue(all(torch.equal(v, runner.model.state_dict()[k]) for k,v in model.state_dict().items()))
                self.assertEqual(runner.optimizer.param_groups[0]['lr'], config['learning_rate'])
                self.assertEqual(runner.state['teacher_shards'], paths)
                self.assertEqual(runner.state['stage'], 'calibration')
                self.assertFalse(runner.state['effective'])
                self.assertEqual(runner.state['snapshots'], [])
                self.assertEqual(runner.state['counters']['optimizer_steps'], 0)
                self.assertEqual(runner.state['history'], [])
                self.assertEqual(runner.state['reward_controller']['games'], 0)
                self.assertNotIn('phase_deadline', runner.state)
                # End this unit run at its first committed child update.
                with mock.patch.object(runner, 'update_deadline',
                                       side_effect=lambda: clock['deadline'] if runner.state['version'] == 0 else 0):
                    runner.run()
                self.assertEqual(read_json(child/'duel/controls.json')['calibration'], 'single fixed Astra')
                self.assertEqual(runner.state['stage'], 'bc_complete')
                self.assertEqual(runner.state['batch'], 1)
                self.assertEqual(runner.state['counters']['optimizer_steps'], 1)
                self.assertEqual(runner.state['history'][0]['reads']['bc']['rows'], 1)
                gate = read_json(child/'duel/bc_gate.json')
                self.assertEqual(gate['corpus'], dict(games=2, required=2, passed=True))
                self.assertEqual(gate['imitation']['formats']['duel']['samples'], 1)
                self.assertFalse(gate['passed'])
                self.assertFalse(runner.state['effective'])
                resumed = FormatExperiment(child/'duel', 'duel', experiment.manifest, clock, collector, resume=True)
                self.assertEqual(resumed.state, runner.state)
                self.assertEqual(sha256(parent_checkpoint), parent_hash)
                collector.assert_not_called()
