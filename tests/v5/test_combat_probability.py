"""Native forecast boundary contracts, separate from sampled execution."""
import copy
import json
import unittest

from tests.v5 import helpers as H


class CombatProbabilityTests(unittest.TestCase):
    def battle(self, *, special=None, chance=60, hp=1, xp=0, counter=False):
        rules = H.rules()
        rules['lawful_bonus'] = [0]
        rules['units']['Fighter']['advances_to'] = ['Ghost']
        for unit in rules['units'].values():
            unit['defense'] = dict.fromkeys(unit['defense'], chance)
        rules['units']['Fighter']['weapons'] = [dict(
            id='sword', damage=10, strikes=1, damage_type='blade', range='melee',
            specials=[special] if special else [])]
        rules['units']['Skeleton']['weapons'] = ([dict(
            id='poison', damage=3, strikes=1, damage_type='blade', range='melee',
            specials=['poison'])] if counter else [])
        spec = H.spec(fog=False)
        spec['units'][0].update(hp=20, xp=xp)
        spec['units'][2].update(unit_type='Skeleton', hp=hp, moves=4)
        engine = H.engine(game_spec=spec, rules_data=rules)
        return engine, rules, spec

    def forecast(self, engine):
        before = H.snapshot(engine)
        value = json.loads(engine.forecast(1, 'p1', 'e1', 0, 0))
        self.assertEqual(H.snapshot(engine), before)
        return value

    def test_fatal_debuffs_remain_in_native_prediction(self):
        for special, key in [('poison', 'poisoned'), ('slow', 'slowed')]:
            with self.subTest(special=special):
                engine, _, _ = self.battle(special=special)
                value = self.forecast(engine)['defender']
                self.assertAlmostEqual(value['hp_chance']['0'], .6)
                self.assertAlmostEqual(value[key], .6)

    def test_combat_experience_heals_forecast_and_execution(self):
        engine, _, _ = self.battle(hp=36, xp=39)
        value = self.forecast(engine)
        self.assertEqual(value['attacker']['hp_chance'], {'40': 1.})
        H.step(engine, dict(kind='attack', unit='p1', target='e1', weapon=0))
        actual = next(u for u in H.observe(engine)['units'] if u['id'] == 'p1')
        self.assertEqual((actual['unit_type'], actual['hp'], actual['xp']), ('Ghost', 30, 0))

    def test_conditional_advancement_uses_kill_probability(self):
        engine, _, _ = self.battle(xp=32)
        value = self.forecast(engine)['attacker']
        self.assertEqual(value['hp_chance'], {'20': .4, '40': .6})

    def test_conditional_poison_uses_native_marginal_estimate(self):
        engine, _, _ = self.battle(xp=32, counter=True)
        value = self.forecast(engine)['attacker']
        # Native estimates poison recovery from the kill/survival marginals.
        # Poison is delivered only in the 0.4 * 0.6 retaliation branch.
        self.assertAlmostEqual(value['poisoned'], .24 * (1-.6))
        self.assertAlmostEqual(value['hp_chance']['40'], .6)

    def test_zero_level_kill_awards_four_experience(self):
        _, rules, spec = self.battle(chance=100, xp=35)
        rules['units']['Skeleton']['level'] = 0
        engine = H.engine(game_spec=spec, rules_data=rules)
        self.assertEqual(self.forecast(engine)['attacker']['hp_chance'], {'20': 1.})
        H.step(engine, dict(kind='attack', unit='p1', target='e1', weapon=0))
        actual = next(u for u in H.observe(engine)['units'] if u['id'] == 'p1')
        self.assertEqual((actual['unit_type'], actual['xp']), ('Fighter', 39))

    def test_old_probability_profile_is_rejected(self):
        engine, _, _ = self.battle()
        before = H.snapshot(engine)
        old = copy.deepcopy(before)
        old['combat_version'] = 'probabilistic_combat_v1'
        with self.assertRaisesRegex(ValueError, 'snapshot version mismatch'):
            H.restore(engine, old)
        self.assertEqual(H.snapshot(engine), before)


if __name__ == '__main__':
    unittest.main()
