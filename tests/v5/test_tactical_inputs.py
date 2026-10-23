"""Public move-ranking inputs must survive collection and deployment."""
import math
import unittest

from learning.features import ACTION, ENTITY, VERSION
from learning.data import validate_record
from learning.sequences import _validate_raw
from tests.test_lua_contracts import initialize
from tests.test_core import record


class TacticalInputTests(unittest.TestCase):
    def capture(self):
        lua, modules = initialize()
        obs = modules['observation.lua'].capture(lua.table(), 1)
        actions, timing = modules['candidates.lua'].generate(obs, 200)
        return lua, modules, obs, actions, timing

    def test_public_move_score_reaches_student(self):
        self.assertEqual(VERSION, 5)
        index = {n: i+1 for i, (n, _) in enumerate(ACTION)}
        self.assertTrue({'move_tactical', 'move_gain', 'move_risk', 'move_primary'} <= index.keys())
        self.assertEqual(ACTION[-1][0], 'unit_type_index')
        _, _, _, actions, timing = self.capture()
        moves = [a for _, a in actions.items() if a['kind'] == 'move']
        self.assertTrue(moves)
        self.assertTrue(any(abs(a['features'][index['move_tactical']]) > 0 for a in moves))
        primary = [a for a in moves if a['features'][index['move_primary']] == 1]
        self.assertEqual(len(primary), len({a['actor']['id'] for a in moves}))
        self.assertTrue(all(a['full'] for a in primary))
        self.assertEqual(timing['budget'], 'fixed-20000-v3')
        self.assertLessEqual(len(actions), 128)
        self.assertLessEqual(timing['predictions'], 16)
        for _, a in actions.items():
            self.assertTrue(all(math.isfinite(v) for _, v in a['features'].items()))
            self.assertFalse(any(str(k).startswith('_') for k, _ in a.items()))

    def test_gain_is_relative_to_the_same_actors_origin(self):
        lua, modules = initialize()
        lua.execute('''
            fixture.visible=fixture.own
            wesnoth.sides[1].recruit={}
            wesnoth.map.find=function(f) return f.terrain and {} or {{7,1}} end
            wesnoth.paths.find_reach=function(u,cfg)
                return {{u.x,u.y,u.moves},{u.x+1,u.y,u.moves-1},{u.x+2,u.y,u.moves-2}}
            end
        ''')
        obs = modules['observation.lua'].capture(lua.table(), 1)
        actions, _ = modules['candidates.lua'].generate(obs, 200)
        index = {n: i+1 for i, (n, _) in enumerate(ACTION)}
        gains = {(a['tx'], a['ty']): a['features'][index['move_gain']]*25
                 for _, a in actions.items() if a['kind'] == 'move' and a['actor']['id'] == 'soldier'}
        self.assertIn((3, 1), gains)
        self.assertIn((4, 1), gains)
        self.assertGreater(gains[(4, 1)], gains[(3, 1)])
        self.assertGreater(gains[(3, 1)], 0)

    def test_relative_round_is_encoded_without_absolute_side_ids(self):
        lua, modules = initialize()
        unit = lua.globals().fixture.visible[3]
        unit.side = 4
        before = modules['spatial.lua'].entity(unit, 3)
        unit.side = 2
        after = modules['spatial.lua'].entity(unit, 3)
        index = dict((n, i+1) for i, (n, _) in enumerate(ENTITY))
        self.assertEqual(before['features'][index['next_round']], 0)
        self.assertEqual(after['features'][index['next_round']], 1)

    def test_inputs_are_generated_before_teacher_query_and_do_not_consume_rng(self):
        import json
        from tests.v5 import helpers
        engine = helpers.engine(game_spec=helpers.spec(sides=4, fog=False))
        before = json.loads(engine.snapshot())['game']
        student = json.loads(engine.decision(1, 500, False, True))
        teacher = json.loads(engine.decision(1, 500, True, True))
        self.assertEqual(student['candidates'], teacher['candidates'])
        self.assertEqual(before, json.loads(engine.snapshot())['game'])

    def test_schema_width_is_identical_in_collected_and_exported_lua(self):
        from learning.lite_host import host_modules
        # Both entry points serialize this same named schema, including the last
        # embedding field. Tests below exercise its actual Lua/PyTorch numerics.
        lua, _ = initialize()
        exported = lua.execute(host_modules()['features.lua'])
        self.assertEqual(exported['version'], VERSION)
        self.assertEqual(len(exported['action_features']), len(ACTION))
        self.assertEqual(len(exported['entity_features']), len(ENTITY))

    def test_old_supervised_and_uncovered_records_cannot_be_silently_relabelled(self):
        row = record()
        row['schema'] = 4
        with self.assertRaisesRegex(ValueError, 'schema mismatch'):
            validate_record(row)
        row['choice'] = -1
        with self.assertRaisesRegex(ValueError, 'current-schema'):
            _validate_raw(row)
        self.assertEqual(row['schema'], 4)


if __name__ == '__main__':
    unittest.main()
