"""Independent local-model and native-entry contracts; execute on Ubuntu."""
from pathlib import Path
import unittest
from lupa import LuaRuntime
from learning.common import ROOT


SOURCE = ROOT / 'learning/teachers/search_teacher'


def load_teacher():
    lua = LuaRuntime(unpack_returned_tuples=True)
    modules = {}

    def load(path):
        name = path.rsplit('/', 1)[-1]
        if name not in modules:
            modules[name] = lua.execute((SOURCE / 'lua' / name).read_text(encoding='utf-8'))
        return modules[name]

    lua.globals().load_module = load
    lua.execute('wesnoth={require=function(path) return load_module(path) end}')
    for name in ('geometry', 'combat', 'state', 'actions', 'search', 'execute', 'public'):
        lua.globals()[name] = load(name + '.lua')
    lua.execute('''
        function unit(id,side,x,y,hp,damage,strikes)
            return {id=id,type=id,side=side,x=x,y=y,hp=hp,max_hp=hp,cost=20,
                moves=0,max_moves=0,attacks_left=1,level=1,xp=0,max_xp=999,
                alignment='neutral',resistance={blade=0},movement={Gg=1},defense={Gg=0},
                weapons={{damage=damage,number=strikes or 1,type='blade',range='melee'}}}
        end
        function board(units,players)
            local s={units={},side=1,root_side=1,players=players or 2,turn=1,max_turns=30,
                terrain={},owners={},gold={[1]=0},villages={},castles={},keeps={},homes={},
                enemies={},adjustment={},recruits={},lawful_bonus=0}
            for x=1,7 do for y=1,7 do s.terrain[geometry.key(x,y)]='Gg' end end
            for side=1,s.players do s.enemies[side]={}
                for other=1,s.players do s.enemies[side][other]=side~=other end
            end
            for _,u in ipairs(units) do s.units[u.id]=u end
            return s
        end
        config={depth=2,width=6,root_width=18,reply_width=0,risk=.35}
        never=function() return false end
    ''')
    return lua, modules


class SearchTeacherTests(unittest.TestCase):
    def test_probability_distribution_and_query_immutability(self):
        lua, _ = load_teacher()
        lua.execute('''
            a=unit('a',1,2,2,5,5);d=unit('d',2,2,3,5,5)
            a.defense.Gg=40;d.defense.Gg=40;s=board{a,d}
            wesnoth.simulate_combat=function() error('live forecast forbidden') end
            f=combat.forecast(s,a,d,1)
        ''')
        f = lua.globals().f
        self.assertAlmostEqual(f['kill'], .6)
        self.assertAlmostEqual(f['death'], .24)
        self.assertAlmostEqual(f['ah'], 3.8)
        self.assertEqual(lua.eval('s.units.a.hp'), 5)
        self.assertEqual(lua.eval('s.units.d.hp'), 5)
        self.assertAlmostEqual(sum(row['p'] for row in f['states'].values()), 1)

    def test_slow_changes_retaliation_and_surviving_status(self):
        lua, _ = load_teacher()
        lua.execute('''
            a=unit('a',1,2,2,20,3);a.weapons[1].slow=true
            d=unit('d',2,2,3,20,7);s=board{a,d};f=combat.forecast(s,a,d,1)
            next_state=state.apply(s,{kind='combat',id='a',enemy='d',weapon=1,tx=2,ty=2})
        ''')
        self.assertEqual(lua.eval('f.ah'), 16)
        self.assertTrue(lua.eval('next_state.units.d.slow'))
        self.assertFalse(lua.eval('s.units.d.slow or false'))

    def test_poison_immunity_and_firststrike(self):
        lua, _ = load_teacher()
        lua.execute('''
            a=unit('a',1,2,2,5,5);a.weapons[1].poison=true
            d=unit('d',2,2,3,5,5);d.weapons[1].firststrike=true;d.unpoisonable=true
            f=combat.forecast(board{a,d},a,d,1)
        ''')
        self.assertEqual(lua.eval('f.death'), 1)
        self.assertEqual(lua.eval('f.kill'), 0)
        self.assertEqual(lua.eval('f.poison'), 0)

    def test_two_action_search_reverses_greedy_order(self):
        lua, _ = load_teacher()
        lua.execute('''
            slow=unit('slow',1,1,2,20,3);slow.cost=10;slow.weapons[1].slow=true
            hit=unit('hit',1,2,1,18,12,2);hit.cost=30
            enemy=unit('enemy',2,2,2,26,10,2);enemy.cost=100
            s=board{slow,hit,enemy};actions=actions.generate(s,config,never,true)
            greedy=actions[1]
            chosen,stats=search.choose(s,actions,config,never)
            config.depth=1;shallow=search.choose(s,actions,config,never)
        ''')
        self.assertEqual(lua.eval('greedy.id'), 'hit')
        self.assertEqual(lua.eval('shallow.id'), 'hit')
        self.assertEqual(lua.eval('chosen.id'), 'slow')
        self.assertEqual(lua.eval('stats.depth'), 2)

    def test_clone_reach_occupancy_and_rollback(self):
        lua, _ = load_teacher()
        lua.execute('''
            a=unit('a',1,2,2,20,5);a.moves=3;a.max_moves=3
            d=unit('d',2,4,2,20,5);s=board{a,d}
            reachable=state.reach(s,a,false)
            next_state=state.apply(s,{kind='move',id='a',tx=2,ty=3})
        ''')
        self.assertEqual(lua.eval('s.units.a.y'), 2)
        self.assertEqual(lua.eval('next_state.units.a.y'), 3)
        self.assertIsNone(lua.eval('reachable[geometry.key(4,2)]'))
        self.assertEqual(lua.eval('reachable[geometry.key(3,2)][3]'), 0)

    def test_expiry_returns_existing_legal_result(self):
        lua, _ = load_teacher()
        lua.execute('''
            s=board{unit('a',1,2,2,20,5),unit('d',2,2,3,20,5)}
            choices=actions.generate(s,config,never,true)
            picked,stats=search.choose(s,choices,config,function() return true end)
        ''')
        self.assertEqual(lua.eval('picked.key'), lua.eval('choices[1].key'))
        self.assertEqual(lua.eval('stats.depth'), 0)

    def test_search_randomness_is_independent_and_repeatable(self):
        lua, _ = load_teacher()
        lua.execute('''
            math.random=function() error('game random forbidden') end
            r1=geometry.random(123);r2=geometry.random(123);same=true
            for _=1,100 do if r1()~=r2() then same=false end end
        ''')
        self.assertTrue(lua.eval('same'))

    def test_reply_visits_every_ffa_seat_after_end_turn(self):
        lua, _ = load_teacher()
        lua.execute('''
            s=board({unit('a',1,2,2,20,5)},4);s.ffa=true;visited={}
            actions.generate=function(s)
                visited[#visited+1]=s.side
                return {{kind='end_turn',score=0,key='end_turn'}}
            end
            reply=search.reply(s,config,never)
        ''')
        self.assertEqual(lua.eval("table.concat(visited,',')"), '2,3,4')
        self.assertEqual(lua.eval('reply.side'), 1)

    def test_root_end_turn_does_not_skip_the_first_opponent(self):
        lua, _ = load_teacher()
        lua.execute('''
            s=board({unit('a',1,2,2,20,5)},4);s.ffa=true;visited={}
            actions.generate=function(s)
                visited[#visited+1]=s.side
                return {{kind='end_turn',score=0,key='end_turn'}}
            end
            ended=state.apply(s,{kind='end_turn'})
            reply=search.reply(ended,config,never)
        ''')
        self.assertEqual(lua.eval("table.concat(visited,',')"), '2,3,4')

    def test_slow_survives_enemy_turn_start_and_doubles_movement_cost(self):
        lua, _ = load_teacher()
        lua.execute('''
            own=unit('a',1,7,7,20,5);enemy=unit('b',2,2,2,20,5)
            enemy.max_moves=4;enemy.slow=true;s=board{own,enemy}
            t=state.apply(s,{kind='end_turn'});r=state.reach(t,t.units.b,false)
            ended=state.apply(t,{kind='end_turn'})
        ''')
        self.assertTrue(lua.eval('t.units.b.slow'))
        self.assertEqual(lua.eval('r[geometry.key(2,3)][3]'), 2)
        self.assertFalse(lua.eval('ended.units.b.slow'))

    def test_steadfast_applies_only_to_the_defending_target(self):
        lua, _ = load_teacher()
        lua.execute('''
            a=unit('a',1,2,2,20,10);d=unit('d',2,2,3,20,10)
            d.steadfast=true;d.resistance.blade=20;s=board{a,d}
        ''')
        self.assertEqual(lua.eval('combat.damage(s,a,d,a.weapons[1],true,false)'), 6)
        self.assertEqual(lua.eval('combat.damage(s,a,d,a.weapons[1],false,false)'), 8)

    def test_soft_expiry_returns_a_plan_without_faulting(self):
        lua, _ = load_teacher()
        lua.execute('''
            now=0;wesnoth.ms_since_init=function() return now end
            public.capture=function() now=1100;return {format='duel'},{} end
            actions.generate=function() return {{kind='end_turn',key='end_turn',score=0}},0 end
            search.choose=function(s,a) return a[1],{nodes=0,depth=0} end
            data={}
        ''')
        bot = lua.execute((SOURCE / 'lua/bot.lua').read_text())
        self.assertEqual(bot.evaluation(bot, lua.table(), lua.globals().data), 0)
        self.assertTrue(lua.eval('data.search.expired'))

    def test_reach_obeys_work_deadline(self):
        lua, _ = load_teacher()
        lua.execute('''
            a=unit('a',1,2,2,20,5);a.moves=20;s=board{a};checks=0
            r=state.reach(s,a,false,function() checks=checks+1;return checks>1 end)
            size=0;for _ in pairs(r) do size=size+1 end
        ''')
        self.assertLessEqual(lua.eval('size'), 7)

    def test_ffa_utility_does_not_merge_opponents(self):
        lua, _ = load_teacher()
        lua.execute('''
            s=board({unit('a',1,2,2,20,5),unit('b',2,3,2,20,5),unit('c',3,3,3,20,5)},4)
            s.ffa=true;before=state.value(s,2);s.units.c.hp=0;after=state.value(s,2)
            s.enemies[2][3]=false;allied=state.value(s,2)
        ''')
        self.assertGreater(lua.eval('after'), lua.eval('before'))
        self.assertNotEqual(lua.eval('allied'), lua.eval('after'))

    def test_unsupported_continuation_is_marked(self):
        lua, _ = load_teacher()
        lua.execute('''
            a=unit('a',1,2,2,20,5);a.weapons[1].berserk=true
            d=unit('d',2,2,3,20,5);s=board{a,d}
            t=state.apply(s,{kind='combat',id='a',enemy='d',weapon=1,tx=2,ty=2})
        ''')
        self.assertTrue(lua.eval('t.leaf_only'))

    def test_native_package_registration(self):
        import addons
        self.assertEqual(addons.validate(SOURCE), 'search_teacher')

    def test_public_capture_ignores_hidden_units_terrain_owners_and_rng(self):
        lua, _ = load_teacher()
        lua.execute('''
            wml={get_child=function() return nil end}
            local function native_unit(id,side,x,y)
                return {id=id,type='Fighter',side=side,x=x,y=y,hitpoints=30,max_hitpoints=30,
                    moves=0,max_moves=5,attacks_left=1,level=1,experience=0,max_experience=99,
                    alignment='neutral',cost=20,status={},__cfg={},
                    attacks={{damage=6,number=2,type='blade',range='melee',__cfg={}}},
                    resistance_against=function() return 0 end,
                    movement_on=function() return 1 end,defense_on=function() return 40 end}
            end
            own=native_unit('a',1,2,2);enemy=native_unit('b',2,3,2)
            hidden_hp=50;hidden_owner=2;hidden_terrain='Wo';hidden_rng=1
            wesnoth.units={find_on_map=function(filter)
                if filter.side then assert(filter.side==1);return {own} end
                assert(filter[1][1]=='filter_vision' and filter[1][2].side==1,'unfiltered query')
                return {own,enemy}
            end}
            wesnoth.current={side=1,turn=1,map=setmetatable({width=7,height=7},{__index=function(_,p)
                assert(p[1]~=7,'unexplored terrain read');return 'Gg'
            end})}
            wesnoth.scenario={turns=30}
            wesnoth.sides={{gold=0,recruit={}},{}}
            wesnoth.sides.is_enemy=function(a,b) return a~=b end
            wesnoth.sides.is_shrouded=function(side,x,y) return x==7 end
            wesnoth.sides.is_fogged=function(side,x,y) return x>=6 end
            wesnoth.map={find=function(filter)
                if filter.gives_income then return {{2,2},{6,2},{7,2}} end
                return {}
            end,get_owner=function(p) assert(p[1]<6,'hidden owner read');return 1 end}
            wesnoth.schedule={get_time_of_day=function() return {lawful_bonus=0} end}
            math.random=function() error('referee random read') end
            function inspect()
                local s=public.capture({},config)
                local aa=actions.generate(s,config,never,true);local keys={}
                for _,a in ipairs(aa) do keys[#keys+1]=a.key..':'..a.score end
                assert(not s.terrain[geometry.key(7,2)] and not s.owners[geometry.key(6,2)])
                return table.concat(keys,'|')
            end
            before=inspect();hidden_hp=1;hidden_owner=1;hidden_terrain='Mm';hidden_rng=999
            after=inspect()
        ''')
        self.assertEqual(lua.eval('before'), lua.eval('after'))

    def test_ambush_at_destination_prevents_followup_attack(self):
        lua, _ = load_teacher()
        lua.execute('''
            actor={id='a',side=1,x=1,y=2,moves=5};enemy={id='d',side=2,x=3,y=2}
            wesnoth.current={side=1};wesnoth.ms_since_init=function() return 0 end
            wesnoth.units={find_on_map=function(f) return f.side and {actor} or {actor,enemy} end}
            wesnoth.paths={find_path=function() return {{1,2},{2,2}} end}
            attacked=0;ai={check_move=function() return {ok=true} end,
                move=function(u,p) u.x=p[1];u.y=p[2];return {ok=false,status=2005} end,
                check_attack=function() return {ok=true} end,
                attack=function() attacked=attacked+1;return {ok=true} end}
            execute.run{kind='combat',id='a',tx=2,ty=2,enemy='d',weapon=1}
        ''')
        self.assertEqual(lua.eval('attacked'), 0)


if __name__ == '__main__':
    unittest.main()
