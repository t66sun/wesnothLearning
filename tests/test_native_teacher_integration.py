"""Frozen Native teacher wiring, independent query clocks and public history."""
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lupa import LuaRuntime
from learning.common import ROOT
from learning.teachers.registry import freeze_set, execution_identity
from learning.teachers.runtime import prepare_job, dagger_rows, query_metrics
from query_clock import QueryClock


def query_runtime():
    lua = LuaRuntime(unpack_returned_tuples=True)
    memory = lua.execute((ROOT/'lua/teacher_memory.lua').read_text())
    lua.globals().memory_module = memory
    lua.execute('''
        now=0;loads=0;real_actions=0;draws=0
        mathx={random=function() draws=draws+1;return 7 end}
        ai={move=function() real_actions=real_actions+1 end}
        wesnoth={current={side=1,turn=1},ms_since_init=function() return now end,
            sides={is_enemy=function(a,b) return a~=b end},require=function() return memory_module end,
            dofile=function(entry) loads=loads+1;loaded_entry=entry;now=now+load_ms
                if load_failure then error('fixture load failure') end
                return implementation end}
        implementation={evaluation=function(self,cfg,data)
            if fail_action then ai.move() end
            if fail_rng then mathx.random() end
            now=now+plan_ms
            data.public.owners[2002]=99;data.home.actor[1]=99
            data.plan={kind='combat',x=2,y=2,tx=2,ty=2,ex=3,ey=2,weapon=2}
        end}
        obs={side=1,own={{id='actor',side=1,x=2,y=2,canrecruit=true}},
            occupied={['2,2']={id='actor',side=1,x=2,y=2},['3,2']={id='enemy',side=2,x=3,y=2}},
            memory={villages={['2,2']=1}},tiles={['2,2']={terrain='Kh',visible=true},['3,2']={terrain='Gg',visible=true}}}
        data={};load_ms=0;plan_ms=0;budgets={}
        data.teacher_query_begin=function(budget,first) budgets[#budgets+1]={budget=budget,first=first} end
        data.teacher_query_end=function(elapsed) elapsed_query=elapsed end
        training={dagger_entry='frozen/duel/bot.lua',dagger_timeout=2,dagger_first_timeout=20,
            dagger_identity={teacher_contract=1,teacher='selected_teacher',teacher_package_sha256='fixture'}}
        candidates={{kind='attack',x=2,y=2,tx=3,ty=2,weapon=2},{kind='end_turn'}}
        scores={0,0}
    ''')
    lua.globals().teacher = lua.execute((ROOT/'lua/teacher.lua').read_text())
    return lua


class NativeTeacherIntegrationTests(unittest.TestCase):
    def test_runtime_roles_pin_entries_budgets_and_query_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            contract = freeze_set(Path(directory)/'teachers', 'mixed-20261107')
            for fmt, roles in contract['formats'].items():
                spec = roles['supervision']
                job = dict(format=fmt, bots=[spec['package'], 'student', 'baseline'], teacher_roles=roles,
                           learning=dict(dagger_teacher=spec['package'], sides={'1': {'teacher': True}, '2': {'teacher': False}}))
                prepared = prepare_job(job, 'native')
                self.assertEqual(prepared['seat_timeouts'], {'1': {k: spec[k] for k in ('timeout', 'first_timeout')}})
                self.assertEqual(prepared['seat_entries'], {'1': spec['entry']})
                self.assertEqual(prepared['learning']['sides']['1']['teacher_identity'], execution_identity(spec, 'native'))
                self.assertEqual(prepared['learning']['sides']['2']['dagger_entry'], spec['entry'])
                self.assertNotIn('teacher_identity', job['learning']['sides']['1'])
                wrong = copy.deepcopy(job)
                wrong['teacher_roles']['supervision']['entry'] = 'wrong'
                with self.assertRaisesRegex(ValueError, 'descriptor'): prepare_job(wrong, 'native')
                wrong = copy.deepcopy(job)
                wrong['learning']['dagger_teacher'] = 'another.zip'
                with self.assertRaisesRegex(ValueError, 'supervision'): prepare_job(wrong, 'native')

    def test_late_first_query_gets_its_own_budget_and_loading_is_included(self):
        lua = query_runtime()
        lua.execute('''
            for _=1,3 do assert(teacher.query(data,obs,candidates,scores,training)==nil) end
            load_ms=400;plan_ms=1600
            first=teacher.query(data,obs,candidates,scores,training)
            load_ms=30000;plan_ms=100
            for _=1,4 do second=teacher.query(data,obs,candidates,scores,training) or second end
        ''')
        self.assertEqual(lua.eval('first.query_budget'), 20)
        self.assertEqual(lua.eval('first.query_ms'), 2000)
        self.assertTrue(lua.eval('first.first_query'))
        self.assertEqual(lua.eval('second.query_budget'), 2)
        self.assertFalse(lua.eval('second.first_query'))
        self.assertEqual(lua.eval('loads'), 1)
        self.assertEqual(lua.eval('loaded_entry'), 'frozen/duel/bot.lua')
        self.assertEqual(lua.eval('first.choice'), 0)
        self.assertEqual(lua.eval('first.actual.weapon'), 2)
        self.assertEqual(lua.eval('first.source'), 'teacher')
        self.assertEqual(lua.eval('data.teacher_ledger.public.owners[2002]'), 1)
        self.assertEqual(lua.eval('data.teacher_ledger.home.actor[1]'), 2)

    def test_public_memory_is_per_seat_and_retains_only_legal_history(self):
        lua = query_runtime()
        lua.execute('''
            teacher.observe(data,obs)
            other={};teacher.observe(other,{side=2,own={},occupied={},memory={villages={}},tiles={}})
            obs.occupied['3,2']=nil;obs.tiles['3,2'].visible=false
            teacher.observe(data,obs);remembered=data.teacher_ledger.public.last_seen.enemy~=nil
            obs.tiles['3,2'].visible=true;teacher.observe(data,obs)
        ''')
        self.assertTrue(lua.eval('remembered'))
        self.assertIsNone(lua.eval('data.teacher_ledger.public.last_seen.enemy'))
        self.assertEqual(lua.eval('data.teacher_ledger.public.terrain[2002]'), 'Kh')
        self.assertIsNone(lua.eval('other.teacher_ledger.public.terrain[2002]'))
        self.assertIsNone(lua.eval('data.teacher_ledger.public.terrain[9009]'))

    def test_query_failures_are_invalid_without_fallback_and_restore_guards(self):
        for failure in ('load_failure', 'fail_action', 'fail_rng', 'timeout'):
            lua = query_runtime()
            lua.execute("teacher.observe(data,obs);"+('plan_ms=20001' if failure=='timeout' else failure+'=true'))
            lua.execute('plan,result=teacher.plan(data,training);ai.move();mathx.random()')
            self.assertIsNone(lua.eval('plan'))
            self.assertEqual(lua.eval('result.choice'), -1)
            self.assertTrue(lua.eval('result.error'))
            self.assertEqual(lua.eval('loads'), 1)
            self.assertEqual(lua.eval('real_actions'), 1)
            self.assertEqual(lua.eval('draws'), 1)

    def test_watchdog_preserves_student_time_and_never_forgives_expiry(self):
        clock = QueryClock()
        deadline = clock.begin(101, 100.6, 20)
        self.assertEqual(deadline, 120.6)
        self.assertAlmostEqual(clock.end(deadline, 102), 102.4)
        deadline = clock.begin(104, 103, 2)
        self.assertEqual(clock.end(deadline, 106), 105)
        with self.assertRaises(ValueError): clock.end(110, 107)
        self.assertEqual(QueryClock().begin(100, 101, 20), 100)

    def test_unmatched_query_keeps_actual_intent_and_error_never_becomes_label(self):
        actual = dict(kind='recruit', type='Spearman', x=2, y=3)
        records = [dict(choice=0, actual={'kind': 'end_turn'}, dagger=dict(choice=-1, actual=actual, query_only=True, query_ms=7)),
                   dict(choice=0, dagger=dict(error='teacher query timeout', choice=-1, query_ms=2001)),
                   dict(choice=0)]
        rows = dagger_rows(records, dict(teacher_contract=1, teacher='selected_teacher'))
        self.assertEqual(rows[0]['actual'], actual)
        self.assertEqual([r['choice'] for r in rows], [-1]*3)
        self.assertEqual({r['teacher'] for r in rows}, {'selected_teacher'})
        self.assertEqual(rows[1]['teacher_query']['error'], 'teacher query timeout')
        metrics = query_metrics(records)
        self.assertEqual((metrics['queries'], metrics['valid'], metrics['unmatched']), (2, 0, 1))
        self.assertEqual(metrics['errors'], ['teacher query timeout'])

    def test_collector_receives_per_seat_budget(self):
        from learning.sample import play_job
        with patch('learning.sample.match.play_game', side_effect=RuntimeError('fixture stop')) as play:
            result = play_job(dict(id='fixture', output='unused', deadline=1e12, bots=['baseline']*2,
                                   factions=['Rebels', 'Loyalists'], seed=1, wesnoth='fixture',
                                   seat_timeouts={'1': {'timeout': 2, 'first_timeout': 20}}))
        self.assertEqual(play.call_args.kwargs['seat_timeouts']['1']['timeout'], 2)
        self.assertEqual(result['status'], 'infrastructure_error')


if __name__ == '__main__':
    unittest.main()
