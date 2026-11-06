import unittest
from tests.test_search_teacher import load_teacher


class TeacherVariantTests(unittest.TestCase):
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
