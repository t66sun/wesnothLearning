"""Frozen teacher selection: no games, sampling or optimizer work."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from learning.teachers import build
from learning.teachers.registry import (
    DEFAULT_SET, ROLES, SELECTED_SHA256, describe, execution_identity,
    freeze_set, module_sources, role, validate_set, verify_set, require_runtime,
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
