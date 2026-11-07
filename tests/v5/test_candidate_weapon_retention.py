"""Check weapon retention on the frozen #228 public board."""
import copy
import json
import unittest

from _engine_lite import LiteEngine

from learning.lite_host import host_modules
from learning.rules_catalog import resolve_dir
from verification.candidate_support_20261106.fixtures import cases


def combat_slots(rules):
    return next(case['spec'] for case in cases(rules) if case['name'] == 'combat_slots')


def witness(row):
    return {a['weapon']: a for a in row['candidates']
            if a['kind'] == 'attack' and (a['x'], a['y'], a['tx'], a['ty']) == (9, 3, 9, 4)}


# Observe actual shared forecasts without touching the production measurement path.
AUDIT = '''
    local generate=M.generate
    function M.generate(obs)
        local simulate=wesnoth.simulate_combat
        local calls={}
        wesnoth.simulate_combat=function(u,w,e)
            local ours,theirs=simulate(u,w,e)
            calls[#calls+1]={actor=u.id,x=u.x,y=u.y,weapon=w,target=e.id,
                target_slow=theirs.slowed,target_poison=theirs.poisoned}
            return ours,theirs
        end
        local actions,timing=generate(obs)
        wesnoth.simulate_combat=simulate
        timing.test_calls=calls
        return actions,timing
    end
    return M
'''


def engine(rules, spec, *, audit=False):
    instance = LiteEngine(json.dumps(rules), json.dumps(spec))
    modules = host_modules()
    if audit:
        modules['candidates.lua'] = 'local M=(function()\n' + modules['candidates.lua'] + '\nend)()\n' + AUDIT
    instance.configure_host(json.dumps(modules))
    return instance


class CandidateWeaponRetentionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = json.loads((resolve_dir() / 'rules.json').read_text())
        cls.spec = combat_slots(cls.rules)

    def test_dominant_ranged_weapon_immediately_occupies_its_group_slot(self):
        game = engine(self.rules, self.spec, audit=True)
        row = json.loads(game.decision(1))
        self.assertEqual(set(witness(row)), {2})
        candidate = witness(row)[2]
        self.assertEqual(candidate['features'][23], 1)
        for actual, expected in zip(candidate['features'][14:18], (17.1072 / 50, 0, .4752, 0)):
            self.assertAlmostEqual(actual, expected)
        self.assertEqual(len(row['candidates']), 37)
        self.assertEqual(row['candidates'][0]['kind'], 'end_turn')
        self.assertEqual({a['type'] for a in row['candidates'] if a['kind'] == 'recruit'}, {'Spearman', 'Mage'})

        timing = row['timing']
        calls = timing['test_calls']
        keys = {(c['actor'], c['x'], c['y'], c['weapon'], c['target']) for c in calls}
        self.assertEqual(len(calls), len(keys))
        self.assertEqual(timing['predictions'], len(calls))
        self.assertLessEqual(timing['predictions'], 36)
        self.assertGreater(timing['prediction_reuses'], 0)
        self.assertLessEqual(timing['work'], 12000)
        self.assertEqual(timing['predictions'], json.loads(game.decision(1))['timing']['predictions'])

    def test_damage_dominance_does_not_remove_a_slow_tradeoff(self):
        rules = copy.deepcopy(self.rules)
        # Add the standard slow effect to the retained low-damage weapon. The
        # otherwise identical combat-slot fixture controls the retention conflict.
        rules['units']['Elvish Marksman']['weapons'][0]['specials'].append('slow')
        row = json.loads(engine(rules, self.spec, audit=True).decision(1))
        self.assertEqual(set(witness(row)), {1})
        calls = {c['weapon']: c for c in row['timing']['test_calls'] if c['actor'] == 'archer-04'}
        self.assertEqual(set(calls), {1, 2})
        self.assertGreater(calls[1]['target_slow'], 0)
        self.assertEqual(calls[2]['target_slow'], 0)
        self.assertLess(witness(row)[1]['features'][14], 17.1072 / 50)
        self.assertGreater(witness(row)[1]['features'][15], 0)

    def test_damage_dominance_does_not_remove_a_possible_plague_conversion(self):
        spec = copy.deepcopy(self.spec)
        next(u for u in spec['units'] if u['id'] == 'archer-04').update(unit_type='Necromancer', hp=48)
        next(u for u in spec['units'] if u['id'] == 'target-04')['hp'] = 9
        game = engine(self.rules, spec, audit=True)
        row = json.loads(game.decision(1))
        self.assertEqual(set(witness(row)), {1})
        calls = {c['weapon'] for c in row['timing']['test_calls'] if c['actor'] == 'archer-04'}
        self.assertTrue({1, 2} <= calls)
        staff, ranged = (json.loads(game.forecast(1, 'archer-04', 'target-04', weapon)) for weapon in (0, 1))
        self.assertGreater(staff['defender']['hp_chance']['0'], 0)
        self.assertGreater(ranged['defender']['hp_chance']['0'], staff['defender']['hp_chance']['0'])
        self.assertLess(ranged['defender']['average_hp'], staff['defender']['average_hp'])
        self.assertGreater(ranged['attacker']['average_hp'], staff['attacker']['average_hp'])


if __name__ == '__main__':
    unittest.main()
