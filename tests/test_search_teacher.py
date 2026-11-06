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
