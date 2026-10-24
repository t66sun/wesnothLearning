"""Tactical checks for the Astra teacher derived from expected_damage_v1."""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

import lupa

from learning.data import validate_record
from learning.teachers import PROFILE, build, identity, lua_modules, source_digest
from tests.v5 import helpers

ROOT = Path(__file__).resolve().parents[2]


def _values():
    lua = lupa.LuaRuntime(unpack_returned_tuples=True)
    path = (ROOT / 'learning/teachers/gpt6astra/lua/value.lua').as_posix()
    return lua, lua.execute('return dofile("%s")' % path)


class AstraAdaptationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lua, cls.values = _values()

    def score(self, **overrides):
        option = dict(dealt=0, taken=0, kill=0, death=0, enemy_value=100, enemy_max=100,
                      own_value=100, own_max=100, death_cost=.7, poison=0,
                      enemy_poisoned=False, slow=0, enemy_slowed=False, own_poison=0,
                      own_poisoned=False, risk=0, expected_hp=100, risk_weight=.35)
        option.update(overrides)
        return self.values.combat_score(self.lua.table_from(option))

    @staticmethod
    def legacy(**overrides):
        """The frozen upstream status values, used only as a counterexample."""
        option = dict(dealt=0, taken=0, kill=0, death=0, enemy_value=100, enemy_max=100,
                      own_value=100, own_max=100, death_cost=.7, poison=0,
                      enemy_poisoned=False, slow=0, enemy_slowed=False)
        option.update(overrides)
        s = (option['dealt'] * option['enemy_value'] / option['enemy_max']
             + option['kill'] * option['enemy_value'] * .8
             - option['taken'] * option['own_value'] / option['own_max']
             - option['death'] * option['own_value'] * option['death_cost'])
        if not option['enemy_poisoned']:
            s += option['poison'] * 8 * option['enemy_value'] / option['enemy_max']
        if not option['enemy_slowed']:
            s += option['slow'] * 5
        return s

    def test_six_public_positions_rank_deterministically(self):
        # 1. A lethal blow beats a larger nonlethal hit.
        lethal = self.score(dealt=10, kill=1)
        nonlethal = self.score(dealt=12)
        self.assertGreater(lethal, nonlethal)

        # 2. Surviving retaliation beats a bigger hit that kills the attacker.
        fatal = self.score(dealt=50, death=1)
        survival = self.score(dealt=20)
        self.assertGreater(survival, fatal)

        # 3. Of two strikes with different original hit chances, the one that
        #    deals more expected damage and does not die ranks first.
        accurate = self.score(dealt=30, taken=4)
        speculative = self.score(dealt=10, taken=8)
        self.assertGreater(accurate, speculative)

        # 4. Slow is worth the damage cut plus the movement restriction.
        slowed = self.score(slow=1, risk=20)
        plain = self.score(dealt=6)
        self.assertGreater(slowed, plain)
        self.assertAlmostEqual(self.values.slow_gain(20), 7.0)
        self.assertLess(self.legacy(dealt=0, slow=1), 6)

        # 5. A poison tick is six points, so a poison-only attack loses to a
        #    seven-point hit; the old eight-point value ranked it first.
        poisoned = self.score(poison=1)
        hit = self.score(dealt=7)
        self.assertGreater(hit, poisoned)
        self.assertGreater(self.legacy(poison=1), 7)

        # 6. Poison immunity removes the status bonus, so a normal attack wins.
        immune = self.score(poison=1, enemy_poisoned=True)
        normal = self.score(dealt=3)
        self.assertGreater(normal, immune)
        self.assertEqual(self.values.POISON_TICK, 6.0)

    def test_old_teacher_rows_cannot_enter_a_new_batch(self):
        row = helpers.sequence_rows(turns=1, decisions_per_turn=1)[0]
        validate_record(row, 'duel')
        del row['teacher_profile']
        with self.assertRaisesRegex(ValueError, 'different Astra teacher profile'):
            validate_record(row, 'duel')

    def test_source_is_derived_and_marked(self):
        modules = lua_modules()
        self.assertIn('astra/value.lua', modules)
        for name in ('duel.lua', 'four.lua', 'eight.lua'):
            self.assertIn('V.combat_score', modules['astra/' + name])
        self.assertEqual(identity()['teacher_profile'], PROFILE)
        with tempfile.TemporaryDirectory() as directory:
            target = build(Path(directory) / 'derived.zip')
            with zipfile.ZipFile(target) as archive:
                self.assertIn('gpt6astra/lua/value.lua', archive.namelist())
                self.assertIn('gpt6astra/lua/duel.lua', archive.namelist())
                self.assertEqual(json.loads(archive.read('gpt6astra/arena.json'))['id'], 'gpt6astra')
        self.assertEqual(identity()['teacher_source_sha256'], source_digest())


if __name__ == '__main__':
    unittest.main()
