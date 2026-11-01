"""Chosen counterattack drives forecast, execution and defensive plague."""
import copy
import json
import unittest

from learning.data import validate_record
from tests.v5 import helpers as H


class RetaliationTests(unittest.TestCase):
    def test_forecast_execution_and_plague_share_the_selected_counter(self):
        rules = H.rules()
        rules['lawful_bonus'] = [0]
        rules['units']['Fighter']['weapons'][0].update(damage=1, strikes=1)
        rules['units']['Fighter']['resistance']['blade'] = 10
        rules['units']['Skeleton']['weapons'] = [
            dict(id='blade', damage=100, strikes=1, damage_type='blade', range='melee'),
            dict(id='plague', damage=20, strikes=1, damage_type='impact', range='melee',
                 specials=['plague'], plague_type='Ghost')]
        spec = H.spec(fog=False)
        spec['units'][0]['hp'] = 8
        spec['units'][2].update(unit_type='Skeleton', hp=36, moves=4)
        engine = H.engine(game_spec=spec, rules_data=rules)
        before = H.snapshot(engine)
        forecast = json.loads(engine.forecast(1, 'p1', 'e1', 0, 1))
        self.assertEqual(H.snapshot(engine), before)
        self.assertEqual(forecast['attacker']['average_hp'], 0)
        result = H.step(engine, dict(kind='attack', unit='p1', target='e1', weapon=0))
        self.assertEqual(result['strikes'][-1]['attacker'], 'e1')
        units = H.snapshot(engine)['game']['units']
        self.assertEqual(next(u['hp'] for u in units if u['id'] == 'e1'),
                         forecast['defender']['average_hp'])
        raised = [u for u in units if u['hp'] > 0 and u['pos'] == spec['units'][0]['pos']]
        self.assertEqual([(u['unit_type'], u['side']) for u in raised], [('Ghost', 2)])

    def test_v1_snapshots_and_rows_are_rejected(self):
        engine = H.engine()
        before = H.snapshot(engine)
        old = copy.deepcopy(before)
        old.update(combat_version='expected_damage_v1', rng_version='deterministic-expected_damage_v1')
        with self.assertRaisesRegex(ValueError, 'snapshot version mismatch'):
            H.restore(engine, old)
        self.assertEqual(H.snapshot(engine), before)
        row = H.synthetic_decision_row()
        for field, value in (('combat_version', 'expected_damage_v1'),
                             ('rng_version', 'deterministic-expected_damage_v1'),
                             ('teacher_profile', 'expected_damage_v1')):
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'identity|teacher'):
                validate_record(dict(row, **{field: value}))


if __name__ == '__main__':
    unittest.main()
