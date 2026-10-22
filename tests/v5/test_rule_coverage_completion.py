"""Small deterministic checks for implementation coverage and training closure."""
import hashlib
import json
from pathlib import Path
import runpy
import tempfile
import unittest

from engine_lite.audit import audit_catalog, training_closure


def unit(*, advances=(), weapons=(), abilities=(), unsupported=()):
    return dict(advances_to=list(advances), weapons=list(weapons),
                abilities=list(abilities), unsupported=list(unsupported))


def approximate(units):
    return {name: dict(status='approximate', reasons=['native semantics pending'], scopes=['core'])
            for name in units}


PROFILE = dict(FACTIONS=('Fixture',), LEADERS=('Leader',), RECRUITS=('Recruit',))


class TrainingClosureTests(unittest.TestCase):
    def test_advancement_and_plague_are_transitive_and_missing_references_block(self):
        units = dict(Leader=unit(), Recruit=unit(advances=['Veteran']),
                     Veteran=unit(weapons=[dict(id='touch', specials=['plague'], plague_type='Spawn')]),
                     Spawn=unit(advances=['Missing']))
        report = training_closure(dict(units=units), approximate(units), PROFILE)
        self.assertEqual(report['unit_ids'], ['Leader', 'Recruit', 'Spawn', 'Veteran'])
        self.assertEqual(report['missing_unit_ids'], ['Missing'])
        self.assertIn(dict(source='Veteran', kind='plague', target='Spawn'), report['references'])
        self.assertFalse(report['implementation_complete'])

    def test_unknown_declarations_and_events_cannot_be_hidden_by_approximate(self):
        units = dict(Leader=unit(abilities=['unknown_aura']),
                     Recruit=unit(weapons=[dict(id='sword', specials=['unknown_strike'])],
                                  unsupported=['scripted_type_event']))
        report = training_closure(dict(units=units), approximate(units), PROFILE)
        self.assertEqual(report['unsupported_unit_ids'], ['Leader', 'Recruit'])
        self.assertIn('ability:unknown_aura', report['unsupported_reasons']['Leader'])
        self.assertIn('weapon:sword:unknown_strike', report['unsupported_reasons']['Recruit'])
        self.assertIn('scripted_type_event', report['unsupported_reasons']['Recruit'])
        self.assertFalse(report['implementation_complete'])

    def test_real_profile_seeds_come_from_the_shared_training_configuration(self):
        path = Path(__file__).resolve().parents[2] / 'vendor/arena/params.py'
        profile = runpy.run_path(str(path))
        seeds = set(profile['LEADERS'])
        for recruits in profile['RECRUITS']:
            seeds.update(recruits.split(','))
        units = {name: unit() for name in seeds}
        report = training_closure(dict(units=units), approximate(units))
        self.assertEqual(set(report['factions']), set(profile['FACTIONS']))
        self.assertEqual(set(report['unit_ids']), seeds)
        self.assertTrue(report['implementation_complete'])

    def test_missing_coverage_entry_and_untyped_plague_block(self):
        units = dict(Leader=unit(), Recruit=unit(weapons=[dict(id='touch', specials=['plague'])]))
        coverage = approximate(units)
        del coverage['Leader']
        report = training_closure(dict(units=units), coverage, PROFILE)
        self.assertEqual(report['unsupported_reasons']['Leader'], ['missing_coverage_entry'])
        self.assertIn('weapon:touch:plague_without_type', report['unsupported_reasons']['Recruit'])
        self.assertFalse(report['implementation_complete'])


class CoverageAuditTests(unittest.TestCase):
    def test_compiled_coverage_does_not_treat_amla_only_abilities_as_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            raw = dict(id='Leader', **{'1': {'1': 'advancement', '2': {
                '1': {'1': 'abilities', '2': {'1': {'1': 'dummy', '2': {'id': 'amla_only'}}}}}}})
            units = dict(Leader=unit(), Recruit=unit(unsupported=['scripted_type_event']))
            capture = dict(scope='core', units=units,
                           raw_definitions=dict(Leader=raw, Recruit=dict(id='Recruit')), variations={})
            data = json.dumps(capture).encode()
            digest = hashlib.sha256(data).hexdigest()
            (root / 'captures').mkdir()
            (root / 'captures' / (digest + '.json')).write_bytes(data)
            rules = dict(rules_version='fixture', source_hash='fixture', units=units)
            rules_bytes = json.dumps(rules).encode()
            (root / 'rules.json').write_bytes(rules_bytes)
            catalog = dict(rules_file_sha256=hashlib.sha256(rules_bytes).hexdigest(),
                           captures=[dict(sha256=digest)], complete=False,
                           native_accepted=False, performance_accepted=False)
            (root / 'catalog.json').write_text(json.dumps(catalog), encoding='utf-8')
            (root / 'coverage.json').write_text(json.dumps(approximate(units)), encoding='utf-8')
            report = audit_catalog(root)
            self.assertEqual(report['units']['Leader']['implementation_status'],
                             'implemented_pending_native_acceptance')
            self.assertEqual(report['units']['Recruit']['implementation_status'], 'event_dependent')
            self.assertEqual(report['units']['Leader']['abilities'][0]['id'], 'amla_only')
            self.assertEqual(report['units']['Leader']['compiled_abilities'], [])
            self.assertFalse(report['semantic_acceptance']['native_accepted'])
            self.assertEqual(report['coverage_counts'], dict(approximate=2))


if __name__ == '__main__':
    unittest.main()
