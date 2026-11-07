import unittest
from tests.test_search_teacher import load_teacher


class TeacherPVSTests(unittest.TestCase):
    def test_bot_keeps_search_and_combat_cache_diagnostics_separate(self):
        lua,_=load_teacher()
        lua.execute('''
            wesnoth.ms_since_init=function() return 0 end
            public.capture=function() return {format='duel'},{} end
            actions.generate=function() return {{kind='end_turn',key='end_turn',score=0}},0 end
            search.choose=function(s,a) return a[1],{nodes=8,depth=2,tt_hits=7,algorithm='pvs'} end
            combat.cache_stats=function() return 10,17 end
            data={};bot=wesnoth.require('~add-ons/search_teacher/lua/bot.lua');bot:evaluation({},data)
        ''')
        self.assertEqual(lua.eval('data.search.tt_hits'),7)
        self.assertEqual(lua.eval('data.search.combat_cache_hits'),17)
        self.assertEqual(lua.eval('data.search.algorithm'),'pvs')

    def test_pvs_matches_exhaustive_search_with_repeated_players(self):
        lua,_=load_teacher();lua.globals().pvs=lua.globals().load_module('pvs.lua')
        lua.execute('''
            local rng=geometry.random(4097)
            function tree(depth,id,ply)
                local n={key=id,value=math.floor(rng()*1000),maximize=math.floor(ply/2)%2==0,children={}}
                if depth>0 then for i=1,3 do n.children[i]={key=id..i,child=tree(depth-1,id..i,ply+1)} end end
                return n
            end
            model={key=function(n) return n.key end,maximizing=function(n) return n.maximize end,
                   evaluate=function(n) return n.value end,terminal=function(n) return #n.children==0 end,
                   actions=function(n) return n.children end,apply=function(n,a) return a.child end}
            function exhaustive(n,depth)
                if depth==0 or #n.children==0 then return n.value end
                local value=n.maximize and -math.huge or math.huge
                for _,a in ipairs(n.children) do
                    local child=exhaustive(a.child,depth-1)
                    value=n.maximize and math.max(value,child) or math.min(value,child)
                end
                return value
            end
            correct=true;pruned=0;researched=0
            for i=1,60 do
                local root=tree(4,'r',i%4);local cache,pv={},{}
                for depth=1,4 do
                    local action,value,stats=pvs.solve(root,model,depth,never,cache,pv)
                    if value~=exhaustive(root,depth) or exhaustive(action.child,depth-1)~=value then correct=false end
                    pruned=pruned+stats.cutoffs;researched=researched+stats.researches
                end
                local action,value,stats=pvs.solve(root,model,4,never,cache,pv)
                if stats.cache_hits<1 or value~=exhaustive(root,4) then correct=false end
            end
        ''')
        self.assertTrue(lua.eval('correct'))
        self.assertGreater(lua.eval('pruned'),0)
        self.assertGreater(lua.eval('researched'),0)

    def test_local_pvs_finds_two_action_cooperation(self):
        lua,_=load_teacher()
        lua.execute('''
            slow=unit('slow',1,1,2,20,3);slow.cost=10;slow.weapons[1].slow=true
            hit=unit('hit',1,2,1,18,12,2);hit.cost=30
            defender=unit('defender',2,2,2,26,10,2);defender.cost=100
            s=board{slow,hit,defender};config.algorithm='pvs';config.tree_depth=2
            choices=actions.generate(s,config,never,true)
            chosen,stats=search.choose(s,choices,config,never)
        ''')
        self.assertEqual(lua.eval('chosen.id'),'slow')
        self.assertEqual(lua.eval('stats.depth'),2)
        self.assertEqual(lua.eval('stats.algorithm'),'pvs')

    def test_pvs_expiry_keeps_legal_fallback_and_ffa_uses_individual_replies(self):
        lua,_=load_teacher()
        lua.execute('''
            s=board{unit('a',1,2,2,20,5),unit('b',2,2,3,20,5)}
            choices=actions.generate(s,config,never,true);config.algorithm='pvs'
            fallback_key=choices[1].key
            picked,stats=search.choose(s,choices,config,function() return true end)
            s=board({unit('a',1,2,2,20,5)},4);s.ffa=true
            choices=actions.generate(s,config,never,true)
            ffa,ffa_stats=search.choose(s,choices,config,never)
        ''')
        self.assertEqual(lua.eval('picked.key'),lua.eval('fallback_key'))
        self.assertEqual(lua.eval('stats.depth'),0)
        self.assertEqual(lua.eval('ffa_stats.algorithm'),'beam_ffa')

    def test_tree_key_separates_probability_corrections_and_turn_resources(self):
        lua,_=load_teacher();lua.globals().model=lua.globals().load_module('tree_model.lua')
        lua.execute('''
            s=board{unit('a',1,2,2,20,5)}
            first=model.key{state=s,used=0};t=state.clone(s);t.adjustment[1]=.25
            changed=model.key{state=t,used=0};used=model.key{state=s,used=1}
        ''')
        self.assertNotEqual(lua.eval('first'),lua.eval('changed'))
        self.assertNotEqual(lua.eval('first'),lua.eval('used'))


if __name__=='__main__':
    unittest.main()
