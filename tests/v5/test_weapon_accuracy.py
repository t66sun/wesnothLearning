"""Accuracy and opposing parry affect the same sampled/forecast strike."""
import copy
import json
import unittest

from tests.v5 import helpers as H


class WeaponAccuracyTests(unittest.TestCase):
    def battle(self, accuracy=0, parry=0, special=None, counter=True):
        rules = H.rules()
        rules['lawful_bonus'] = [0]
        for unit in rules['units'].values():
            unit['defense'] = dict.fromkeys(unit['defense'], 60)
            unit['resistance']['blade'] = 100
        rules['units']['Fighter']['weapons'] = [dict(id='sword', damage=10, strikes=1,
            damage_type='blade', range='melee', accuracy=accuracy, parry=15,
            specials=[special] if special else [])]
        rules['units']['Skeleton']['weapons'] = [dict(id='axe', damage=3, strikes=1,
            damage_type='blade', range='melee' if counter else 'ranged', accuracy=5, parry=parry)]
        spec = H.spec(fog=False)
        spec['units'][2].update(unit_type='Skeleton', hp=36, moves=4)
        return H.engine(game_spec=spec, rules_data=rules)

    def test_accuracy_and_parry_feed_execution_and_full_distribution(self):
        engine = self.battle(accuracy=20, parry=10)
        before = H.snapshot(engine)
        forecast = json.loads(engine.forecast(1, 'p1', 'e1', 0, 0))
        self.assertEqual(H.snapshot(engine), before)
        self.assertAlmostEqual(forecast['defender']['hp_chance']['26'], .7)
        self.assertAlmostEqual(forecast['defender']['hp_chance']['36'], .3)
        self.assertAlmostEqual(forecast['attacker']['hp_chance']['37'], .5)
        result = H.step(engine, dict(kind='attack', unit='p1', target='e1', weapon=0))
        self.assertEqual([s['chance'] for s in result['strikes']], [70, 50])
        H.restore(engine, before)
        self.assertEqual(H.step(engine, dict(kind='attack', unit='p1', target='e1', weapon=0)), result)

    def test_signed_clamping_special_order_and_absent_counter(self):
        for accuracy, parry, special, counter, expected in [
                (-100, 0, None, True, 0), (100, -50, None, True, 100),
                (-100, 20, 'magical', True, 70), (-100, 20, 'marksman', True, 60),
                (20, 30, None, False, 80)]:
            with self.subTest(accuracy=accuracy, parry=parry, special=special, counter=counter):
                engine = self.battle(accuracy, parry, special, counter)
                result = H.step(engine, dict(kind='attack', unit='p1', target='e1', weapon=0))
                self.assertEqual(result['strikes'][0]['chance'], expected)

    def test_old_v3_snapshot_is_rejected(self):
        engine = self.battle()
        old = copy.deepcopy(H.snapshot(engine))
        old['combat_version'] = 'probabilistic_combat_v3'
        with self.assertRaisesRegex(ValueError, 'snapshot version mismatch'):
            H.restore(engine, old)


if __name__ == '__main__':
    unittest.main()
