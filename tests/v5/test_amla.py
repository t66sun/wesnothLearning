"""Standard AMLA executes only when declared by the frozen unit type."""
import unittest
from tests.v5 import helpers as H


class AmlaTests(unittest.TestCase):
    def battle(self, *, declared=True, count=0, required=40, xp=None):
        rules = H.rules()
        rules['lawful_bonus'] = [0]
        rules['units']['Fighter']['standard_amla'] = declared
        rules['units']['Fighter']['weapons'][0].update(damage=0, strikes=1)
        rules['units']['Skeleton']['weapons'] = []
        spec = H.spec(fog=False)
        spec['units'][0].update(hp=12, xp=required-1 if xp is None else xp,
            amla_count=count, resolved_max_hp=40+3*count,
            resolved_max_experience=required, status=['poisoned', 'slowed'])
        spec['units'][2].update(unit_type='Skeleton', hp=36, moves=4)
        return H.engine(game_spec=spec, rules_data=rules)

    def attack(self, engine):
        H.step(engine, dict(kind='attack', unit='p1', target='e1', weapon=0))
        return next(u for u in H.observe(engine)['units'] if u['id']=='p1')

    def test_standard_amla_heals_preserves_type_and_consumes_experience(self):
        engine = self.battle()
        before = H.snapshot(engine)
        actual = self.attack(engine)
        self.assertEqual((actual['unit_type'], actual['hp'], actual['xp']), ('Fighter', 43, 0))
        self.assertEqual((actual['resolved_max_hp'], actual['resolved_max_experience'], actual['amla_count']), (43, 48, 1))
        self.assertFalse(set(actual['status']) & {'poisoned', 'slowed'})
        H.restore(engine, before)
        self.assertEqual(self.attack(engine), actual)

    def test_repeated_amla_rounds_the_twenty_percent_increase(self):
        actual = self.attack(self.battle(count=1, required=48))
        self.assertEqual((actual['hp'], actual['resolved_max_experience'], actual['amla_count']), (46, 58, 2))

    def test_no_amla_without_declaration_or_after_limit(self):
        for declared, count in [(False, 0), (True, 100)]:
            with self.subTest(declared=declared, count=count):
                actual = self.attack(self.battle(declared=declared, count=count))
                self.assertEqual((actual['hp'], actual['xp']), (12, 40))

    def test_excess_experience_carries_to_the_next_threshold(self):
        actual = self.attack(self.battle(xp=45))
        self.assertEqual((actual['hp'], actual['xp']), (43, 6))


if __name__ == '__main__':
    unittest.main()
