"""The maintained teacher stops a native ambush without masking move errors."""
import unittest
from pathlib import Path

from lupa import LuaError, LuaRuntime


ROOT = Path(__file__).resolve().parents[2]
STRATEGIES = ('duel', 'four', 'eight')


def scene(strategy, status):
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.globals().move_status = status
    lua.execute("""
actor={id='actor',x=4,y=3,moves=5}
target={id='target',x=4,y=4}
calls={move=0,attack=0}
local helper={get_attackable_enemies=function() return {target} end}
wesnoth={sides={{},{}},current={side=1},
    require=function() return helper end,
    ms_since_init=function() return 0 end,
    paths={find_path=function() return {{4,3},{3,4}} end},
    units={find_on_map=function() return {actor} end}}
ai={check_move=function() return {ok=true} end,
    check_attack=function() return {ok=true} end,
    attack=function() calls.attack=calls.attack+1; return {ok=true} end}
ai.move=function(u,p)
    calls.move=calls.move+1
    u.x=p[1];u.y=p[2];u.moves=0
    return {ok=move_status==0,status=move_status}
end
ai.move_full=ai.move
plan={kind='combat',id='actor',x=4,y=3,tx=3,ty=4,enemy='target',weapon=1}
""")
    module = lua.execute((ROOT / f'learning/teachers/gpt6astra/lua/{strategy}.lua').read_text())
    return lua, module


class TeacherMovementTests(unittest.TestCase):
    def test_ambush_stops_before_the_planned_attack(self):
        for strategy in STRATEGIES:
            with self.subTest(strategy=strategy):
                lua, teacher = scene(strategy, 2005)
                teacher.execution(teacher, lua.table(), lua.table(plan=lua.globals().plan))
                self.assertEqual(lua.globals().calls.move, 1)
                self.assertEqual(lua.globals().calls.attack, 0)
                self.assertEqual((lua.globals().actor.x, lua.globals().actor.y), (3, 4))

    def test_normal_arrival_executes_the_planned_attack(self):
        for strategy in STRATEGIES:
            with self.subTest(strategy=strategy):
                lua, teacher = scene(strategy, 0)
                teacher.execution(teacher, lua.table(), lua.table(plan=lua.globals().plan))
                self.assertEqual(lua.globals().calls.attack, 1)

    def test_other_native_move_errors_still_fail(self):
        for strategy in STRATEGIES:
            with self.subTest(strategy=strategy):
                lua, teacher = scene(strategy, 2008)
                with self.assertRaises(LuaError):
                    teacher.execution(teacher, lua.table(), lua.table(plan=lua.globals().plan))
                self.assertEqual(lua.globals().calls.attack, 0)


if __name__ == '__main__':
    unittest.main()
