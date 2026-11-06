import unittest
from tests.test_search_teacher import load_teacher


class TeacherUCTTests(unittest.TestCase):
    def test_stochastic_bandit_converges_with_a_repeatable_private_stream(self):
        lua,_=load_teacher();lua.globals().uct=lua.globals().load_module('uct.lua')
        lua.execute('''
            math.random=function() error('real game RNG forbidden') end
            root={id='root',side=1};arms={{key='risky'},{key='sure'}}
            model={players=2,key=function(n) return n.id end,player=function(n) return n.side end,
                terminal=function(n) return n.value~=nil end,actions=function(n) return arms end,
                evaluate=function(n,side) return (n.value or 0)*(side==1 and 1 or -1) end,
                apply=function(n,a,rng)
                    local value=a.key=='sure' and 4000 or (rng()<.2 and 10000 or 0)
                    return {id=tostring(value),side=2,value=value}
                end}
            cfg={mc_iterations=1800,mc_depth=1}
            first,first_stats=uct.solve(root,model,cfg,never,geometry.random(361))
            second,second_stats=uct.solve(root,model,cfg,never,geometry.random(361))
            expired,expired_stats=uct.solve(root,model,cfg,function() return true end,geometry.random(361))
        ''')
        self.assertEqual(lua.eval('first.key'),'sure')
        self.assertEqual(lua.eval('second.key'),'sure')
        self.assertEqual(lua.eval('first_stats.simulations'),1800)
        self.assertEqual(dict(lua.eval('first_stats.root_visits')),dict(lua.eval('second_stats.root_visits')))
        self.assertEqual(lua.eval('expired.key'),'risky')
        self.assertEqual(lua.eval('expired_stats.simulations'),0)

    def test_ffa_opponent_optimizes_its_own_utility_not_a_coalition(self):
        lua,_=load_teacher();lua.globals().uct=lua.globals().load_module('uct.lua')
        lua.execute('''
            root={id='root',side=1,values={0,0,0}}
            safe={id='safe',side=1,values={40000,0,0},leaf=true}
            branch={id='branch',side=2,values={0,0,0}}
            selfish={id='selfish',side=2,values={80000,90000,10000},leaf=true}
            coalition={id='coalition',side=2,values={10000,50000,90000},leaf=true}
            root.arms={{key='safe',child=safe},{key='branch',child=branch}}
            branch.arms={{key='coalition',child=coalition},{key='selfish',child=selfish}}
            model={players=3,key=function(n) return n.id end,player=function(n) return n.side end,
                terminal=function(n) return n.leaf end,actions=function(n) return n.arms end,
                evaluate=function(n,side) return n.values[side] end,apply=function(n,a) return a.child end}
            choice,stats=uct.solve(root,model,{mc_iterations=4000,mc_depth=2,ucb=.3},never,geometry.random(88))
        ''')
        self.assertEqual(lua.eval('choice.key'),'branch')
        self.assertTrue(lua.eval('stats.root_covered'))

    def test_local_combat_sampling_is_repeatable_and_does_not_change_public_state(self):
        lua,_=load_teacher()
        lua.execute('''
            math.random=function() error('real game RNG forbidden') end
            wesnoth.simulate_combat=function() error('live forecast forbidden') end
            a=unit('a',1,2,2,20,8,3);b=unit('b',2,2,3,20,7,3)
            a.defense.Gg=50;b.defense.Gg=50;s=board{a,b}
            config.algorithm='uct';config.mc_iterations=48;config.mc_depth=4;config.reply_width=2
            choices=actions.generate(s,config,never,true)
            before=s.units.a.hp..':'..s.units.b.hp
            first,one=search.choose(s,choices,config,never)
            second,two=search.choose(s,choices,config,never)
            after=s.units.a.hp..':'..s.units.b.hp
        ''')
        self.assertEqual(lua.eval('one.algorithm'),'uct')
        self.assertEqual(lua.eval('one.simulations'),48)
        self.assertGreater(lua.eval('one.sampled_combats'),0)
        self.assertEqual(lua.eval('first.key'),lua.eval('second.key'))
        self.assertEqual(dict(lua.eval('one.root_visits')),dict(lua.eval('two.root_visits')))
        self.assertEqual(lua.eval('before'),lua.eval('after'))


if __name__=='__main__':
    unittest.main()
