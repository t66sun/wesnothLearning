"""Exercise the actual Lua forecast and candidate generation on frozen unit definitions."""
import hashlib
import json
import unittest

from _engine_lite import LiteEngine

from learning.lite_host import host_modules
from learning.rules_catalog import resolve_dir


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def capture_cases():
    rules_text=(resolve_dir()/'rules.json').read_text();rules=json.loads(rules_text)
    def run(types,positions,side_ids,water,landing):
        terrain=['Gg']*49
        for p in water: terrain[p]='Wo'
        units=[]
        for name,kind,side,pos in zip(('actor','defender','support'),types,side_ids,positions):
            definition=rules['units'][kind]
            units.append(dict(id=name,unit_type=kind,side=side,pos=pos,hp=definition['hp'],moves=definition['moves'],
                              attacks_left=1,leader=True,xp=0,status=[],traits=[]))
        spec=dict(width=7,height=7,terrain=terrain,seed=20261104,max_turns=5,allow_approximate=True,units=units,
                  sides=[dict(id=s,team=str(s),gold=0,recruit=[],fog=False,shroud=False,share_view=False,share_maps=False)
                         for s in sorted(set(side_ids))])
        engine=LiteEngine(rules_text,json.dumps(spec));modules=host_modules()
        # The ordinary candidate generator runs first. Request the actual teacher
        # forecast through the same Lua API on the specified legal landing.
        mods='''
            local generate=M.generate
            function M.generate(obs)
                local actions,timing=generate(obs)
                local a=wesnoth.units.find_on_map{id='actor'}[1]:clone()
                local d=wesnoth.units.find_on_map{id='defender'}[1]
                a.x,a.y=LANDING
                local ar,dr=wesnoth.simulate_combat(a,1,d)
                local function report(stats)
                    local hp={};for k,p in pairs(stats.hp_chance) do hp[tostring(k)]=p end
                    return {average_hp=stats.average_hp,hp_chance=hp,slowed=stats.slowed,poisoned=stats.poisoned}
                end
                timing.test_forecast={attacker=report(ar),defender=report(dr)}
                return actions,timing
            end
            return M
        '''.replace('LANDING',f'{landing%7+1},{landing//7+1}')
        modules['candidates.lua']='local M=(function()\n'+modules['candidates.lua']+'\nend)()\n'+mods
        engine.configure_host(json.dumps(modules))
        view=json.loads(engine.observe(1));legal=json.loads(engine.legal_actions(1));before=json.loads(engine.snapshot())['game']
        assert any(a['kind']=='move' and a['unit']=='actor' and a['to']==landing for a in legal)
        decision=json.loads(engine.decision(1));assert before==json.loads(engine.snapshot())['game']
        return dict(public_view=digest(view),legal=digest(legal),visible_ids=[u['id'] for u in view['units']],
                    scene=digest([decision['global'],decision['opponents'],decision['spatial']]),
                    candidates=digest(decision['candidates']),candidate_count=len(decision['candidates']),
                    forecast=decision['timing']['test_forecast'])
    def hidden(pos): return run(('Spearman','Skeleton','Death Knight'),(22,24,pos),(1,2,2),(17,6),23)
    def flanker(kind,pos): return run(('Rogue','Skeleton',kind),(25,24,pos),(1,2,3),(32,),23)
    return dict(hidden_near=hidden(17),hidden_far=hidden(6),reconcealed=flanker('Skeleton',32),
                unflanked=flanker('Skeleton',33),visible_flanker=flanker('Elvish Fighter',32))


class ForecastPublicContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.cases=capture_cases()

    def test_hidden_leadership_cannot_change_hypothetical_forecast_or_normal_candidates(self):
        a,b=self.cases['hidden_near'],self.cases['hidden_far']
        self.assertEqual(a['visible_ids'],['actor','defender'])
        for key in ('public_view','legal','scene','forecast','candidates'):
            self.assertEqual(a[key],b[key],key)

    def test_previously_public_ffa_flanker_reconceals_after_rogue_moves(self):
        a=self.cases['reconcealed']
        self.assertIn('support',a['visible_ids'])
        self.assertEqual(a['forecast'],self.cases['unflanked']['forecast'])
        self.assertLess(self.cases['visible_flanker']['forecast']['defender']['average_hp'],
                        a['forecast']['defender']['average_hp'])


if __name__=='__main__': unittest.main()
