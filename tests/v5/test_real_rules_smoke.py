"""Opt-in smoke for the shared Lua host against the captured native 1.18.8 core.

This is deliberately not an acceptance claim: the frozen catalogue is marked
incomplete and the job must pass ``require_accepted=False``.  It catches
regressions that synthetic rules cannot see, such as real terrain/movement
tables and a leader path crossing its own recruits.
"""
from __future__ import annotations

import gzip
import json
import time
import unittest
from pathlib import Path

from learning.common import ROOT
from learning.features import RULES_PATH
from learning.lite_host import play_lite_job

from .helpers import engine, legal, observe, step

RULES = RULES_PATH.parent / 'rules.json'
CATALOG = RULES_PATH


def _unit(rules, side, unit_type, x, y, width):
    definition = rules['units'][unit_type]
    return dict(id=f'leader_{side}', unit_type=unit_type, side=side,
                pos=(y - 1) * width + x - 1, hp=definition['hp'],
                moves=definition['moves'], attacks_left=1, xp=0, leader=True,
                status=[], traits=[])


def _combat_spec(rules):
    """Adjacent leaders on open arena terrain for a rules-runtime smoke."""
    board = json.loads((ROOT / 'vendor/arena/maps/arena2.json').read_text(encoding='utf-8'))
    width = len(board['terrain'][0])
    terrain = [code for row in board['terrain'] for code in row]
    units = [
        dict(id='leader_1', unit_type='Elvish Fighter', side=1, pos=(7 - 1) * width + (3 - 1),
             hp=rules['units']['Elvish Fighter']['hp'], moves=rules['units']['Elvish Fighter']['moves'],
             attacks_left=1, xp=0, leader=True, status=[], traits=[]),
        dict(id='enemy_1', unit_type='Skeleton', side=2, pos=(7 - 1) * width + (4 - 1),
             hp=rules['units']['Skeleton']['hp'], moves=rules['units']['Skeleton']['moves'],
             attacks_left=1, xp=0, leader=True, status=[], traits=[]),
    ]
    sides = [
        dict(id=1, team='1', faction='Rebels', gold=100, base_income=2,
             recruit=['Elvish Fighter', 'Elvish Archer'], fog=False, shroud=False,
             share_view=False, share_maps=False),
        dict(id=2, team='2', faction='Undead', gold=100, base_income=2,
             recruit=['Skeleton', 'Walking Corpse'], fog=False, shroud=False,
             share_view=False, share_maps=False),
    ]
    return dict(width=width, height=len(board['terrain']), terrain=terrain, sides=sides,
                units=units, village_owner={}, seed=7, max_turns=3,
                experience_modifier=100, allow_approximate=True)


def _spec():
    rules = json.loads(RULES.read_text(encoding='utf-8'))
    board = json.loads((ROOT / 'vendor/arena/maps/arena2.json').read_text(encoding='utf-8'))
    width = len(board['terrain'][0])
    sides = [
        dict(id=1, team='1', faction='Rebels', gold=100, base_income=2,
             recruit=['Elvish Fighter', 'Elvish Archer'], fog=True, shroud=False,
             share_view=True, share_maps=True),
        dict(id=2, team='2', faction='Undead', gold=100, base_income=2,
             recruit=['Skeleton', 'Walking Corpse'], fog=True, shroud=False,
             share_view=True, share_maps=True),
    ]
    return dict(width=width, height=len(board['terrain']),
                terrain=[code for row in board['terrain'] for code in row],
                sides=sides,
                units=[_unit(rules, 1, 'Elvish Fighter', *board['starts'][0], width),
                       _unit(rules, 2, 'Skeleton', *board['starts'][1], width)],
                village_owner={}, seed=7, max_turns=2, allow_approximate=True)


@unittest.skipUnless(RULES.is_file() and CATALOG.is_file(),
                     'captured native 1.18.8 core rules are absent')
class RealRulesSmokeTests(unittest.TestCase):
    def test_real_rules_engine_combat_executes_without_downgrade(self):
        rules = json.loads(RULES.read_text(encoding='utf-8'))
        instance = engine(game_spec=_combat_spec(rules), rules_data=rules)
        view = observe(instance, 1)
        self.assertEqual({u['id'] for u in view['units']}, {'leader_1', 'enemy_1'})
        actions = legal(instance, 1)
        attacks = [a for a in actions if a.get('kind') == 'attack'
                   and a.get('unit') == 'leader_1' and a.get('target') == 'enemy_1']
        self.assertTrue(attacks, 'full captured rules expose no attack')
        result = step(instance, attacks[0])
        self.assertGreater(len(result.get('strikes', [])), 0)
        self.assertTrue(all('attacker' in row and 'defender' in row for row in result['strikes']))
        after = observe(instance, 1)
        by_id = {u['id']: u for u in after['units']}
        self.assertLessEqual(by_id['enemy_1']['hp'], rules['units']['Skeleton']['hp'])

    def test_astra_job_runs_shared_lua_on_real_core_rules(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            shard = Path(directory) / 'job.jsonl.gz'
            job = dict(id='real-core-smoke', seed=7, bots=['astra', 'astra'],
                       game_spec=_spec(), rules_dir=str(RULES.parent), shard=str(shard),
                       deadline=time.time() + 120, max_decisions=500,
                       meta=dict(format='duel', map='arena2', map_sha256='real-core',
                                 map_partition='train', context='solo'),
                       teams=[1, 2], factions=['Rebels', 'Undead'],
                       game_family='real-core-smoke',
                       learning=dict(sides={'1': {}, '2': {}}, version='v5-smoke'),
                       require_accepted=False, max_turns=2)
            outcome = play_lite_job(job)
            self.assertEqual(outcome['status'], 'complete', outcome.get('error'))
            self.assertEqual(outcome['engine'], 'lite')
            self.assertGreater(outcome['training_shard']['written'], 0)
            self.assertGreater(outcome['coverage']['total'], 0)
            self.assertGreater(outcome['coverage']['matched'], 0)
            with gzip.open(shard, 'rt', encoding='utf-8') as stream:
                rows = [json.loads(line) for line in stream]
            self.assertTrue(all(row['schema'] == 4 for row in rows))
            self.assertTrue(all(row['engine_id'] == 'lite' for row in rows))
            self.assertTrue(all(row['actual']['kind'] != 'baseline' for row in rows))
            self.assertEqual(outcome['result']['bots'], ['astra', 'astra'])
