import unittest
from tests.test_search_teacher import load_teacher


class TeacherVariantTests(unittest.TestCase):
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
