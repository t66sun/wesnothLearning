import unittest
from tests.test_search_teacher import load_teacher


class TeacherHybridTests(unittest.TestCase):
    def test_strategic_actions_and_expired_search_keep_the_beam_result(self):
        lua,_=load_teacher()
        lua.execute('''
            monte=load_module('monte_search.lua')
            monte.choose=function() error('unexpected Monte Carlo search') end
            search.beam=function(s,a) return a[1],{nodes=1,depth=2,value=3} end
            config.algorithm='hybrid'
            recruit,one=search.choose({},{{kind='recruit',key='recruit'}},config,never)
            expired,two=search.choose({},{{kind='combat',key='combat'}},config,function() return true end)
        ''')
        self.assertEqual(lua.eval('recruit.key'),'recruit')
        self.assertEqual(lua.eval('expired.key'),'combat')
        self.assertEqual(lua.eval('one.algorithm'),'hybrid')
        self.assertEqual(lua.eval('one.simulations'),0)
        self.assertEqual(lua.eval('two.simulations'),0)

    def test_combat_override_requires_coverage_visits_and_utility_margin(self):
        lua,_=load_teacher()
        lua.execute('''
            first={kind='combat',key='first'};second={kind='combat',key='second'}
            ending={kind='end_turn',key='end'};mc_visits=3;mc_value=.55;covered=true
            monte=load_module('monte_search.lua')
            monte.choose=function(s,roots)
                assert(#roots==3 and roots[1]==first and roots[3]==ending)
                return second,{nodes=12,depth=4,simulations=9,sampled_combats=10,utility=mc_value,
                    root_covered=covered,root_visits={first=3,second=mc_visits,['end']=3},
                    root_values={first=.5,second=mc_value,['end']=.3}}
            end
            search.beam=function() return first,{nodes=2,depth=2,value=3} end
            config.algorithm='hybrid';local roots={first,second,ending}
            changed,one=search.choose({},roots,config,never)
            mc_visits=2;few=search.choose({},roots,config,never)
            mc_visits=3;mc_value=.515;small=search.choose({},roots,config,never)
            mc_value=.55;covered=false;incomplete=search.choose({},roots,config,never)
        ''')
        self.assertEqual(lua.eval('changed.key'),'second')
        self.assertTrue(lua.eval('one.hybrid_replaced'))
        self.assertIsNone(lua.eval('one.value'))
        for name in ('few','small','incomplete'):
            self.assertEqual(lua.eval(name+'.key'),'first')

    def test_local_combat_refinement_uses_repeatable_private_sampling(self):
        lua,_=load_teacher()
        lua.execute('''
            math.random=function() error('real game RNG forbidden') end
            wesnoth.simulate_combat=function() error('live forecast forbidden') end
            a=unit('a',1,2,2,20,8,3);b=unit('b',2,2,3,20,7,3)
            a.defense.Gg=50;b.defense.Gg=50;s=board{a,b}
            config.algorithm='hybrid';config.mc_iterations=48;config.mc_depth=4;config.reply_width=2
            choices=actions.generate(s,config,never,true)
            first,one=search.choose(s,choices,config,never)
            second,two=search.choose(s,choices,config,never)
        ''')
        self.assertEqual(lua.eval('one.algorithm'),'hybrid')
        self.assertEqual(lua.eval('one.simulations'),48)
        self.assertGreater(lua.eval('one.sampled_combats'),0)
        self.assertEqual(lua.eval('first.key'),lua.eval('second.key'))
        self.assertEqual(dict(lua.eval('one.root_visits')),dict(lua.eval('two.root_visits')))
        self.assertEqual(lua.eval('s.units.a.hp'),20)
        self.assertEqual(lua.eval('s.units.b.hp'),20)


if __name__=='__main__':
    unittest.main()
