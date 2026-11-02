"""AMLA compiler accepts the exact native rule, never its display label alone."""
import copy
import unittest
from pathlib import Path

from engine_lite.audit import audit_catalog

from engine_lite.advancement import compile_advancement


def standard():
    effects = [dict(apply_to='hitpoints', increase_total=3, heal_full=True),
               dict(apply_to='max_experience', increase='20%'),
               dict(apply_to='status', remove='poisoned'),
               dict(apply_to='status', remove='slowed')]
    value = dict(id='amla_default', max_times=100, strict_amla=True,
                 description='Translated display', image='icons/amla-default.png')
    value.update({str(i): {'1': 'effect', '2': effect} for i, effect in enumerate(effects, 1)})
    return {'1': {'1': 'advancement', '2': value}}


class AmlaDeclarationTests(unittest.TestCase):
    def test_catalog_distinguishes_implemented_standard_amla(self):
        report = audit_catalog(Path(__file__).resolve().parents[2] / 'data/rules/1.18.8-combat')
        self.assertNotIn('amla_execution_unimplemented',
                         report['units']['Dwarvish Lord']['definition_gaps'])
        self.assertEqual(report['training_closure']['unsupported_unit_ids'], [])

    def test_exact_declaration_and_no_declaration(self):
        self.assertEqual(compile_advancement(standard()), (True, []))
        self.assertEqual(compile_advancement({}), (False, []))

    def test_name_does_not_hide_different_effect_or_conditions(self):
        for mutate in [lambda c: c['1']['2'].update(increase_total=30),
                       lambda c: c.update(max_times=99),
                       lambda c: c.update(strict_amla=False),
                       lambda c: c.update(require_amla='other'),
                       lambda c: c.update({'5': {'1': 'filter', '2': {'side': 1}}})]:
            cfg = standard()
            mutate(cfg['1']['2'])
            self.assertEqual(compile_advancement(cfg), (False, ['unsupported_advancement_declaration']))

    def test_multiple_choices_are_not_silently_standardized(self):
        cfg = standard()
        cfg['2'] = copy.deepcopy(cfg['1'])
        self.assertEqual(compile_advancement(cfg), (False, ['unsupported_advancement_declaration']))


if __name__ == '__main__':
    unittest.main()
