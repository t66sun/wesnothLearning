"""Atomic public paths must never leave two live units on one hex."""
import unittest

from . import helpers as H


class FriendlyTransitTests(unittest.TestCase):
    def game(self, *, hidden_contact=False):
        rules=H.rules()
        rules['units']['Fighter']['vision']=1
        units=[H._unit('mover','Fighter',1,0,0,width=6,leader=True),
               H._unit('ally','Fighter',2,1,0,width=6,leader=True),
               H._unit('enemy','Fighter',3,2 if hidden_contact else 5,0,width=6,leader=True)]
        terrain=['Gg']*6
        if not hidden_contact: terrain[1]='Gg^Vh'
        spec=dict(width=6,height=1,terrain=terrain,units=units,seed=9,max_turns=4,
                  allow_approximate=True,village_owner={} if hidden_contact else {1:2},
                  sides=[dict(id=i,team='allies' if i<3 else 'enemy',gold=0,recruit=[],
                              fog=hidden_contact,shroud=False,share_view=False,share_maps=False)
                         for i in range(1,4)])
        return H.engine(game_spec=spec,rules_data=rules)

    def assert_no_overlap(self,engine):
        units=[u for u in H.snapshot(engine)['game']['units'] if u['hp']>0]
        self.assertEqual(len({u['pos'] for u in units}),len(units))

    def test_crossing_occupied_friendly_village_does_not_capture_or_stop_there(self):
        engine=self.game()
        action=dict(kind='move',unit='mover',to=3,full=True)
        self.assertIn(dict(action,full=False),H.legal(engine))
        result=H.step(engine,action)
        self.assertFalse(result['interrupted'])
        self.assertEqual(result['actual_pos'],3)
        self.assertEqual(H.snapshot(engine)['game']['village_owner'][1],2)
        self.assert_no_overlap(engine)

    def test_new_enemy_contact_on_friendly_transit_hex_stops_at_last_vacant_hex(self):
        engine=self.game(hidden_contact=True)
        self.assertNotIn('enemy',{u['id'] for u in H.observe(engine)['units']})
        action=dict(kind='move',unit='mover',to=3,full=True)
        self.assertIn(dict(action,full=False),H.legal(engine))
        result=H.step(engine,action)
        self.assertTrue(result['interrupted'])
        self.assertEqual(result['actual_pos'],0)
        self.assert_no_overlap(engine)
