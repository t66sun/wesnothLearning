import unittest
from tests.test_lua_contracts import initialize


class CandidateCoverageTests(unittest.TestCase):
    def test_intermediate_tactical_hex_is_not_lost_between_goals(self):
        lua, modules = initialize()
        lua.execute('''
            fixture.own={fixture.own[1]};fixture.visible=fixture.own
            fixture.own[1].canrecruit=false
            local leader=fixture.own[1]:clone();leader.canrecruit=true;leader.id='home'
            leader.x=40;leader.y=40;leader.moves=0
            fixture.own[2]=leader
            wesnoth.map.find=function(filter) return filter.terrain and {} or {{12,1}} end
            wesnoth.paths.find_reach=function(u,cfg)
                local r={};for x=2,10 do for y=1,3 do r[#r+1]={x,y,1} end end;return r
            end
            fixture.own[1].defense_on=function(u,t) return t=='Ff' and 70 or 20 end
            wesnoth.current.map=setmetatable({width=16,height=16}, {__index=function(_,p)
                return p[1]==9 and p[2]==1 and 'Ff' or 'Gg'
            end})
        ''')
        actions, _ = modules['candidates.lua'].generate(modules['observation.lua'].capture(lua.table()), 200)
        self.assertTrue(any(a['kind']=='move' and a['tx']==9 and a['ty']==1 for _,a in actions.items()))

    def test_busy_unit_cannot_consume_other_units_move_slots(self):
        lua, modules = initialize()
        lua.execute('''
            local original=fixture.own[2]
            fixture.own={};fixture.visible={}
            for i=1,12 do
                local u=original:clone();u.id='unit'..i;u.x=i;u.y=1
                fixture.own[i]=u;fixture.visible[i]=u
            end
            fixture.visible[#fixture.visible+1]={id='leader',side=1,x=40,y=40,
                canrecruit=true,hitpoints=40,max_hitpoints=40,moves=0,max_moves=4,
                attacks_left=0,attacks={},status={},type='Fighter',defense_on=original.defense_on,
                movement_on=original.movement_on,resistance_against=original.resistance_against}
            fixture.own[#fixture.own+1]=fixture.visible[#fixture.visible]
            wesnoth.sides[1].recruit={}
            wesnoth.map.find=function(filter)
                local r={};if not filter.terrain then for x=1,16 do r[#r+1]={x,2} end end;return r
            end
            wesnoth.paths.find_reach=function(u,cfg)
                local r={};for x=1,16 do r[#r+1]={x,2,2} end;return r
            end
        ''')
        actions, _ = modules['candidates.lua'].generate(modules['observation.lua'].capture(lua.table()))
        origins={a['x'] for _,a in actions.items() if a['kind']=='move'}
        self.assertEqual(origins,set(range(1,13)))
        self.assertLessEqual(len(actions),37)


if __name__=='__main__':unittest.main()
