import unittest
from tests.test_search_teacher import load_teacher


class TeacherHealingTests(unittest.TestCase):
    def test_public_profile_distinguishes_curing_from_hitpoint_healing(self):
        lua,_=load_teacher()
        lua.execute('''
            wml={get_child=function(cfg,key) return cfg[key] end}
            native={id='h',type='Healer',side=1,x=2,y=2,hitpoints=30,max_hitpoints=30,
                moves=0,max_moves=5,attacks_left=1,cost=20,status={},attacks={},
                __cfg={abilities={{'heals',{poison='cured'}},{'heals',{value=8,poison='slowed'}},
                    {'regenerate',{value=4,poison='cured'}}}},
                resistance_against=function() return 0 end,
                movement_on=function() return 1 end,defense_on=function() return 40 end}
            p=public.profile(native,{Gg=true})
        ''')
        self.assertEqual(lua.eval('p.healing'),8)
        self.assertEqual(lua.eval('p.healing_poison'),2)
        self.assertEqual(lua.eval('p.regenerates'),4)
        self.assertEqual(lua.eval('p.regeneration_poison'),2)

    def test_village_cures_poison_instead_of_healing_on_that_turn(self):
        lua,_=load_teacher()
        lua.execute('''
            u=unit('u',2,2,2,30,5);u.hp=10;u.poison=true;s=board{u}
            s.villages[geometry.key(2,2)]={x=2,y=2};after=state.apply(s,{kind='end_turn'})
        ''')
        self.assertEqual(lua.eval('after.units.u.hp'),10)
        self.assertFalse(lua.eval('after.units.u.poison'))
        self.assertTrue(lua.eval('s.units.u.poison'))

    def test_regeneration_uses_maximum_healing_and_cures_separately(self):
        lua,_=load_teacher()
        lua.execute('''
            u=unit('u',2,2,2,30,5);u.hp=10;u.regenerates=8;u.regeneration_poison=2
            s=board{u};s.villages[geometry.key(2,2)]={x=2,y=2}
            healed=state.apply(s,{kind='end_turn'})
            u.poison=true;cured=state.apply(s,{kind='end_turn'})
        ''')
        self.assertEqual(lua.eval('healed.units.u.hp'),18)
        self.assertEqual(lua.eval('cured.units.u.hp'),10)
        self.assertFalse(lua.eval('cured.units.u.poison'))

    def test_allied_healer_slows_on_patient_turn_and_cures_on_its_own(self):
        lua,_=load_teacher()
        lua.execute('''
            u=unit('u',2,2,2,30,5);u.hp=10;u.poison=true
            h=unit('h',3,2,3,30,5);h.healing=8;h.healing_poison=2
            s=board({u,h},4);s.enemies[2][3]=false;s.enemies[3][2]=false
            slowed=state.apply(s,{kind='end_turn'})
            cured=state.apply(slowed,{kind='end_turn'})
            next_round=state.apply(state.apply(state.apply(state.apply(cured,
                {kind='end_turn'}),{kind='end_turn'}),{kind='end_turn'}),{kind='end_turn'})
        ''')
        self.assertEqual(lua.eval('slowed.units.u.hp'),10)
        self.assertTrue(lua.eval('slowed.units.u.poison'))
        self.assertEqual(lua.eval('cured.units.u.hp'),10)
        self.assertFalse(lua.eval('cured.units.u.poison'))
        self.assertEqual(lua.eval('next_round.units.u.hp'),18)

    def test_visible_healers_do_not_stack_or_heal_self_enemies_or_stone(self):
        lua,_=load_teacher()
        lua.execute('''
            u=unit('u',2,2,2,30,5);u.hp=10
            h=unit('h',2,2,3,30,5);h.hp=10;h.healing=8;h.healing_poison=1
            other=unit('other',2,3,2,30,5);other.healing=4
            foe=unit('foe',1,1,3,30,5);foe.hp=10
            stone=unit('stone',2,3,3,30,5);stone.hp=10;stone.petrified=true
            s=board{u,h,other,foe,stone};after=state.apply(s,{kind='end_turn'})
            s.units.other=nil;alone=state.apply(s,{kind='end_turn'})
        ''')
        self.assertEqual(lua.eval('after.units.u.hp'),18)
        self.assertEqual(lua.eval('after.units.foe.hp'),10)
        self.assertEqual(lua.eval('after.units.stone.hp'),10)
        self.assertEqual(lua.eval('alone.units.h.hp'),10)


if __name__=='__main__':
    unittest.main()
