"""Frozen teacher selection: no games, sampling or optimizer work."""
import copy
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from learning.teachers import build
from learning.teachers.registry import (
    DEFAULT_SET, ROLES, SELECTED_SHA256, describe, execution_identity,
    freeze_set, module_sources, role, validate_set, verify_set, require_runtime, require_same_teachers,
)


class TeacherSetTests(unittest.TestCase):
    def test_mixed_roles_pin_original_strategies(self):
        with tempfile.TemporaryDirectory() as temporary:
            contract = freeze_set(Path(temporary)/'teachers', 'mixed-20261107')
            expected = {'duel': 'clean_fortified_pruned', 'ffa4': 'maintained_astra',
                        'team2v2': 'clean_fortified_pvs'}
            for fmt, strategy in expected.items():
                roles = contract['formats'][fmt]
                self.assertEqual(set(roles), set(ROLES))
                for spec in roles.values():
                    self.assertEqual(spec['strategy'], strategy)
                    self.assertEqual(spec['format'], fmt)
                    self.assertEqual(spec['timeout'], 1 if fmt == 'ffa4' else 2)
                    self.assertEqual(spec['first_timeout'], 10 if fmt == 'ffa4' else 20)
                    if fmt != 'ffa4':
                        self.assertEqual(spec['package_sha256'], SELECTED_SHA256)
                        self.assertEqual(spec['parameters']['planning_ms'], 1000)
                        self.assertEqual(spec['parameters']['tactical_ms'], 700)
            verify_set(contract)

    def test_astra_set_and_build_are_reproducible(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            a = freeze_set(root/'first', 'astra')
            b = freeze_set(root/'second', 'astra')
            for fmt in a['formats']:
                first = a['formats'][fmt]['supervision']
                second = b['formats'][fmt]['supervision']
                self.assertEqual(first['teacher'], 'gpt6astra')
                self.assertEqual(first['package_sha256'], second['package_sha256'])
                self.assertEqual(first['source_sha256'], second['source_sha256'])
            verify_set(a)

    def test_package_bytes_ignore_source_extraction_times(self):
        from learning.teachers import SOURCE
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outputs = []
            for index, timestamp in enumerate((946684800, 1704067200)):
                source = root/str(index)
                shutil.copytree(SOURCE, source)
                for path in source.rglob('*'):
                    if path.is_file(): os.utime(path, (timestamp, timestamp))
                with patch('learning.teachers.SOURCE', source):
                    outputs.append(build(root/f'{index}.zip').read_bytes())
            self.assertEqual(*outputs)

    def test_same_named_set_cannot_inherit_different_teacher_supervision(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = {'teacher_set': freeze_set(root/'parent', 'mixed-20261107')}
            child = {'teacher_set': freeze_set(root/'child', 'mixed-20261107')}
            require_same_teachers(parent, child, ('duel', 'ffa4', 'team2v2'))
            for key in ('source_sha256', 'package_sha256', 'parameters'):
                altered = copy.deepcopy(parent)
                altered['teacher_set']['formats']['ffa4']['supervision'][key] = 'different'
                with self.assertRaisesRegex(ValueError, 'weights-only'):
                    require_same_teachers(altered, child, ('ffa4',))

    def test_package_bytes_ignore_zip_platform_defaults(self):
        import zipfile
        from learning.teachers import archive_bytes
        original = zipfile.ZipInfo
        def platform(system):
            class Entry(original):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, **kwargs)
                    self.create_system = system
            return Entry
        outputs = []
        for system in (0, 3):
            with patch('learning.teachers.zipfile.ZipInfo', platform(system)):
                outputs.append(archive_bytes())
        self.assertEqual(*outputs)

    def test_branch_rejects_same_set_with_changed_source_before_copying_state(self):
        from learning.common import write_json
        from learning.coordinator import Experiment
        from learning.experiment import default_config
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent, child = root/'parent', root/'child'
            parent.mkdir()
            config = default_config('cpu')
            contract = freeze_set(root/'teachers', 'astra')
            original = dict(config=config, task_id=config['task_id'], teacher_set=contract,
                            rules={'identity': 'same'}, baseline={'path': 'unused'})
            write_json(parent/'manifest.json', original)
            write_json(parent/'clock.json', {})
            changed = copy.deepcopy(original)
            changed['teacher_set']['formats']['duel']['supervision']['source_sha256'] = 'changed'
            with patch('learning.coordinator.output_path', side_effect=Path), \
                 patch('learning.coordinator.freeze', return_value=(changed, [])), \
                 patch('learning.coordinator.prepare_branch') as inherit:
                with self.assertRaisesRegex(ValueError, 'teacher execution identity changed'):
                    Experiment(child, config=config | {'branch_reset_optimizer': True}, branch_from=parent)
                inherit.assert_not_called()

    def test_role_and_module_loading_preserve_namespaces(self):
        with tempfile.TemporaryDirectory() as temporary:
            contract = freeze_set(Path(temporary)/'teachers', 'mixed-20261107')
            manifest = {'teacher_set': contract}
            spec = role(manifest, 'duel')
            modules = module_sources(spec)
            for fmt in ('duel', 'ffa4', 'team2v2'):
                self.assertIn(f'~add-ons/selected_teacher/lua/{fmt}/bot.lua', modules)
            spec['parameters']['width'] = 999
            self.assertEqual(role(manifest, 'duel')['parameters']['width'], 6)
            self.assertIsNone(role({}, 'duel'))

    def test_corrupt_package_descriptor_and_role_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            contract = freeze_set(Path(temporary)/'teachers', 'mixed-20261107')
            for change in ('budget', 'source', 'role'):
                altered = copy.deepcopy(contract)
                spec = altered['formats']['duel']['supervision']
                if change == 'budget': spec['timeout'] = 100
                if change == 'source': spec['source_sha256'] = 'wrong'
                if change == 'role': del altered['formats']['duel']['evaluation']
                with self.assertRaises(ValueError): verify_set(altered)
            spec = contract['formats']['duel']['supervision']
            with Path(spec['package']).open('ab') as stream: stream.write(b'changed')
            with self.assertRaisesRegex(ValueError, 'frozen teacher package'):
                module_sources(spec)
            with self.assertRaisesRegex(ValueError, 'frozen delivery'):
                describe(spec['package'], 'duel')

    def test_backend_and_strategy_identities_are_distinct(self):
        with tempfile.TemporaryDirectory() as temporary:
            contract = freeze_set(Path(temporary)/'teachers', 'mixed-20261107')
            duel = contract['formats']['duel']['supervision']
            team = contract['formats']['team2v2']['supervision']
            lite = execution_identity(duel, 'lite')
            native = execution_identity(duel, 'native')
            self.assertNotEqual(lite['teacher_adapter_sha256'], native['teacher_adapter_sha256'])
            self.assertEqual(lite['teacher_source_sha256'], native['teacher_source_sha256'])
            self.assertNotEqual(lite['teacher_source_sha256'], execution_identity(team, 'lite')['teacher_source_sha256'])
            self.assertEqual(lite['teacher_contract'], 1)

    def test_cli_selects_set_and_rejects_resume_override(self):
        from learning.__main__ import parser, main
        self.assertEqual(parser().parse_args(['run', '--teacher-set', 'mixed-20261107']).teacher_set,
                         'mixed-20261107')
        with patch('learning.__main__.bind_rules'), patch('learning.coordinator.Experiment') as start:
            with self.assertRaises(SystemExit):
                main(['run', '--resume', 'unused', '--teacher-set', 'astra'])
            start.assert_not_called()
        with self.assertRaises(ValueError): validate_set('unknown')

    def test_incomplete_runtime_cannot_silently_run_astra(self):
        require_runtime('astra')
        with self.assertRaisesRegex(ValueError, 'integration is pending'):
            require_runtime('mixed-20261107')


if __name__ == '__main__':
    unittest.main()
