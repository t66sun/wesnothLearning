import unittest
from tests.test_search_teacher import load_teacher


class TeacherVariantTests(unittest.TestCase):
    def test_two_enemy_responses_expose_a_fatal_focus_fire(self):
        lua,_=load_teacher()
        lua.execute('''
            leader=unit('leader',1,3,3,30,0);leader.leader=true
            first=unit('first',2,3,2,30,20);second=unit('second',2,2,3,30,20)
            s=board{leader,first,second};config.reply_width=3
            one=search.reply(s,config,never)
            config.reply_actions=2;two=search.reply(s,config,never)
        ''')
        self.assertEqual(lua.eval('one.units.leader.hp'),10)
        self.assertEqual(lua.eval('two.units.leader.hp'),0)
        self.assertTrue(lua.eval('two.defeated[1]'))
        self.assertEqual(lua.eval('s.units.leader.hp'),30)

    def test_healthy_leader_stays_home_but_wounded_leader_can_seek_healing(self):
        lua,_=load_teacher()
        lua.execute('''
            leader=unit('leader',1,2,2,50,8);leader.leader=true;leader.moves=4;leader.max_moves=4
            s=board{leader};s.homes.leader={x=2,y=2};s.keeps[geometry.key(2,2)]={x=2,y=2}
            s.villages[geometry.key(4,2)]={x=4,y=2};s.owners[geometry.key(4,2)]=0
            original=actions.generate(s,config,never,true)
            s.leader_home_bonus=16;guarded=actions.generate(s,config,never,true)
            leader.hp=10;wounded=actions.generate(s,config,never,true)
        ''')
        self.assertEqual(lua.eval('original[1].kind'),'move')
        self.assertEqual(lua.eval('guarded[1].kind'),'end_turn')
        self.assertEqual(lua.eval('wounded[1].kind'),'move')
        self.assertEqual(lua.eval('wounded[1].tx'),4)
        self.assertEqual(lua.eval('wounded[1].ty'),2)

    def test_leader_death_removes_its_faction_but_keeps_a_team_partner(self):
        lua,_=load_teacher()
        lua.execute('''
            a=unit('a',1,2,2,30,20);leader=unit('leader',2,2,3,5,1);leader.leader=true
            follower=unit('follower',2,6,6,30,10);partner=unit('partner',4,6,7,30,10);partner.leader=true
            s=board({a,leader,follower,partner},4);s.gold[2]=50;s.owners[geometry.key(6,6)]=2
            s.enemies[2][4]=false;s.enemies[4][2]=false
            after=state.apply(s,{kind='combat',id='a',enemy='leader',weapon=1,tx=2,ty=2})
        ''')
        self.assertEqual(lua.eval('after.units.follower.hp'),0)
        self.assertEqual(lua.eval('after.units.partner.hp'),30)
        self.assertTrue(lua.eval('after.defeated[2]'))
        self.assertEqual(lua.eval('state.material(after,2)'),0)
        self.assertEqual(lua.eval('s.units.follower.hp'),30)
        self.assertIsNone(lua.eval('s.defeated'))

    def test_another_known_living_leader_prevents_faction_elimination(self):
        lua,_=load_teacher()
        lua.execute('''
            a=unit('a',1,2,2,30,20);leader=unit('leader',2,2,3,5,1);leader.leader=true
            second=unit('second',2,6,6,30,10);second.leader=true;s=board{a,leader,second};s.gold[2]=50
            after=state.apply(s,{kind='combat',id='a',enemy='leader',weapon=1,tx=2,ty=2})
        ''')
        self.assertEqual(lua.eval('after.units.second.hp'),30)
        self.assertEqual(lua.eval('after.gold[2]'),50)
        self.assertIsNone(lua.eval('after.defeated[2]'))

    def test_live_state_identity_keeps_the_existing_private_seed(self):
        lua,_=load_teacher();lua.globals().model=lua.globals().load_module('tree_model.lua')
        lua.execute("s=board{unit('a',1,2,2,20,5)};identity=model.key{state=s,used=0}")
        self.assertEqual(lua.eval('identity'),'1;1;0;0;a,1,2,2,20,0,1,0,0;0/0;0/0')

    def test_forecast_cache_reuses_distributions_without_stale_context(self):
        lua,_=load_teacher()
        lua.execute('''
            a=unit('a',1,2,2,30,8,3);d=unit('d',2,2,3,30,6,3)
            a.defense.Gg=50;d.defense.Gg=40;s=board{a,d}
            combat.reset_cache(true);f=combat.forecast(s,a,d,1);again=combat.forecast(s,a,d,1)
            reused=f==again;entries,hits=combat.cache_stats()
            d.slow=true;d.hp=21;a.weapons[1].poison=true
            changed=combat.forecast(s,a,d,1);different=f~=changed
            combat.reset_cache(false);plain=combat.forecast(s,a,d,1)
        ''')
        self.assertTrue(lua.eval('reused'))
        self.assertEqual(lua.eval('hits'),1)
        self.assertEqual(lua.eval('entries'),1)
        self.assertTrue(lua.eval('different'))
        for key in ('ah','dh','kill','death','slow','poison','own_slow','own_poison'):
            self.assertEqual(lua.eval('changed.'+key),lua.eval('plain.'+key))

    def test_cache_keys_include_aura_terrain_and_supported_continuation(self):
        lua,_=load_teacher()
        lua.execute('''
            a=unit('a',1,2,2,30,8,3);d=unit('d',2,2,3,30,6,3)
            a.alignment='lawful';d.defense.Gg=40;d.defense.Ff=70
            s=board{a,d};combat.reset_cache(true);old=combat.forecast(s,a,d,1)
            s.lawful_bonus=25;s.terrain[geometry.key(d.x,d.y)]='Ff';a.xp=a.max_xp-1
            cached=combat.forecast(s,a,d,1);combat.reset_cache(false);plain=combat.forecast(s,a,d,1)
        ''')
        self.assertFalse(lua.eval('cached.supported'))
        self.assertNotEqual(lua.eval('cached.dh'),lua.eval('old.dh'))
        self.assertEqual(lua.eval('cached.dh'),lua.eval('plain.dh'))

    def test_keep_access_prevents_leaving_an_unrecruited_army_as_gold(self):
        lua,_=load_teacher()
        lua.execute('''
            leader=unit('leader',1,2,2,50,8);leader.leader=true;leader.moves=4;leader.max_moves=4
            recruit=unit('recruit',1,2,3,30,8);recruit.type='Spearman';recruit.cost=14
            s=board{leader};s.gold[1]=100;s.recruits={recruit}
            s.keeps[geometry.key(2,2)]={x=2,y=2}
            s.castles[geometry.key(2,2)]={x=2,y=2};s.castles[geometry.key(2,3)]={x=2,y=3}
            s.villages[geometry.key(4,2)]={x=4,y=2};s.owners[geometry.key(4,2)]=0
            config.depth=1;config.root_width=30
            choices=actions.generate(s,config,never,true)
            before=search.choose(s,choices,config,never)
            s.outside_keep_gold=.1
            after=search.choose(s,choices,config,never)
        ''')
        self.assertEqual(lua.eval('before.kind'),'move')
        self.assertEqual(lua.eval('after.kind'),'recruit')


if __name__=='__main__':
    unittest.main()
