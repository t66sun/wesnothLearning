import unittest
from lupa import LuaRuntime
from learning.common import ROOT
import match


class TeacherBudgetTests(unittest.TestCase):
    def test_per_seat_options_and_legacy_defaults(self):
        self.assertEqual(match.seat_budgets(None, 2), {})
        self.assertEqual(match.seat_budgets({1: {'timeout': 2, 'first_timeout': 20}}, 2),
                         {'1': {'timeout': 2, 'first_timeout': 20}})
        for invalid in ({0: {'timeout': 1, 'first_timeout': 10}},
                        {3: {'timeout': 1, 'first_timeout': 10}},
                        {1: {'timeout': 0, 'first_timeout': 10}},
                        {1: {'timeout': float('nan'), 'first_timeout': 10}},
                        {1: {'timeout': True, 'first_timeout': 10}},
                        {1: {'timeout': 1}}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                match.seat_budgets(invalid, 2)

    def runtime(self):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute('''
            now=0;events={};options={timeout=1,first_timeout=10,max_actions=2000,
                seat_timeouts={['1']={timeout=2,first_timeout=20},['2']={timeout=1,first_timeout=10}}}
            judge={states={},options=function() return options end,done=function() return false end,
                emit=function(kind,row) events[#events+1]={kind=kind,row=row} end,
                check=function() end,disqualify=function(side,reason) fault={side=side,reason=reason} end}
            implementation={evaluation=function() return 100 end,execution=function() now=now+elapsed end}
            wesnoth={current={side=1,turn=1},ms_since_init=function() return now end,
                require=function() return judge end,dofile=function() now=now+load_ms;return implementation end}
            ai={};load_ms=0;elapsed=0
        ''')
        lua.globals().candidate = lua.execute((ROOT / 'vendor/arena/runtime/candidate.lua').read_text())
        return lua

    def test_runtime_call_budgets_include_first_load_and_execution(self):
        lua = self.runtime()
        lua.execute('''
            load_ms=100;elapsed=900
            candidate:evaluation({entry='bot'},{});candidate:execution({}, {})
            first=events[1].row;first_return=events[#events].row
            events={};elapsed=1500
            candidate:evaluation({entry='bot'},{});candidate:execution({}, {})
            ordinary=events[1].row;ordinary_return=events[#events].row
            wesnoth.current.side=2;events={};elapsed=0;load_ms=0
            candidate:evaluation({entry='bot'},{});candidate:execution({}, {})
            old_first=events[1].row
            events={};elapsed=1500
            candidate:evaluation({entry='bot'},{});candidate:execution({}, {})
            old_ordinary=events[1].row
        ''')
        self.assertEqual(lua.eval('first.budget'), 20)
        self.assertEqual(lua.eval('first_return.elapsed_ms'), 1000)
        self.assertEqual(lua.eval('ordinary.budget'), 2)
        self.assertEqual(lua.eval('ordinary_return.elapsed_ms'), 1500)
        self.assertEqual(lua.eval('old_first.budget'), 10)
        self.assertEqual(lua.eval('old_ordinary.budget'), 1)
        self.assertEqual(lua.eval('fault.side'), 2)
        self.assertEqual(lua.eval('fault.reason'), 'candidate-action timeout')

    def test_omitting_override_uses_original_runtime_budget(self):
        lua = self.runtime()
        lua.execute('''
            options.seat_timeouts=nil;elapsed=0
            candidate:evaluation({entry='bot'},{});candidate:execution({}, {})
            first=events[1].row.budget;events={}
            candidate:evaluation({entry='bot'},{});candidate:execution({}, {})
        ''')
        self.assertEqual(lua.eval('first'), 10)
        self.assertEqual(lua.eval('events[1].row.budget'), 1)


if __name__ == '__main__':
    unittest.main()
