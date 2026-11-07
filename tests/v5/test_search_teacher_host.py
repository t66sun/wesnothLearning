"""Frozen teacher code on the actual Rust/Lua host; no optimizer or training."""
import copy
import json
import tempfile
import time
import unittest
from pathlib import Path

from learning.adapters import LiteAdapter
from learning.lite_host import LiteHost, host_modules, teacher_candidate
from learning.teachers.registry import freeze_set
from tests.v5 import helpers

FIXTURE = '~add-ons/fixture/lua/bot.lua'


class SearchTeacherHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.contract = freeze_set(Path(cls.directory.name)/'teachers', 'mixed-20261107')

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def core(self, fmt='duel', *, spec=None, rules=None, extra=None):
        from _engine_lite import LiteEngine
        chosen = self.contract['formats'][fmt]['supervision']
        if spec is None:
            spec = helpers.spec(sides=2 if fmt=='duel' else 4, fog=False)
            for side in spec['sides']:
                side['gold'] = 0
                if fmt=='ffa4': side['team'] = str(side['id'])
        modules = host_modules(teacher_specs=[chosen])
        modules.update(extra or {})
        core = LiteEngine(json.dumps(rules or helpers.rules()),json.dumps(spec))
        core.configure_host(json.dumps(modules))
        return core, spec, chosen

    def wrapped(self, core, spec, teacher=None, query=None):
        host = LiteHost.__new__(LiteHost)
        host.adapter = LiteAdapter.__new__(LiteAdapter)
        host.adapter.core, host.adapter.spec = core, spec
        host.teacher_specs = teacher or {}
        host.query_spec = query
        host.calls, host.queries = {}, {}
        return host

    def test_frozen_strategies_plan_execute_and_restore_on_all_formats(self):
        for fmt in ('duel','ffa4','team2v2'):
            with self.subTest(format=fmt):
                core, spec, teacher = self.core(fmt)
                core.begin_call(teacher['first_timeout'])
                before = json.loads(core.snapshot())['game']
                decision = json.loads(core.decision(1,True,teacher_entry=teacher['entry']))
                self.assertEqual(json.loads(core.snapshot())['game'], before)
                core.end_call()
                saved = core.snapshot()
                core.restore(saved)
                again = json.loads(core.decision(1,True,teacher_entry=teacher['entry']))
                self.assertEqual(again['teacher_action'], decision['teacher_action'])
                action = teacher_candidate(again['teacher_action'])
                core.begin_call(teacher['timeout'])
                result = json.loads(core.execute_candidate(json.dumps(action)))
                core.end_call()
                self.assertTrue(result['committed'])
                core.restore(saved)
                self.assertEqual(json.loads(core.snapshot())['game'], before)

    def test_full_paths_isolate_same_named_modules_and_selected_configs(self):
        core, _, _ = self.core(extra={
            '~add-ons/a/lua/config.lua': 'return {value=11}',
            '~add-ons/b/lua/config.lua': 'return {value=22}',
            FIXTURE: '''
local a=wesnoth.require '~add-ons/a/lua/config.lua'
local b=wesnoth.require '~add-ons/b/lua/config.lua'
assert(a.value==11 and b.value==22 and a~=b)
local duel=wesnoth.require '~add-ons/selected_teacher/lua/duel/config.lua'
local team=wesnoth.require '~add-ons/selected_teacher/lua/team2v2/config.lua'
assert(duel~=team and team.algorithm=='pvs')
return {evaluation=function() return 0 end}
'''})
        self.assertEqual(json.loads(core.teacher_query(1,FIXTURE,1))['teacher_action']['kind'],'end_turn')

    def test_templates_schedule_and_supported_ability_fields(self):
        rules=helpers.rules()
        rules['lawful_bonus']=[25,0,-25]
        unit=rules['units']['Fighter']
        unit.update(abilities=['healing','regenerates','steadfast'], healing_amount=4,healing_poison='slowed',
                    regeneration_amount=8,regeneration_poison='cured')
        unit['resistance']['blade']=80
        unit['weapons'][0].update(accuracy=13,parry=5,defense_weight=.5)
        spec=helpers.spec(max_turns=7)
        core,_,_=self.core(spec=spec,rules=rules,extra={FIXTURE: '''
return {evaluation=function(self,cfg,data)
    assert(wesnoth.scenario.turns==7)
    assert(wesnoth.schedule.get_time_of_day(nil,2).lawful_bonus==0)
    assert(wesnoth.schedule.get_time_of_day(nil,3).lawful_bonus==-25)
    local u=wesnoth.units.create{type='Fighter',side=1,id='template'}
    assert(u.x==nil and u.y==nil and u.id=='template')
    local abilities=wml.get_child(u.__cfg,'abilities')
    assert(wml.get_child(abilities,'heals').value==4)
    assert(wml.get_child(abilities,'heals').poison=='slowed')
    assert(wml.get_child(abilities,'regenerate').value==8)
    assert(wml.get_child(abilities,'regenerate').poison=='cured')
    assert(wml.get_child(abilities,'resistance').id=='steadfast')
    assert(u:resistance_against('blade',true)==20 and u:resistance_against('blade',false)==40)
    assert(u.attacks[1].accuracy==13 and u.attacks[1].parry==5 and u.attacks[1].defense_weight==.5)
    assert(#wesnoth.units.find_on_map{id='template'}==0)
    return 0
end}
'''})
        before=json.loads(core.snapshot())['game']
        core.teacher_query(1,FIXTURE,1)
        self.assertEqual(json.loads(core.snapshot())['game'],before)

    def test_hard_query_deadline_interrupts_lua_and_restores_student_budget(self):
        core,_,_=self.core(extra={FIXTURE:'return {evaluation=function() while true do end end}'})
        saved=core.snapshot();before=json.loads(saved)['game']
        core.begin_call(.04)
        started=time.perf_counter()
        with self.assertRaisesRegex(ValueError,'hard deadline'):
            core.teacher_query(1,FIXTURE,.12)
        self.assertLess(time.perf_counter()-started,1)
        # Query exceeds the student's entire allowance; its paused remainder
        # must still permit execution after the failed label is discarded.
        result=json.loads(core.execute_candidate(json.dumps({'kind':'end_turn'})))
        self.assertTrue(result['committed'])
        core.end_call()
        core.restore(saved)
        core.begin_call(.001)
        time.sleep(.005)
        with self.assertRaisesRegex(ValueError,'hard deadline'):
            core.execute_candidate(json.dumps({'kind':'end_turn'}))
        core.end_call(False)
        self.assertEqual(json.loads(core.snapshot())['game'],before)

    def test_a_single_native_forecast_is_interrupted_inside_probability_propagation(self):
        rules=helpers.rules()
        for unit in rules['units'].values():
            unit['hp']=10000
            for weapon in unit['weapons']:
                weapon.update(damage=1,strikes=100,specials=['berserk','poison','slow'])
        state=helpers.spec(fog=False)
        for unit in state['units']:unit['hp']=10000
        core,_,_=self.core(spec=state,rules=rules,extra={FIXTURE: '''
return {evaluation=function()
    local a=wesnoth.units.find_on_map{id='p1'}[1]
    local d=wesnoth.units.find_on_map{id='e1'}[1]
    wesnoth.simulate_combat(a,1,d)
end}
'''})
        before=json.loads(core.snapshot())['game']
        started=time.perf_counter()
        with self.assertRaisesRegex(ValueError,'inside native operation'):
            core.teacher_query(1,FIXTURE,.08)
        self.assertLess(time.perf_counter()-started,1)
        self.assertEqual(json.loads(core.snapshot())['game'],before)
        # The callback-scoped deadline cannot leak into later, untimed APIs.
        self.assertTrue(json.loads(core.legal_actions(1)))

    def test_wrong_format_entry_budget_and_reset_are_rejected(self):
        core,state,teacher=self.core()
        before=core.snapshot()
        host=self.wrapped(core,state,query=teacher)
        host.validate_teachers(state)
        for key,value in [('format','team2v2'),('entry',teacher['entry'].replace('/duel/','/team2v2/')),('timeout',999)]:
            host.query_spec=dict(teacher,**{key:value})
            with self.assertRaisesRegex(ValueError,'descriptor differs'):host.validate_teachers(state)
        host.query_spec=teacher
        with self.assertRaisesRegex(ValueError,'descriptor differs'):host.reset(helpers.spec(sides=4))
        self.assertEqual(core.snapshot(),before)

    def test_query_cannot_execute_and_failure_does_not_poison_later_execution(self):
        core,_,_=self.core(extra={FIXTURE: '''
return {evaluation=function()
    local actor=wesnoth.units.find_on_map{side=1}[1]
    local enemy=wesnoth.units.find_on_map{side=2}[1]
    ai.attack(actor,enemy,1)
end}
'''})
        before=json.loads(core.snapshot())['game']
        with self.assertRaisesRegex(ValueError,'planning cannot execute'):
            core.teacher_query(1,FIXTURE,1)
        self.assertEqual(json.loads(core.snapshot())['game'],before)
        core.decision(1,False)
        result=json.loads(core.execute_candidate(json.dumps({'kind':'end_turn'})))
        self.assertTrue(result['committed'])

    def test_first_query_is_independent_and_snapshot_restores_call_counts(self):
        core,spec,teacher=self.core()
        host=self.wrapped(core,spec,query=teacher)
        for _ in range(3):
            host.begin_call(1);host.decision(1);host.end_call()
        self.assertEqual(host.begin_call(1),1)
        first=host.query_teacher(1)
        host.end_call()
        self.assertNotIn('error',first)
        self.assertEqual(first['query_budget'],20)
        saved=host.snapshot()
        second=host.query_teacher(1)
        self.assertEqual(second['query_budget'],2)
        self.assertFalse(second['first_query'])
        host.restore(saved)
        self.assertEqual(host.snapshot(),saved)
        self.assertEqual(host.query_teacher(1)['query_budget'],2)
        host.reset(spec)
        self.assertEqual(host.query_teacher(1)['query_budget'],20)

    def test_public_memory_is_separate_for_two_team_seats(self):
        core,_,teacher=self.core('team2v2')
        core.teacher_query(1,teacher['entry'],20)
        core.teacher_query(3,teacher['entry'],20)
        state=json.loads(core.snapshot())['host']['teacher_memory']
        self.assertIn('p1',state['1']['public']['homes'])
        self.assertNotIn('p1',state['3']['public']['homes'])
        self.assertIn('a1',state['3']['public']['homes'])
        core.restore(core.snapshot())
        self.assertEqual(json.loads(core.snapshot())['host']['teacher_memory'],state)

    def test_unknown_terrain_hidden_unit_and_referee_rng_do_not_change_decision(self):
        width,height=24,16
        terrain=['Gg']*(width*height)
        terrain[2*width+2]='Gg^Kh';terrain[14*width+22]='Gg^Kh'
        units=[helpers._unit('own','Fighter',1,2,2,width=width,leader=True),
               helpers._unit('hidden','Fighter',2,22,14,width=width,leader=True)]
        spec=helpers.spec(width=width,height=height,terrain=terrain,units=units,fog=True,shroud=True)
        for side in spec['sides']:side['gold']=0
        changed=copy.deepcopy(spec)
        changed['seed']=777;changed['units'][1]['hp']=1;changed['terrain'][-1]='Ww'
        outputs=[]
        for state in (spec,changed):
            core,_,teacher=self.core(spec=state)
            before=json.loads(core.snapshot())['game']
            view=json.loads(core.observe(1))
            plan=json.loads(core.teacher_query(1,teacher['entry'],20))
            self.assertEqual(json.loads(core.snapshot())['game'],before)
            outputs.append((view,plan))
        self.assertEqual(*outputs)


if __name__=='__main__':
    unittest.main()
