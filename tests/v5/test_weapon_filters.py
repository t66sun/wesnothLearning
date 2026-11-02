"""Native defense weights filter counters, not explicitly chosen attacks."""
import json
import unittest

from engine_lite.weapon_specials import compile_special
from tests.v5 import helpers as H


class WeaponFilterTests(unittest.TestCase):
    def battle(self, weights):
        rules = H.rules()
        rules['lawful_bonus'] = [0]
        for row in rules['units'].values():
            row['defense'] = dict.fromkeys(row['defense'], 100)
            row['resistance']['blade'] = 100
        rules['units']['Fighter']['weapons'] = [dict(id='sword', damage=1, strikes=1,
            damage_type='blade', range='melee', attack_weight=0)]
        rules['units']['Skeleton']['weapons'] = [dict(id=str(i), damage=damage, strikes=1,
            damage_type='blade', range='melee', defense_weight=weight)
            for i, (damage, weight) in enumerate(zip([15, 3], weights))]
        spec = H.spec(fog=False)
        spec['units'][2].update(unit_type='Skeleton', hp=36, moves=4)
        return H.engine(game_spec=spec, rules_data=rules)

    def test_old_v4_snapshot_is_rejected(self):
        engine = self.battle([1, 1])
        old = H.snapshot(engine)
        old['combat_version'] = 'probabilistic_combat_v4'
        with self.assertRaisesRegex(ValueError, 'snapshot version mismatch'):
            H.restore(engine, old)

    def test_nonpositive_defense_weight_is_ineligible(self):
        for weight in (0, -1):
            with self.subTest(weight=weight):
                engine = self.battle([weight, 1])
                forecast = json.loads(engine.forecast(1, 'p1', 'e1', 0, 0))
                self.assertEqual(forecast['attacker']['average_hp'], 37)
                result = H.step(engine, dict(kind='attack', unit='p1', target='e1', weapon=0))
                self.assertEqual(result['strikes'][1]['damage'], 3)

    def test_no_eligible_counter_and_explicit_zero_weight_attack(self):
        engine = self.battle([0, -1])
        action = dict(kind='attack', unit='p1', target='e1', weapon=0)
        self.assertIn(action, json.loads(engine.legal_actions(1)))
        forecast = json.loads(engine.forecast(1, 'p1', 'e1', 0, 0))
        self.assertEqual(forecast['attacker']['hp_chance'], {'40': 1.})
        result = H.step(engine, action)
        self.assertEqual(len(result['strikes']), 1)

    def test_positive_weight_does_not_override_native_distribution_choice(self):
        engine = self.battle([1, 1000])
        result = H.step(engine, dict(kind='attack', unit='p1', target='e1', weapon=0))
        self.assertEqual(result['strikes'][1]['damage'], 15)


class WeaponSpecialCompilerTests(unittest.TestCase):
    def test_standard_name_cannot_hide_a_different_rule(self):
        for tag, cfg in [('chance_to_hit', dict(id='magical', value=100, cumulative=False)),
                         ('berserk', dict(id='berserk', value=99)),
                         ('damage', dict(id='charge', multiply=2, active_on='defense', apply_to='both')),
                         ('disable', dict(id='firststrike')),
                         ('poison', {'id': 'poison', '1': {'1': 'filter_opponent', '2': {'race': 'elf'}}})]:
            with self.subTest(tag=tag, cfg=cfg):
                self.assertIsNone(compile_special(tag, cfg))

    def test_label_is_not_the_rule(self):
        self.assertEqual(compile_special('firststrike', dict(id='deterrentstrike')), ('firststrike', {}))
        self.assertEqual(compile_special('chance_to_hit', dict(id='translated', value=70, cumulative=False)), ('magical', {}))


if __name__ == '__main__':
    unittest.main()
