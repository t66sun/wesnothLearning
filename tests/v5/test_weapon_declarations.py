"""Frozen raw declarations restore native accuracy/parry without mutating inputs."""
import copy
import unittest

from engine_lite.weapons import compile_weapons


class WeaponDeclarationTests(unittest.TestCase):
    def test_signed_modifiers_and_defaults_are_compiled_from_raw(self):
        compact = [dict(id='sword'), dict(id='bow')]
        before = copy.deepcopy(compact)
        raw = {'1': {'1': 'attack', '2': dict(name='sword', accuracy=10, parry=-5)},
               '2': {'1': 'attack', '2': dict(name='bow')}}
        self.assertEqual(compile_weapons(raw, compact),
                         [dict(id='sword', accuracy=10, parry=-5), dict(id='bow', accuracy=0, parry=0)])
        self.assertEqual(compact, before)

    def test_mismatched_inventory_or_order_is_rejected(self):
        raw = {'1': {'1': 'attack', '2': dict(name='sword')}}
        for compact in ([], [dict(id='bow')]):
            with self.assertRaisesRegex(ValueError, 'weapon'):
                compile_weapons(raw, compact)

    def test_formula_is_not_silently_replaced_with_zero(self):
        raw = {'1': {'1': 'attack', '2': dict(name='sword', accuracy='(level * 10)')}}
        with self.assertRaisesRegex(ValueError, 'integer'):
            compile_weapons(raw, [dict(id='sword')])


if __name__ == '__main__':
    unittest.main()
