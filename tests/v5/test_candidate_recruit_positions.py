"""Check the actual retained and executable recruit intents on #228 boards."""
import copy
import json
from pathlib import Path
import unittest

from learning.rules_catalog import resolve_dir
from tests.v5.helpers import cube_distance
from tests.v5.test_candidate_weapon_retention import engine
from verification.candidate_support_20261106.fixtures import cases, put, tile


def recruitment_case(rules):
    return next(case['spec'] for case in cases(rules) if case['name'] == 'recruit_positions')


def recruit_key(action):
    return action['type'], action['x'], action['y']


def recruit_intents(row):
    return {recruit_key(a): a for a in row['candidates'] if a['kind'] == 'recruit'}


def frozen_recruit_support():
    evidence = Path(__file__).resolve().parents[2] / 'verification/candidate_support_20261106/measured.json'
    witness = json.loads(evidence.read_text())['findings']['recruit_positions']
    front = {recruit_key(a) for a in witness['support']['A'] if a['kind'] == 'recruit'}
    low = {recruit_key(a) for a in witness['useful']['C']}
    return front, low


def low_pairs(recruits, low):
    kept = sorted(recruits.keys() & low)
    return [(a, b) for a in kept for b in kept if a[0] == 'Spearman' and b[0] == 'Mage' and a[1:] != b[1:]]


class CandidateRecruitPositionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = json.loads((resolve_dir() / 'rules.json').read_text())
        cls.spec = recruitment_case(cls.rules)
        cls.front, cls.low = frozen_recruit_support()

    def test_public_low_exposure_pair_is_retained_and_executes(self):
        game = engine(self.rules, self.spec)
        row = json.loads(game.decision(1))
        recruits = recruit_intents(row)
        pairs = low_pairs(recruits, self.low)
        self.assertTrue(pairs, sorted(recruits))
        for kind in ('Spearman', 'Mage'):
            self.assertEqual(sum(k[0] == kind for k in recruits.keys() & self.low), 4)
            self.assertEqual(sum(k[0] == kind for k in recruits.keys() & self.front), 4)
        self.assertEqual(len(recruits), len(row['candidates']) - 1)
        self.assertEqual(row['candidates'][0]['kind'], 'end_turn')
        self.assertEqual(row['timing']['recruit_probes'], 16)
        self.assertEqual(row['timing']['reaches'], 2)
        self.assertLessEqual(row['timing']['work'], 12000)
        for key in pairs[0]:
            outcome = json.loads(game.execute_candidate(json.dumps(recruits[key])))
            self.assertTrue(outcome['committed'], outcome)
        after = json.loads(game.observe(1))
        self.assertEqual(after['sides'][0]['gold'], 0)
        for kind, x, y in pairs[0]:
            pos = (y - 1) * self.spec['width'] + x - 1
            self.assertTrue(any(u['unit_type'] == kind and u['pos'] == pos for u in after['units']))

    def test_front_and_low_exposure_survive_the_final_slot_cap(self):
        spec = copy.deepcopy(self.spec)
        for x in range(16, 23):
            put(spec, self.rules, f'mover-{x}', 'Elvish Scout', 1, x, 1, moves=5, attacks=0)
        row = json.loads(engine(self.rules, spec).decision(1))
        self.assertEqual(len(row['candidates']), 37)
        recruits = recruit_intents(row)
        for kind in ('Spearman', 'Mage'):
            self.assertIn((kind, 6, 2), recruits)
            self.assertTrue(any(key[0] == kind for key in recruits.keys() & self.low), sorted(recruits))

    def test_all_exposed_keeps_the_nearest_legal_recruits(self):
        spec = copy.deepcopy(self.spec)
        enemy = (7, 4)
        threat = next(u for u in spec['units'] if u['id'] == 'threat')
        threat['pos'] = (enemy[1] - 1) * spec['width'] + enemy[0] - 1
        sites = {(x, y) for x in range(2, 7) for y in range(2, 7)} - {(2, 4)}
        front = sorted(sites, key=lambda xy: (cube_distance(xy, enemy), xy))[:8]
        row = json.loads(engine(self.rules, spec).decision(1))
        self.assertEqual(recruit_intents(row).keys(), {(kind, *xy) for kind in ('Spearman', 'Mage') for xy in front})

    def test_incomplete_public_threat_map_preserves_original_order(self):
        spec = copy.deepcopy(self.spec)
        for i in range(11):
            put(spec, self.rules, f'remote-{i:02}', 'Orcish Grunt', 2, 17 + i % 6, 2 + i // 6)
        row = json.loads(engine(self.rules, spec).decision(1))
        self.assertEqual(row['timing']['reaches'], 12)
        self.assertEqual(recruit_intents(row).keys(), self.front)

    def test_frozen_hidden_deltas_cannot_change_recruit_options(self):
        rows = []
        for case in cases(self.rules):
            if case['name'] not in ('hidden_control', 'hidden_changed'):
                continue
            spec = case['spec']
            spec['sides'][0].update(gold=self.spec['sides'][0]['gold'], recruit=['Spearman', 'Mage'])
            next(u for u in spec['units'] if u['id'] == 'scout')['moves'] = 0
            for x in range(2, 7):
                for y in range(2, 7):
                    if (x, y) != (2, 2):
                        tile(spec, x, y, 'Ch')
            put(spec, self.rules, 'threat', 'Orcish Grunt', 2, 11, 4)
            game = engine(self.rules, spec)
            view = json.loads(game.observe(1))
            self.assertEqual({u['id'] for u in view['units']}, {'leader', 'scout', 'threat'})
            row = json.loads(game.decision(1))
            self.assertTrue(low_pairs(recruit_intents(row), self.low))
            rows.append({key: row[key] for key in ('global', 'opponents', 'spatial', 'candidates')})
        self.assertEqual(len(rows), 2)
        self.assertEqual(*rows)


if __name__ == '__main__':
    unittest.main()
