import copy
import json
import random
import unittest
from pathlib import Path
from unittest import mock

import torch

from learning.branch import adopt, prepare
from learning.checkpoints import (CHECKPOINT_VERSION, checkpoint, inherited_checkpoint, resume_pins,
                                     validate_checkpoint)
from learning.data import split
from learning.experiment import validate_resume
from learning.ppo import PLAN_VERSION
from learning.sequences import attach_histories
from learning.updates import rollout_identity
from tests.v5 import helpers


class CheckpointContractTests(unittest.TestCase):
    def test_failed_atomic_save_leaves_the_previous_checkpoint(self):
        with helpers.temporary_directory() as directory:
            model = helpers.model(seed=3)
            optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
            path = Path(directory) / 'latest.pt'
            checkpoint(path, model, optimizer, runner=dict(version=1), execution=dict(plan_version=PLAN_VERSION))
            before = path.read_bytes()
            with mock.patch('learning.checkpoints.torch.save', side_effect=RuntimeError('disk full')):
                with self.assertRaises(RuntimeError):
                    checkpoint(path, model, optimizer, runner=dict(version=2))
            self.assertEqual(path.read_bytes(), before)
            state = torch.load(path, weights_only=False)
            self.assertEqual(state['runner']['version'], 1)
            self.assertEqual(state['checkpoint_version'], CHECKPOINT_VERSION)
            self.assertEqual(state['execution'], {'version': 2, 'plan_version': PLAN_VERSION})

    def test_incompatible_identity_is_rejected_before_loading_weights(self):
        with helpers.temporary_directory() as directory:
            model = helpers.model(seed=3)
            optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
            path = Path(directory) / 'latest.pt'
            checkpoint(path, model, optimizer, manifest_sha256='parent')
            state = torch.load(path, weights_only=False)
            validate_checkpoint(state, 'duel', 'parent')
            with self.assertRaisesRegex(ValueError, 'manifest changed'):
                validate_checkpoint(state, 'duel', 'other')
            with self.assertRaisesRegex(ValueError, 'different format'):
                validate_checkpoint(state, 'ffa4')
            state['execution']['version'] = 99
            with self.assertRaisesRegex(ValueError, 'execution format'):
                validate_checkpoint(state)
            state['execution']['version'] = 2
            state['checkpoint_version'] = 99
            with self.assertRaisesRegex(ValueError, 'newer execution'):
                validate_checkpoint(state)

    def test_resume_accepts_the_parent_pin_of_a_branch(self):
        with helpers.temporary_directory() as directory:
            run = directory / 'run'
            fmt_dir = run / 'duel'
            fmt_dir.mkdir(parents=True)
            (run / 'manifest.json').write_text('{"child": 1}')
            model = helpers.model(seed=5)
            optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
            checkpoint(fmt_dir / 'latest.pt', model, optimizer, manifest_sha256='parent')
            state = torch.load(fmt_dir / 'latest.pt', weights_only=False)
            with self.assertRaisesRegex(ValueError, 'manifest changed'):
                validate_resume(state, 'duel', fmt_dir)
            (run / 'branch.json').write_text(json.dumps({'parent_manifest_sha256': 'parent'}))
            self.assertIn('parent', resume_pins(fmt_dir))
            validate_resume(state, 'duel', fmt_dir)
            (run / 'branch.json').write_text(json.dumps({'parent_manifest_sha256': 'other'}))
            with self.assertRaisesRegex(ValueError, 'manifest changed'):
                validate_resume(state, 'duel', fmt_dir)

    def test_inherited_branch_checkpoint_is_recognised_by_its_parent_pin(self):
        with helpers.temporary_directory() as directory:
            run = directory / 'run'
            fmt_dir = run / 'duel'
            fmt_dir.mkdir(parents=True)
            (run / 'manifest.json').write_text('{"child": 1}')
            inherited_state = dict(manifest_sha256='parent', runner=dict(clock={'parent': 1}))
            own_state = dict(manifest_sha256='child', runner=dict(clock={'child': 2}))
            self.assertIsNone(inherited_checkpoint(fmt_dir, inherited_state))
            (run / 'branch.json').write_text(json.dumps({'parent_manifest_sha256': 'parent',
                                                         'parent_clock': {'parent': 1}}))
            self.assertEqual(inherited_checkpoint(fmt_dir, inherited_state)['parent_manifest_sha256'], 'parent')
            self.assertIsNone(inherited_checkpoint(fmt_dir, own_state))

    def test_rollout_identity_covers_targets_and_provenance(self):
        rows = []
        for game_id, turns in (('b', 2), ('c', 3)):
            part = helpers.sequence_rows(turns=turns, decisions_per_turn=1, source='policy',
                                         game_id=game_id, game_family=game_id)
            for row in part:
                row['split'] = split(game_id)
            rows += part
        rows = attach_histories(rows)
        self.assertEqual(rollout_identity(rows), rollout_identity(list(reversed(rows))))
        rows[0]['version'] = 'different'
        self.assertNotEqual(rollout_identity(rows), rollout_identity(rows[1:]))

    def test_branch_copies_and_records_parent_without_editing_it(self):
        with helpers.temporary_directory() as directory:
            source = directory / 'source'
            destination = directory / 'child'
            model = helpers.model(seed=4)
            optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
            runner = dict(format='duel', version=7, pending_train=dict(paths=['x'], method='ppo'),
                          pending_validation='bc', stage='ppo', phase='auto', clock={'old': 1})
            source_checkpoint = source / 'duel' / 'latest.pt'
            checkpoint(source_checkpoint, model, optimizer, runner=runner,
                       execution=dict(plan_version=PLAN_VERSION), manifest_sha256='parent')
            before = source_checkpoint.read_bytes()
            info = prepare(source, destination, ['duel'], seed=123, reset_optimizer=True, clock={'old': 1})
            info.update(parent=str(source), parent_manifest_sha256='parent', parent_clock={'old': 1})
            self.assertEqual(source_checkpoint.read_bytes(), before)
            self.assertNotEqual((destination / 'duel' / 'latest.pt').read_bytes(), b'')
            self.assertEqual(info['seed'], 123)
            state = adopt(runner, info, {'started': 2}, 'bc')
            self.assertEqual(state['clock'], {'started': 2})
            self.assertEqual(state['stage'], 'bc')
            self.assertEqual(state['phase'], 'bc')
            self.assertIsNone(state['pending_train'])
            self.assertIsNone(state['pending_validation'])
            self.assertEqual(state['lineage'][-1]['parent'], str(source))
            self.assertEqual(state['lineage'][-1]['seed'], 123)
            self.assertEqual(state['lineage'][-1]['optimizer'], 'reset')
            self.assertEqual(runner['stage'], 'ppo')
            self.assertIsNotNone(runner['pending_train'])
            self.assertEqual(len(runner), 7)


if __name__ == '__main__':
    unittest.main()