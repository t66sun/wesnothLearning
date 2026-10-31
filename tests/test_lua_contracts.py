import json
import unittest
from lupa import LuaRuntime
from learning.common import ROOT
from learning.features import schema
import native


def initialize():
    lua=LuaRuntime(unpack_returned_tuples=True)
    lua.execute((ROOT/'tests/lua_fixture.lua').read_text())
    modules={'features.lua':lua.eval(native.lua(schema()))}
    def load(path):
        name=path.rsplit('/',1)[-1]
        if name not in modules:
            modules[name]=lua.execute((ROOT/'lua'/name).read_text())
        return modules[name]
    lua.globals().load_module=load
    lua.execute('wesnoth.require=function(path) return load_module(path) end')
    for name in ('observation.lua','candidates.lua','network.lua','routing.lua'):
        load(name)
    return lua,modules


class LuaContractTests(unittest.TestCase):
    def test_time_limit_observation_reads_current_schedule(self):
        lua,modules=initialize()
        lua.execute('''
            wesnoth.current.turn=31
            wesnoth.schedule.get_time_of_day=function(...)
                assert(select('#',...)>=1,'schedule expected, got no value')
                local _,turn=...
                if turn and turn>30 then error('turn number out of range') end
                return {lawful_bonus=25}
            end
        ''')
        obs=modules['observation.lua'].capture(lua.table(),1)
        self.assertIsNotNone(obs['potential'])
        self.assertEqual(len(obs['global']),len(schema()['global_features']))

    def test_teacher_path_steps_are_one_intent_and_noops_are_not_labels(self):
        lua,modules=initialize();lua.execute('records={}')
        modules['config.lua']=lua.eval('{}')
        modules['runtime.lua']=lua.eval('{emit=function(kind,row) records[#records+1]=row end}')
        lua.execute('''
            ai.move=function(u,p)
                u.x=p[1];u.y=p[2];u.moves=u.moves-1
                return {ok=true,gamestate_changed=true}
            end
            ai.move_full=function(u,p)
                u.x=p[1];u.y=p[2];u.moves=0
                return {ok=true,gamestate_changed=true}
            end
        ''')
        collector=lua.execute((ROOT/'learning/collector.lua').read_text(encoding='utf-8-sig'))
        lua.execute('fixture.judge=true')
        undo=collector.wrap(lua.table(),lua.eval('{teacher="gpt6astra",version="fixture"}'))
        lua.execute('ai.move(fixture.own[1],{2,2});ai.move_full(fixture.own[1],{3,2})')
        undo(True)
        rows=lua.globals().records
        self.assertEqual(len(rows),1);self.assertEqual(rows[1]['microsteps'],2)
        self.assertEqual(rows[1]['actual']['x'],1);self.assertEqual(rows[1]['actual']['tx'],3)
        self.assertGreaterEqual(rows[1]['choice'],0)
        lua.execute('ai.move=function() return {ok=true,gamestate_changed=false} end')
        undo=collector.wrap(lua.table(),lua.eval('{teacher="gpt6astra",version="fixture"}'))
        lua.execute('ai.move(fixture.own[1],{3,2})');undo(True)
        self.assertEqual(len(rows),1)

    def test_opening_route_cached_after_elimination_and_lazy_weights(self):
        for teams,expected in [([1,2],'duel'),([1,2,3,4],'ffa4'),([1,2,1,2],'team2v2'),([1,2,3],'ffa4'),(list(range(1,10)),'ffa4')]:
            lua,modules=initialize();R=modules['routing.lua']
            lua.globals().newteams=lua.eval(native.lua(teams))
            lua.execute('fixture.teams=newteams; wesnoth.sides={};for i=1,#newteams do wesnoth.sides[i]={controller="ai"} end;wesnoth.sides.is_enemy=function(a,b) return fixture.teams[a]~=fixture.teams[b] end')
            memory=lua.table();self.assertEqual(R.select(memory),expected)
            lua.execute('fixture.leaders={};wesnoth.sides[1].controller="null"')
            self.assertEqual(R.select(memory),expected)
        lua,modules=initialize();R=modules['routing.lua']
        lua.execute('fixture.teams={1,1,1,2}')
        with self.assertRaises(Exception): R.select(lua.table())
        lua,modules=initialize();loaded=[]
        modules['config.lua']=lua.eval('{mode="greedy",version="fixture"}')
        modules['weights_team2v2.lua']=lua.table()
        modules['network.lua']=lua.eval('{forward=function() return {0},0 end, choose=function() return 1,0 end, commit=function() end}')
        def require(path):
            name=path.rsplit('/',1)[-1];loaded.append(name)
            if name not in modules:
                modules[name]=lua.execute((ROOT/'lua'/name).read_text())
            return modules[name]
        lua.globals().load_module=require
        bot=lua.execute((ROOT/'lua/bot.lua').read_text());data=lua.table()
        self.assertNotIn('weights_team2v2.lua',loaded)
        bot.evaluation(bot,lua.table(),data);bot.evaluation(bot,lua.table(),data)
        self.assertEqual([n for n in loaded if n.startswith('weights_')],['weights_team2v2.lua'])

    def test_far_village_hop_and_unit_identity_survive_selection(self):
        lua,modules=initialize();C=modules['candidates.lua'];O=modules['observation.lua']
        lua.execute('''
            fixture.own={fixture.own[1]};fixture.visible=fixture.own
            fixture.own[1].x=1;fixture.own[1].y=1
            fixture.owners['2,2']=1
            wesnoth.map.find=function(filter) return filter.terrain and {} or {{2,2},{12,1}} end
            wesnoth.paths.find_reach=function(u,cfg) return {{1,1,4},{2,1,3},{3,1,2},{4,1,1}} end
            wesnoth.paths.find_path=function(u,x,y,cfg) local p={};for i=1,x do p[#p+1]={i,1} end;return p,11 end
        ''')
        obs=O.capture(lua.table());actions,_=C.generate(obs,200)
        self.assertTrue(any(a['kind']=='move' and a['tx']==4 and a['ty']==1 and a['goal_x']==12 for _,a in actions.items()))
        lua.execute("wesnoth.unit_types['Elvish Fighter']={cost=14};wesnoth.unit_types.Wose={cost=14};fixture.own[1].type='Elvish Fighter'")
        a,_=C.generate(O.capture(lua.table()),200)
        first=next(v for _,v in a.items() if v['kind']=='move')['features']
        lua.execute("fixture.own[1].type='Wose';fixture.own[1].attacks={{damage=25,number=2,type='impact',range='melee'}}")
        b,_=C.generate(O.capture(lua.table()),200)
        second=next(v for _,v in b.items() if v['kind']=='move')['features']
        self.assertNotEqual(first[len(first)],second[len(second)])
        self.assertNotEqual(self.to_python(first),self.to_python(second))

    def test_ambush_reobserves_and_illegal_move_still_fails(self):
        lua,modules=initialize();C=modules['candidates.lua']
        action=lua.eval('{kind="move_attack",x=1,y=1,tx=2,ty=2,ex=3,ey=2,weapon=1}')
        lua.execute('ai.move=function() return {ok=false,gamestate_changed=true,status=2005} end')
        C.execute(action)
        self.assertEqual(len(lua.globals().fixture.calls),0)
        lua.execute('ai.move=function() return {ok=false,gamestate_changed=false,status=2008} end')
        with self.assertRaises(Exception): C.execute(action)

    def test_hidden_units_and_village_ownership_do_not_change_features(self):
        lua,modules=initialize();O=modules['observation.lua'];C=modules['candidates.lua']
        lua.execute("fixture.fog['4,4']=true; fixture.owners['4,4']=2")
        def capture():
            obs=O.capture(lua.table());actions,timing=C.generate(obs,450)
            return native.lua(self.to_python(obs['global'])),native.lua(self.to_python(obs['opponents'])),native.lua(self.to_python(actions))
        before=capture()
        lua.execute("fixture.hidden={{side=2,x=90,y=90,hitpoints=999}};fixture.owners['4,4']=4")
        self.assertEqual(before,capture())

    def test_all_action_kinds_and_visible_team_support(self):
        lua,modules=initialize();obs=modules['observation.lua'].capture(lua.table())
        self.assertEqual(len(obs['opponents']),2)
        self.assertEqual(obs['global'][17],1/8)
        self.assertEqual(obs['global'][18],1/40)
        actions,timing=modules['candidates.lua'].generate(obs,450)
        kinds={a['kind'] for _,a in actions.items()}
        self.assertEqual(kinds,{'end_turn','recruit','move','attack','move_attack'})
        self.assertLessEqual(len(actions),37)
        for _,action in actions.items():
            if action['kind']!='move_attack': modules['candidates.lua'].execute(action)
        move_attack=next(a for _,a in actions.items() if a['kind']=='move_attack')
        lua.globals().moving=move_attack
        lua.execute('local a=moving;for _,u in ipairs(fixture.visible) do if u.x==a.x and u.y==a.y then u.x=a.tx;u.y=a.ty;break end end')
        modules['candidates.lua'].execute(move_attack)
        self.assertIn('attack',[v for _,v in lua.globals().fixture.calls.items()])

    def test_no_leader_keeps_end_turn(self):
        lua,modules=initialize();obs=modules['observation.lua'].capture(lua.table())
        obs['leader']=None
        actions,timing=modules['candidates.lua'].generate(obs)
        self.assertEqual(len(actions),1);self.assertEqual(actions[1]['kind'],'end_turn')
        self.assertEqual(timing['budget'],'work-12000-v5')

    def test_deployed_bot_scores_every_shared_candidate(self):
        def run():
            lua,modules=initialize()
            modules['config.lua']=lua.eval(native.lua(dict(mode='greedy',version='fixture')))
            modules['weights_team2v2.lua']=lua.table()
            lua.execute('seen={};'
                'wesnoth.paths.find_reach=function(u,cfg) return {{1,1,4},{2,1,3},{3,1,2},{4,1,1},{5,1,1}} end')
            modules['network.lua']=lua.eval('''{
                forward=function(w,g,opponents,candidates,spatial,memory,turn)
                    local row={}
                    for i,a in ipairs(candidates) do row[i]=(a.kind or '')..'@'..tostring(a.x)..','..tostring(a.y) end
                    seen[#seen+1]=row
                    local scores={}
                    for i=1,#candidates do scores[i]=i end
                    return scores,0
                end,
                choose=function(scores,sample,random) return #scores,0 end,
                commit=function() end}''')
            bot=lua.execute((ROOT/'lua/bot.lua').read_text());data=lua.table()
            bot.evaluation(bot,lua.table(),data)
            return list(lua.globals().seen[1].values()),data
        seen,data=run()
        candidates=list(data['learning_record']['candidates'].values())
        self.assertGreater(len(candidates),2,'the fixture must expose several candidates')
        self.assertEqual(len(seen),len(candidates))
        self.assertEqual([row.split('@')[0] for row in seen],[c['kind'] for c in candidates])
        self.assertEqual(data['learning_record']['choice'],len(candidates)-1)
        self.assertEqual(data['plan']['kind'],seen[-1].split('@')[0])

    def test_team_continues_after_one_leader_dies_and_ends_after_enemy_team(self):
        lua,modules=initialize()
        lua.execute('fixture.judge=true')
        runtime=lua.execute((ROOT/'vendor/arena/runtime/runtime.lua').read_text())
        options=dict(token='test',max_turns=30,teams=[1,2,1,2],lenient=False)
        runtime.setup(lua.eval(native.lua(options)))
        lua.execute('fixture.leaders[1]=false')
        runtime.check();self.assertFalse(bool(runtime.done()))
        lua.execute('fixture.leaders[2]=false;fixture.leaders[4]=false')
        runtime.check();self.assertTrue(runtime.done())

    def test_team_fault_forfeits_the_team(self):
        lua,modules=initialize()
        lua.execute('fixture.judge=true')
        runtime=lua.execute((ROOT/'vendor/arena/runtime/runtime.lua').read_text())
        runtime.setup(lua.eval(native.lua(dict(token='t',max_turns=30,teams=[1,2,1,2],lenient=False))))
        runtime.disqualify(1,'test fault')
        self.assertTrue(runtime.done())
        self.assertFalse(lua.globals().fixture.leaders[3])

    def test_replay_observer_queries_the_side_ai_instead_of_a_global(self):
        lua,modules=initialize()
        modules['config.lua']=lua.eval('{}')
        lua.execute('''
            local real_ai=ai
            collected={}
            std_print=function(line) collected[#collected+1]=line end
            wesnoth.custom_synced_commands={}
            wesnoth.sides[1].controller='human'
            wesnoth.sides.debug_ai=function(side) assert(side==1,'wrong side queried');return {ai=real_ai} end
            ai=nil
            setmetatable(_G,{__index=function(_,name) error("variable '"..name.."' must be assigned before being used") end})
        ''')
        observer=lua.execute((ROOT/'learning/replay_observer.lua').read_text())
        observer.setup(lua.eval(native.lua(dict(format='duel',expected_actions=1,source_sha256='x',observer_version=1,
            actions=[dict(kind='end_turn',side=1,index=0)]))))
        lua.execute('''
            wesnoth.custom_synced_commands.learning_observe({index=0})
            wesnoth.custom_synced_commands.learning_complete()
        ''')
        events=[json.loads(line.split('LEARNING_HUMAN ',1)[1]) for line in lua.eval('collected').values()]
        self.assertEqual([e['event'] for e in events],['sample','complete'])
        self.assertEqual((events[0]['record']['action_index'],events[0]['record']['choice']),(0,0))
        self.assertTrue(lua.eval('rawget(_G,"ai")==nil'),'the observer must not leak its AI table into the global scope')

    @staticmethod
    def to_python(value):
        if hasattr(value,'items'):
            items=list(value.items())
            if all(isinstance(k,int) for k,_ in items):
                return [LuaContractTests.to_python(value[i]) for i in range(1,len(value)+1)]
            return {k:LuaContractTests.to_python(v) for k,v in items}
        return value


if __name__=='__main__': unittest.main()
