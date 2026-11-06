"""Real runner, complete checkpoint, branch, export and resume boundaries for BC KL."""
import copy
from dataclasses import replace
import random
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import torch

from learning import ppo
from learning.bc_anchor import ensure_anchor, weights_sha256
from learning.common import read_json, sha256, write_json
from learning.data import write_shard
from learning.experiment import FormatExperiment, default_config
from learning.export import load_model
from learning.features import schema
from learning.model import ARCHITECTURE
from learning.rowpack import ROW_SCHEMA
from learning.teachers import lineage
from tests.v5 import helpers
from tests.v5.test_ppo_plan import _records


def make_runner(root, mode='frozen_bc_kl', *, resume=False, branch=False, manifest=None, clock=None):
    if manifest is None:
        config = default_config('cpu') | dict(ppo_aux_target=mode, seed=41, epochs=2, minibatch=2,
                                             formats=['duel'], phase='bc', reward_mode='fixed',
                                             human_data=str(root/'human'))
        manifest = dict(config=config, features=schema(), architecture=ARCHITECTURE, row_schema=ROW_SCHEMA,
                        teacher=lineage(), opponents=[dict(path='gpt6astra.zip', sha256='fixture')],
                        baseline=dict(path='unused'))
        write_json(root/'manifest.json', manifest)
    if clock is None:
        clock = dict(started=time.time(), update_deadline=time.time()+3600, deadline=time.time()+7200)
        write_json(root/'clock.json', clock)
    collector = Mock(side_effect=AssertionError('this fixture must not collect games'))
    return FormatExperiment(root/'duel', 'duel', manifest, clock, collector, resume=resume, branch=branch)


def complete_bc(runner):
    runner.state.update(stage='bc_complete', phase='bc', effective=True, version=7, batch=7,
                        history=[dict(method='bc', updates=1)], pending_train=None)
    runner.save()
    runner._write_checkpoint(runner.directory/'last_bc.pt')


def schedule_rows(runner, *, delta=0.):
    paths = []
    for game in ('b', 'c', 'd', 'e', 'g'):
        rows = _records([(game, 2, delta)])
        for row in rows:
            row.update(split_rule='scenario-v2', scenario_family=game, policy_sha256='fixture-policy')
        path = runner.directory/'data'/(game+'.jsonl.gz')
        write_shard(path, game, rows, dict(bots=['student', 'astra'], faults=[], winner=1))
        paths.append(str(path))
    runner.state.update(policy_shards=paths, stage='ppo', phase='ppo',
        pending_train=dict(method='ppo', paths=paths, cursor=dict(epoch=0, step=0),
                           reward_config=runner.controller.freeze()))
    return paths


class FrozenBcAnchorTests(unittest.TestCase):
    def test_cli_defaults_and_old_execution_contract_stay_historical(self):
        from learning.__main__ import main, parser, run_config
        self.assertEqual(run_config(parser().parse_args(['run']))['ppo_aux_target'], 'historical_action')
        self.assertEqual(run_config(parser().parse_args(['run', '--ppo-aux-target', 'frozen_bc_kl']))['ppo_aux_target'], 'frozen_bc_kl')
        with helpers.temporary_directory() as root:
            runner = make_runner(root, 'historical_action')
            saved = torch.load(runner.directory/'latest.pt', weights_only=False)
            saved['execution'].pop('ppo_aux_target')
            torch.save(saved, runner.directory/'latest.pt')
            manifest = copy.deepcopy(runner.manifest)
            manifest['config'].pop('ppo_aux_target')
            write_json(root/'manifest.json', manifest)
            saved['manifest_sha256'] = sha256(root/'manifest.json')
            torch.save(saved, runner.directory/'latest.pt')
            resumed = make_runner(root, resume=True, manifest=manifest, clock=runner.clock)
            self.assertIsNone(ensure_anchor(resumed))
            self.assertFalse((runner.directory/'frozen_bc.pt').exists())
            with patch('builtins.print'), self.assertRaises(SystemExit):
                main(['run', '--resume', str(root), '--ppo-aux-target', 'frozen_bc_kl'])

    def test_pin_is_complete_immutable_and_export_is_loadable(self):
        with helpers.temporary_directory() as root:
            runner = make_runner(root)
            complete_bc(runner)
            manifest_before = (root/'manifest.json').read_bytes()
            rng = torch.get_rng_state().clone()
            anchor = ensure_anchor(runner)
            torch.testing.assert_close(torch.get_rng_state(), rng)
            identity = runner.state['frozen_bc_anchor']
            self.assertEqual(identity['checkpoint_sha256'], sha256(runner.directory/'last_bc.pt'))
            self.assertEqual(identity['weights_sha256'], ppo._digest(runner.model))
            self.assertEqual(identity['teacher_initialization'], runner.manifest['teacher'])
            self.assertEqual(identity['features'], schema())
            self.assertEqual(identity['architecture'], ARCHITECTURE)
            self.assertEqual(identity['row_schema'], ROW_SCHEMA)
            self.assertEqual(identity['format'], 'duel')
            self.assertTrue(all(not p.requires_grad and p.grad is None for p in anchor.parameters()))
            self.assertEqual((root/'manifest.json').read_bytes(), manifest_before)
            export_path = Path(runner.ensure_export(runner.model, 'bc-test', 'FrozenBcFixture'))
            tensor = export_path.parent/'model.pt'
            exported, _ = load_model(tensor, 'duel')
            self.assertEqual(ppo._digest(exported), identity['weights_sha256'])
            from learning.lite_policy import FrozenPolicies
            consumer = FrozenPolicies(dict(bots=[str(export_path), 'astra'], seed=3, format='duel'))
            choice = consumer.choose(_records([('b', 1, 0.)])[0], 1)
            self.assertGreaterEqual(choice['choice'], 0)
            # A later mutable role must never retarget the fixed copy.
            with torch.no_grad():
                next(runner.model.parameters()).add_(1.)
            runner._write_checkpoint(runner.directory/'last_bc.pt')
            self.assertEqual(ppo._digest(ensure_anchor(runner)), identity['weights_sha256'])
            self.assertEqual(sha256(runner.directory/'frozen_bc.pt'), identity['checkpoint_sha256'])

    def test_learn_pins_before_export_or_collection_and_force_cannot_invent_bc(self):
        with helpers.temporary_directory() as root:
            runner = make_runner(root)
            runner.state.update(phase='ppo', forced_ppo={'reason': 'fixture'})
            before = ppo._digest(runner.model)
            with self.assertRaisesRegex(ValueError, 'qualifying last_bc'):
                runner.learn()
            runner.collector.assert_not_called()
            self.assertEqual(ppo._digest(runner.model), before)
            complete_bc(runner)
            runner.state['phase'] = 'ppo'
            def exported(*args, **kwargs):
                self.assertIn('frozen_bc_anchor', runner.state)
                self.assertTrue((runner.directory/'frozen_bc.pt').is_file())
                raise LookupError('boundary observed')
            with patch.object(runner, 'ensure_export', side_effect=exported), self.assertRaisesRegex(LookupError, 'boundary observed'):
                runner.learn()

    def test_unqualified_or_pending_bc_is_rejected(self):
        with helpers.temporary_directory() as root:
            runner = make_runner(root)
            complete_bc(runner)
            original = torch.load(runner.directory/'last_bc.pt', weights_only=False)
            for change in ({'effective': False}, {'pending_train': {'method': 'bc'}},
                           {'history': [{'method': 'ppo', 'updates': 1}]}):
                invalid = copy.deepcopy(original)
                invalid['runner'].update(change)
                torch.save(invalid, runner.directory/'last_bc.pt')
                with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'qualifying BC'):
                    ensure_anchor(runner)

    def test_real_runner_compares_targets_and_uses_pending_coefficient(self):
        with helpers.temporary_directory() as root:
            results = {}
            for mode in ('historical_action', 'frozen_bc_kl'):
                runner = make_runner(root/mode, mode)
                complete_bc(runner)
                if mode == 'frozen_bc_kl':
                    ensure_anchor(runner)
                schedule_rows(runner)
                runner.state['pending_train']['reward_config']['bc_aux'] = .1
                # A controller change cannot alter the coefficient of this batch.
                runner.controller.config = replace(runner.controller.config, bc_aux=.2)
                random.seed(13)
                self.assertTrue(runner.finish_train())
                result = runner.state['history'][-1]
                self.assertEqual(result['bc_aux'], .1)
                self.assertEqual(result['ppo_aux_target'], mode)
                self.assertEqual(result['rehearsal_sources'], [dict(source='policy', teacher_impl=None, sha256='fixture-policy')])
                self.assertEqual(result['committed_decisions'], 20)
                self.assertEqual(result['repeated_targets'], 0)
                results[mode] = ppo._digest(runner.model)
                runner.collector.assert_not_called()
            self.assertNotEqual(results['historical_action'], results['frozen_bc_kl'])

    def test_interrupted_resume_matches_uninterrupted_with_real_shards(self):
        with helpers.temporary_directory() as root:
            complete = make_runner(root/'complete')
            complete_bc(complete)
            ensure_anchor(complete)
            schedule_rows(complete)
            random.seed(13)
            self.assertTrue(complete.finish_train())
            runner = make_runner(root/'interrupted')
            complete_bc(runner)
            ensure_anchor(runner)
            schedule_rows(runner)
            random.seed(13)
            original_step = runner.optimizer.step
            stepped = [False]
            def step(*args, **kwargs):
                result = original_step(*args, **kwargs)
                stepped[0] = True
                return result
            with patch.object(runner.optimizer, 'step', side_effect=step), \
                 patch.object(runner, 'update_deadline', return_value=1.), \
                 patch('learning.ppo.time.time', side_effect=lambda: 2. if stepped[0] else 0.):
                self.assertFalse(runner.finish_train())
            saved = torch.load(runner.directory/'latest.pt', weights_only=False)
            self.assertEqual(saved['runner']['pending_train']['cursor']['updates'], 1)
            self.assertEqual(saved['runner']['pending_train']['auxiliary_target']['anchor_sha256'],
                             saved['runner']['frozen_bc_anchor']['checkpoint_sha256'])
            resumed = make_runner(root/'interrupted', resume=True, manifest=runner.manifest, clock=runner.clock)
            torch.testing.assert_close(torch.get_rng_state(), saved['torch_rng'])
            self.assertEqual(random.getstate(), saved['python_rng'])
            self.assertTrue(resumed.finish_train())
            self.assertEqual(ppo._digest(resumed.model), ppo._digest(complete.model))
            self.assertEqual(resumed.state['counters'], complete.state['counters'])
            self.assertEqual(resumed.state['frozen_bc_anchor'], runner.state['frozen_bc_anchor'])
            self.assertTrue(all(p.grad is None for p in resumed._bc_anchor.parameters()))
            self.assertEqual(weights_sha256(resumed._bc_anchor.state_dict()),
                             resumed.state['frozen_bc_anchor']['weights_sha256'])

    def test_missing_or_replaced_anchor_fails_before_update_and_on_resume(self):
        with helpers.temporary_directory() as root:
            runner = make_runner(root)
            complete_bc(runner)
            ensure_anchor(runner)
            schedule_rows(runner)
            runner.save()
            path = runner.directory/'frozen_bc.pt'
            contents = path.read_bytes()
            before = ppo._digest(runner.model)
            for replacement, error in ((None, 'anchor is missing'), (b'not the endpoint', 'checkpoint hash differs')):
                if replacement is None:
                    path.unlink()
                else:
                    path.write_bytes(replacement)
                with self.subTest(replacement=replacement), self.assertRaisesRegex(ValueError, error):
                    runner.finish_train()
                self.assertEqual(ppo._digest(runner.model), before)
                with self.assertRaisesRegex(ValueError, error):
                    make_runner(root, resume=True, manifest=runner.manifest, clock=runner.clock)
                path.write_bytes(contents)
            runner.state['frozen_bc_anchor']['weights_sha256'] = 'wrong'
            with self.assertRaisesRegex(ValueError, 'identity differs'):
                runner.finish_train()

    def test_same_task_bc_parent_branches_share_the_pinned_endpoint(self):
        from learning.branch import prepare
        with helpers.temporary_directory() as root:
            parent = make_runner(root/'parent', 'historical_action')
            complete_bc(parent)
            parent_hash = sha256(parent.directory/'last_bc.pt')
            initial = ppo._digest(parent.model)
            for mode in ('historical_action', 'frozen_bc_kl'):
                child_root = root/mode
                manifest = copy.deepcopy(parent.manifest)
                manifest['config'].update(ppo_aux_target=mode, seed=53)
                write_json(child_root/'manifest.json', manifest)
                clock = dict(parent.clock, started=time.time())
                info = prepare(root/'parent', child_root, ['duel'], seed=53, clock=clock)
                info.update(parent=str(root/'parent'), parent_manifest_sha256=sha256(root/'parent/manifest.json'),
                            parent_clock=parent.clock)
                write_json(child_root/'branch.json', info)
                child = make_runner(child_root, manifest=manifest, clock=clock, branch=True)
                self.assertEqual(ppo._digest(child.model), initial)
                self.assertEqual(info['checkpoints']['duel']['bc_endpoint']['sha256'], parent_hash)
                anchor = ensure_anchor(child)
                if mode == 'frozen_bc_kl':
                    self.assertEqual(ppo._digest(anchor), initial)
                    self.assertEqual(child.state['frozen_bc_anchor']['checkpoint_sha256'], parent_hash)
                    self.assertEqual(child.state['frozen_bc_anchor']['initialization_lineage'][-1]['parent'], str(root/'parent'))
                schedule_rows(child)
                self.assertTrue(child.finish_train())
                resumed = make_runner(child_root, resume=True, manifest=manifest, clock=clock)
                self.assertEqual(ppo._digest(resumed.model), ppo._digest(child.model))
            self.assertEqual(sha256(parent.directory/'last_bc.pt'), parent_hash)

    def test_bc_restart_does_not_inherit_the_old_anchor(self):
        from learning.branch import prepare
        with helpers.temporary_directory() as root:
            parent = make_runner(root/'parent')
            complete_bc(parent)
            ensure_anchor(parent)
            child = root/'child'
            prepare(root/'parent', child, ['duel'], seed=5, restart_bc=True)
            self.assertTrue((child/'duel/latest.pt').is_file())
            self.assertFalse((child/'duel/frozen_bc.pt').exists())
            self.assertFalse((child/'duel/last_bc.pt').exists())

    def test_resume_rejects_missing_pin_or_changed_mode_and_identity(self):
        with helpers.temporary_directory() as root:
            runner = make_runner(root)
            complete_bc(runner)
            ensure_anchor(runner)
            schedule_rows(runner)
            runner.save()
            original = torch.load(runner.directory/'latest.pt', weights_only=False)
            changes = [('pin', 'identity is missing'), ('mode', 'auxiliary target differs'),
                       ('format', 'identity differs')]
            for change, error in changes:
                saved = copy.deepcopy(original)
                if change == 'pin':
                    saved['runner'].pop('frozen_bc_anchor')
                elif change == 'mode':
                    saved['execution']['ppo_aux_target'] = 'historical_action'
                else:
                    saved['runner']['frozen_bc_anchor']['format'] = 'team2v2'
                torch.save(saved, runner.directory/'latest.pt')
                with self.subTest(change=change), self.assertRaisesRegex(ValueError, error):
                    make_runner(root, resume=True, manifest=runner.manifest, clock=runner.clock)


if __name__ == '__main__':
    unittest.main()
