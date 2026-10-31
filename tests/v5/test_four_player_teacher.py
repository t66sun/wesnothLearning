"""Minimal regression for the unchanged Astra four-player teacher in lite."""
import json
import unittest
from pathlib import Path

from learning.lite_host import host_modules, teacher_candidate
from . import helpers


class FourPlayerTeacherTests(unittest.TestCase):
    def test_modules_use_the_maintained_teacher_source(self):
        from learning.teachers import lua_modules

        modules = host_modules(Path('data/opponents/gpt6astra.zip'))
        self.assertEqual(modules['astra/four.lua'], lua_modules()['astra/four.lua'])
        self.assertIn('expected_damage_v1', modules['astra/value.lua'])

    def test_four_player_astra_reads_native_configs_without_advancing_state(self):
        from _engine_lite import LiteEngine

        rules = helpers.rules()
        rules['units']['Fighter']['abilities'] = ['healing']
        modules = host_modules()
        # Verify the native config projection before executing the actual shipped
        # teacher. The wrapper adds assertions, not a replacement teacher policy.
        modules['astra/four.lua'] = """
local own=wesnoth.units.find_on_map{side=wesnoth.current.side}[1]
local abilities=assert(wml.get_child(own.__cfg,'abilities'))
assert(wml.get_child(abilities,'heals').id=='healing')
assert(wml.get_child(abilities,'missing')==nil)
local enemy=wesnoth.units.find_on_map{side=3}[1]
local specials=assert(wml.get_child(enemy.attacks[1].__cfg,'specials'))
assert(wml.get_child(specials,'magical').id=='magical')
""" + modules['astra/four.lua']

        for format_name in ('ffa4', 'team2v2'):
            with self.subTest(format=format_name):
                spec = helpers.spec(sides=4, fog=False)
                for side in spec['sides']:
                    side['gold'] = 0  # Reach threat/movement code after recruiting.
                    if format_name == 'ffa4':
                        side['team'] = str(side['id'])
                engine = LiteEngine(json.dumps(rules), json.dumps(spec))
                engine.configure_host(json.dumps(modules))
                before = json.loads(engine.snapshot())['game']
                student = json.loads(engine.decision(1, False))
                teacher = json.loads(engine.decision(1, True))
                self.assertEqual(json.loads(engine.snapshot())['game'], before)
                self.assertEqual(student['candidates'], teacher['candidates'])
                action = teacher_candidate(teacher['teacher_action'])
                self.assertNotEqual(action['kind'], 'end_turn')
                outcome = json.loads(engine.execute_candidate(json.dumps(action)))
                self.assertTrue(outcome['committed'], outcome)
                # A non-first side also creates sparse outer memory keys.
                row = json.loads(engine.decision(3, False))
                saved = engine.snapshot()
                engine.restore(saved)
                restored = json.loads(engine.decision(3, False))
                self.assertEqual(restored['opponents'], row['opponents'])
                self.assertEqual(restored['global'], row['global'])


if __name__ == '__main__':
    unittest.main()
