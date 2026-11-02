"""Per-unit immunity flags affect forecasts and both directions of execution."""
import json
import unittest

from tests.v5 import helpers as H


class CombatImmunityTests(unittest.TestCase):
    def battle(self, special, *, immune, defense=False):
        rules = H.rules()
        rules['lawful_bonus'] = [0]
        for t in rules['units'].values():
            t['defense'] = dict.fromkeys(t['defense'], 100)
        weapon = dict(id=special, damage=10, strikes=1, damage_type='blade',
                      range='melee', specials=[special])
        if special == 'plague':
            weapon['plague_type'] = 'Ghost'
        rules['units']['Fighter']['weapons'] = [weapon] if not defense else [dict(
            id='sword', damage=1, strikes=1, damage_type='blade', range='melee')]
        rules['units']['Skeleton']['weapons'] = [weapon] if defense else []
        spec = H.spec(fog=False)
        spec['units'][0].update(hp=20, leader=False)
        spec['units'][2].update(unit_type='Skeleton', hp=20, moves=4, leader=False)
        target = spec['units'][0 if defense else 2]
        if special == 'plague':
            target['hp'] = 1
        flag = {'poison': 'unpoisonable', 'drains': 'undrainable', 'plague': 'unplagueable'}[special]
        target['status'] = [flag] if immune else []
        return H.engine(game_spec=spec, rules_data=rules), target['id'], target['pos']

    def test_poison_immunity_blocks_nonfatal_and_fatal_forecasts_and_execution(self):
        for defense in (False, True):
            for immune in (False, True):
                with self.subTest(defense=defense, immune=immune):
                    engine, target, _ = self.battle('poison', immune=immune, defense=defense)
                    for hp in (1, 20):
                        saved = H.snapshot(engine)
                        next(u for u in saved['game']['units'] if u['id'] == target)['hp'] = hp
                        H.restore(engine, saved)
                        forecast = json.loads(engine.forecast(1, 'p1', 'e1', 0, 0))
                        self.assertEqual(forecast['attacker' if defense else 'defender']['poisoned'], float(not immune))
                    H.step(engine, dict(kind='attack', unit='p1', target='e1', weapon=0))
                    actual = next(u for u in H.snapshot(engine)['game']['units'] if u['id'] == target)
                    self.assertEqual('poisoned' in actual['status'], not immune)

    def test_drain_immunity_blocks_healing_in_forecast_and_execution(self):
        for defense in (False, True):
            for immune in (False, True):
                with self.subTest(defense=defense, immune=immune):
                    engine, _, _ = self.battle('drains', immune=immune, defense=defense)
                    expected = (19 if defense else 20) + (0 if immune else 5)
                    forecast = json.loads(engine.forecast(1, 'p1', 'e1', 0, 0))
                    self.assertEqual(forecast['defender' if defense else 'attacker']['average_hp'], expected)
                    H.step(engine, dict(kind='attack', unit='p1', target='e1', weapon=0))
                    actual = next(u for u in H.snapshot(engine)['game']['units'] if u['id'] == ('e1' if defense else 'p1'))
                    self.assertEqual(actual['hp'], expected)

    def test_plague_immunity_blocks_conversion_in_both_directions(self):
        for defense in (False, True):
            for immune in (False, True):
                with self.subTest(defense=defense, immune=immune):
                    engine, _, pos = self.battle('plague', immune=immune, defense=defense)
                    H.step(engine, dict(kind='attack', unit='p1', target='e1', weapon=0))
                    raised = [u for u in H.snapshot(engine)['game']['units'] if u['pos'] == pos and u['hp'] > 0]
                    self.assertEqual([u['unit_type'] for u in raised], [] if immune else ['Ghost'])


if __name__ == '__main__':
    unittest.main()
