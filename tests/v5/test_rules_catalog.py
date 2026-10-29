"""Integrity checks for a captured native 1.18.8 rules catalog."""
from __future__ import annotations

import hashlib
import json
import os
import runpy
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from learning import rules_catalog

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / 'data/rules/1.18.8'


@unittest.skipUnless((DIR / 'catalog.json').is_file(), 'no captured 1.18.8 catalog')
class CapturedRulesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads((DIR / 'catalog.json').read_text(encoding='utf-8'))
        cls.rules = json.loads((DIR / 'rules.json').read_text(encoding='utf-8'))
        cls.coverage = json.loads((DIR / 'coverage.json').read_text(encoding='utf-8'))

    def test_catalog_hash_and_source_provenance(self):
        digest = hashlib.sha256((DIR / 'rules.json').read_bytes()).hexdigest()
        self.assertEqual(self.catalog['rules_file_sha256'], digest)
        self.assertEqual(self.catalog['source_hash'], self.rules['source_hash'])
        self.assertEqual(self.rules['source_version'], '1.18.8')

    def test_acceptance_flags_are_not_claimed_by_capture(self):
        self.assertFalse(self.catalog['native_accepted'])
        self.assertFalse(self.catalog['performance_accepted'])
        self.assertFalse(self.catalog['complete'])
        self.assertTrue(self.catalog.get('scope_inventory_complete'))
        self.assertEqual(self.catalog.get('missing_scopes'), [])
        with self.assertRaisesRegex(RuntimeError, 'acceptance is pending'):
            rules_catalog.load(DIR, acceptance_scope='full')

    def test_shipped_maps_use_captured_terrain_codes(self):
        import glob
        missing = {}
        for filename in glob.glob(str(ROOT / 'vendor/arena/maps/*.json')):
            board = json.loads(Path(filename).read_text(encoding='utf-8'))
            codes = {code for row in board['terrain'] for code in row}
            absent = sorted(code for code in codes if code not in self.rules['terrains'])
            if absent:
                missing[Path(filename).name] = absent
        self.assertEqual(missing, {})

    def test_unit_and_terrain_closure(self):
        units = self.rules['units']
        terrains = self.rules['terrains']
        self.assertGreater(len(units), 0)
        self.assertGreater(len(terrains), 0)
        for unit_id, unit in units.items():
            self.assertEqual(unit['id'], unit_id)
            self.assertEqual(set(unit['movement']), set(terrains))
            self.assertEqual(set(unit['defense']), set(terrains))
            for target in unit['advances_to']:
                self.assertIn(target, units)
            for weapon in unit['weapons']:
                if weapon.get('plague_type'):
                    self.assertIn(weapon['plague_type'], units)
        for cover in self.coverage.values():
            self.assertIn(cover['status'], ('approximate', 'exact', 'unsupported_script'))


class CatalogSummaryTests(unittest.TestCase):
    def test_runtime_summary_avoids_the_capture_catalog_and_detects_stale_rules(self):
        summary_path = DIR / rules_catalog.SUMMARY
        if not summary_path.is_file():
            self.skipTest('no runtime catalog summary')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copyfile(DIR / 'rules.json', root / 'rules.json')
            shutil.copyfile(summary_path, root / rules_catalog.SUMMARY)
            (root / 'catalog.json').write_text('{broken audit payload', encoding='utf-8')
            loaded = rules_catalog.load(root, require_accepted=False)
            self.assertEqual(loaded['rules_version'], json.loads(summary_path.read_text())['rules_version'])
            self.assertGreater(loaded['unit_count'], 0)
            with (root / 'rules.json').open('ab') as stream:
                stream.write(b'\n')
            with self.assertRaisesRegex(ValueError, 'frozen catalog hash'):
                rules_catalog.load(root, require_accepted=False)


class TrainingReadinessTests(unittest.TestCase):
    def package(self, root, *, unsupported=False, missing=False):
        profile = runpy.run_path(str(ROOT / 'vendor/arena/params.py'))
        seeds = set(profile['LEADERS'])
        for recruits in profile['RECRUITS']:
            seeds.update(recruits.split(','))
        units = {name: dict(abilities=[], weapons=[], advances_to=[], unsupported=[])
                 for name in seeds}
        units[profile['LEADERS'][0]]['advances_to'] = ['Fixture advancement']
        if not missing:
            units['Fixture advancement'] = dict(abilities=[], weapons=[], advances_to=[],
                                               unsupported=['scripted_type_event'] if unsupported else [])
        # Peripheral scripts remain in the frozen package without blocking training.
        units['Campaign only'] = dict(abilities=[], weapons=[], advances_to=[],
                                      unsupported=['scripted_type_event'])
        rules = dict(source_version='1.18.8', source_hash='fixture', units=units)
        raw = json.dumps(rules).encode()
        (root / 'rules.json').write_bytes(raw)
        summary = dict(summary_version=1, source_hash='fixture',
                       rules_file_sha256=hashlib.sha256(raw).hexdigest())
        (root / rules_catalog.SUMMARY).write_text(json.dumps(summary), encoding='utf-8')
        coverage = {name: dict(status='approximate') for name in units}
        (root / 'coverage.json').write_text(json.dumps(coverage), encoding='utf-8')
        (root / 'catalog.json').write_text('{broken audit payload', encoding='utf-8')
        return seeds

    def test_default_load_checks_training_closure_without_reading_full_catalog(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            seeds = self.package(root)
            metadata = rules_catalog.load(root)
            accepted = metadata['training_acceptance']
            self.assertEqual(set(accepted['unit_ids']), seeds | {'Fixture advancement'})
            self.assertTrue(accepted['implementation_complete'])
            self.assertFalse(accepted['native_semantics_accepted'])
            self.assertFalse(accepted['performance_accepted'])
            self.assertNotIn('captures', metadata)
            self.assertNotIn('complete', metadata)
            self.assertEqual(accepted['rules_file_sha256'], metadata['rules_file_sha256'])

    def test_unsupported_or_missing_advancement_blocks_even_with_approximate_coverage(self):
        for change in ('unsupported', 'missing'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                self.package(root, **{change: True})
                with self.assertRaisesRegex(RuntimeError, 'training closure is not ready'):
                    rules_catalog.load(root)

    def test_summary_identity_must_match_compiled_rules(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.package(root)
            path = root / rules_catalog.SUMMARY
            summary = json.loads(path.read_text(encoding='utf-8'))
            summary['source_hash'] = 'wrong'
            path.write_text(json.dumps(summary), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'source provenance mismatch'):
                rules_catalog.load(root)

    def test_rule_directory_resolution_uses_explicit_then_environment_then_default(self):
        with mock.patch.dict(os.environ, {'WESNOTH_RULES_DIR': str(ROOT / 'from-env')}):
            self.assertEqual(rules_catalog.resolve_dir(), (ROOT / 'from-env').resolve())
            self.assertEqual(rules_catalog.resolve_dir(ROOT / 'explicit'), (ROOT / 'explicit').resolve())
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(rules_catalog.resolve_dir(), (ROOT / 'data/rules/1.18.8-training').resolve())


class ProvenanceCacheTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        source = rules_catalog.resolve_dir()
        shutil.copyfile(source / 'rules.json', self.root / 'rules.json')
        shutil.copyfile(source / rules_catalog.SUMMARY, self.root / rules_catalog.SUMMARY)
        self.metadata = rules_catalog.load(self.root, require_accepted=False)

    def test_one_parse_per_rules_file_version(self):
        rules, digest = rules_catalog.provenance(self.metadata, self.root)
        again, digest_again = rules_catalog.provenance(self.metadata, self.root)
        self.assertIs(again, rules)
        self.assertEqual(digest_again, digest)

    def test_a_changed_rules_file_is_checked_again(self):
        rules_catalog.provenance(self.metadata, self.root)
        with (self.root / 'rules.json').open('ab') as stream:
            stream.write(b'\n')
        with self.assertRaisesRegex(ValueError, 'frozen catalog hash'):
            rules_catalog.provenance(self.metadata, self.root)

    def test_experience_modifier_scales_a_copy(self):
        from learning.adapters import scaled_rules
        shared = dict(units=dict(a=dict(experience=10)))
        self.assertIs(scaled_rules(shared, 100), shared)
        scaled = scaled_rules(shared, 70)
        self.assertEqual(scaled['units']['a']['experience'], 7)
        self.assertEqual(shared['units']['a']['experience'], 10)
