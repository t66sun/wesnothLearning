"""New deterministic rule cases only; no statistical or existing-suite rerun."""
import copy
import json
import unittest

from _engine_lite import LiteEngine


WIDTH = 7


def unit_type(name, **fields):
    row = dict(id=name, scope='test', hp=200, moves=6, vision=1, level=1,
               cost=10, experience=1000, alignment='neutral', abilities=[],
               weapons=[dict(id='test', damage=8, strikes=1, damage_type='blade',
                             range='melee')],
               movement={'Gg': 1, 'Ww': 99}, defense={'Gg': 40, 'Ww': 40},
               resistance={'blade': 100})
    row.update(fields)
    return row


def unit(uid, kind, side, pos, **fields):
    row = dict(id=uid, unit_type=kind, side=side, pos=pos, hp=200, moves=6,
               attacks_left=1, xp=0, leader=True, status=[], traits=[], acted=True)
    row.update(fields)
    return row


def engine(types, units, *, terrain=None, lawful_bonus=None):
    rules = dict(source_version='1.18.8', rules_version='abilities-completion',
                 source_hash='abilities-completion', units=types,
                 terrains={code: dict(id=code) for code in ('Gg', 'Ww')},
                 lawful_bonus=lawful_bonus or [0])
    sides = [dict(id=side, team=str(side), gold=0, recruit=[], fog=False,
                  shroud=False) for side in range(1, max(u['side'] for u in units) + 1)]
    spec = dict(width=WIDTH, height=7, terrain=terrain or ['Gg'] * 49,
                sides=sides, units=units, seed=7, max_turns=10, allow_approximate=True)
    return LiteEngine(json.dumps(rules), json.dumps(spec))


def state(core):
    return json.loads(core.snapshot())['game']


def step(core, **action):
    return json.loads(core.step(json.dumps(action)))


def next_round(core):
    for _ in range(len(state(core)['sides'])):
        step(core, kind='end_turn')


def row(core, uid):
    return next(u for u in state(core)['units'] if u['id'] == uid)


class RuleAbilityCompletionTests(unittest.TestCase):
    def test_burrow_requires_full_moves_and_matching_terrain(self):
        types = {'plain': unit_type('plain'),
                 'burrow': unit_type('burrow', concealment_terrains=['Ww'],
                                     concealment_requires_full_moves=True)}
        terrain = ['Gg'] * 49
        terrain[24] = 'Ww'
        for moves, ground, hidden in ((6, terrain, True), (5, terrain, False),
                                     (6, ['Gg'] * 49, False)):
            with self.subTest(moves=moves, terrain=ground[24]):
                core = engine(types, [unit('a', 'plain', 1, 0),
                                      unit('d', 'burrow', 2, 24, moves=moves)],
                              terrain=ground)
                visible = {u['id'] for u in json.loads(core.observe(1))['units']}
                self.assertEqual('d' not in visible, hidden)

    def corridor(self, *, stunned=False, distract=False, petrified=False):
        types = {'plain': unit_type('plain'),
                 'helper': unit_type('helper', abilities=['distract'] if distract else [])}
        terrain = ['Ww'] * 49
        for pos in (10, 17, 24, 16, 25):
            terrain[pos] = 'Gg'
        return engine(types, [unit('a', 'plain', 1, 10),
                              unit('d', 'plain', 2, 25,
                                   status=['stunned'] if stunned else []),
                              unit('h', 'helper', 1, 16,
                                   status=['petrified'] if petrified else [])],
                      terrain=terrain)

    def test_stun_disables_zoc_until_victim_turn(self):
        core = self.corridor(stunned=True)
        moves = json.loads(core.legal_actions(1))
        self.assertIn(dict(kind='move', unit='a', to=24, full=False), moves)
        step(core, kind='move', unit='a', to=24)
        self.assertEqual(row(core, 'a')['moves'], 4)
        step(core, kind='end_turn')
        self.assertNotIn('stunned', row(core, 'd')['status'])

    def test_distract_allows_crossing_zoc_but_petrified_source_does_not(self):
        for active in (False, True):
            with self.subTest(active=active):
                core = self.corridor(distract=True, petrified=not active)
                action = dict(kind='move', unit='a', to=24, full=False)
                self.assertEqual(action in json.loads(core.legal_actions(1)), active)
                if active:
                    step(core, **action)
                    self.assertEqual(row(core, 'a')['pos'], 24)
                    # The destination has left the aura and still consumes ZOC movement.
                    self.assertEqual(row(core, 'a')['moves'], 0)

    def test_inspire_affects_equal_levels_and_excludes_higher_levels(self):
        # base damage 8 at 40% chance: expected_damage_v1 reports ceil(D*1.10*40/100).
        for target_level, expected in ((1, 5), (2, 4)):
            with self.subTest(target_level=target_level):
                types = {'attacker': unit_type('attacker', level=target_level),
                         'plain': unit_type('plain'),
                         'inspirer': unit_type('inspirer', abilities=['inspire'])}
                core = engine(types, [unit('a', 'attacker', 1, 24),
                                      unit('d', 'plain', 2, 25),
                                      unit('h', 'inspirer', 1, 17)])
                result = step(core, kind='attack', unit='a', target='d', weapon=0)
                self.assertEqual(result['strikes'][0]['damage'], expected)

    def test_regeneration_amount_terrain_and_poison_policy(self):
        for fields, terrain_code, status, expected_hp, poisoned in (
                (dict(regeneration_amount=150, regeneration_poison='cured'),
                 'Gg', ['poisoned'], 10, False),
                (dict(regeneration_amount=150, regeneration_poison='cured'),
                 'Gg', [], 160, False),
                (dict(regeneration_amount=6, regeneration_poison='none',
                      regeneration_terrains=['Ww']), 'Ww', [], 16, False),
                (dict(regeneration_amount=6, regeneration_poison='none',
                      regeneration_terrains=['Ww']), 'Gg', [], 10, False),
                (dict(regeneration_amount=6, regeneration_poison='none',
                      regeneration_terrains=['Ww']), 'Ww', ['poisoned'], 2, True)):
            with self.subTest(fields=fields, terrain=terrain_code, status=status):
                terrain = ['Gg'] * 49
                terrain[24] = terrain_code
                core = engine({'regen': unit_type('regen', **fields),
                               'plain': unit_type('plain')},
                              [unit('a', 'regen', 1, 24, hp=10, status=status),
                               unit('d', 'plain', 2, 48)], terrain=terrain)
                next_round(core)
                self.assertEqual(row(core, 'a')['hp'], expected_hp)
                self.assertEqual('poisoned' in row(core, 'a')['status'], poisoned)

    def test_filtered_heals_preserve_unfiltered_curing(self):
        types = {'plain': unit_type('plain'),
                 'healer': unit_type('healer', healing_amount=8,
                                    healing_poison='cured', curing_unfiltered=True,
                                    healing_excluded_status='dehydration_slowed_by_healer')}
        for poisoned in (False, True):
            with self.subTest(poisoned=poisoned):
                status = ['dehydration_slowed_by_healer'] + (['poisoned'] if poisoned else [])
                core = engine(types, [unit('a', 'plain', 1, 24, hp=10, status=status),
                                      unit('h', 'healer', 1, 17),
                                      unit('d', 'plain', 2, 48)])
                next_round(core)
                self.assertEqual(row(core, 'a')['hp'], 10)
                self.assertNotIn('poisoned', row(core, 'a')['status'])

    def test_darkening_reduces_daytime_but_not_below_nighttime(self):
        types = {'lawful': unit_type('lawful', alignment='lawful'),
                 'plain': unit_type('plain'),
                 'dark': unit_type('dark', illumination=-25)}
        for base, expected in ((25, 4), (-25, 3)):
            with self.subTest(base=base):
                core = engine(types, [unit('a', 'lawful', 1, 24),
                                      unit('d', 'plain', 2, 25),
                                      unit('h', 'dark', 1, 17)], lawful_bonus=[base])
                result = step(core, kind='attack', unit='a', target='d', weapon=0)
                self.assertEqual(result['strikes'][0]['damage'], expected)

    def test_diversion_uses_enemy_flanks_in_ffa_and_accumulates(self):
        for second_diversion, expected in ((False, 20), (True, 0)):
            with self.subTest(second_diversion=second_diversion):
                types = {'plain': unit_type('plain'),
                         'diverter': unit_type('diverter', abilities=['diversion'])}
                core = engine(types, [unit('a', 'diverter', 1, 17),
                                      unit('d', 'plain', 2, 24),
                                      unit('h', 'diverter' if second_diversion else 'plain', 3, 31)])
                result = step(core, kind='attack', unit='a', target='d', weapon=0)
                self.assertEqual(result['strikes'][1]['chance'], expected)

    def test_vanguard_counts_both_sides_and_caps_at_six_neighbors(self):
        types = {'plain': unit_type('plain'),
                 'vanguard': unit_type('vanguard', abilities=['vanguard'])}
        extras = [unit('h' + str(i), 'plain', 1 if i % 2 else 2, pos)
                  for i, pos in enumerate((17, 31, 23, 30, 32))]
        for extra_count, expected in ((0, 4), (1, 5), (5, 8)):
            with self.subTest(extra_count=extra_count):
                core = engine(types, [unit('a', 'vanguard', 1, 24),
                                      unit('d', 'plain', 2, 25)] + extras[:extra_count])
                result = step(core, kind='attack', unit='a', target='d', weapon=0)
                self.assertEqual(result['strikes'][0]['damage'], expected)
        # Native add= vanguard is added after the external value= leadership.
        types['commander'] = unit_type('commander', level=2, abilities=['leadership'])
        core = engine(types, [unit('a', 'vanguard', 1, 24),
                              unit('d', 'plain', 2, 25),
                              unit('h', 'commander', 1, 17)])
        result = step(core, kind='attack', unit='a', target='d', weapon=0)
        self.assertEqual(result['strikes'][0]['damage'], 6)

    def test_initiative_aura_requires_melee_opponent_and_active_source(self):
        types = {'plain': unit_type('plain'),
                 'initiative': unit_type('initiative', abilities=['initiative'])}
        types['plain']['weapons'].append(dict(id='ranged', damage=8, strikes=1,
                                             damage_type='blade', range='ranged'))
        for weapon, source_status, first in ((0, [], 'd'), (1, [], 'a'),
                                             (0, ['petrified'], 'a')):
            with self.subTest(weapon=weapon, source_status=source_status):
                core = engine(types, [unit('a', 'plain', 1, 17),
                                      unit('d', 'plain', 2, 24),
                                      unit('h', 'initiative', 2, 31, status=source_status)])
                result = step(core, kind='attack', unit='a', target='d', weapon=weapon)
                self.assertEqual(result['strikes'][0]['attacker'], first)

    def test_diversion_forecast_does_not_read_hidden_flanker(self):
        types = {'plain': unit_type('plain'),
                 'diverter': unit_type('diverter', abilities=['diversion']),
                 'hidden': unit_type('hidden', concealment_terrains=['Gg'])}
        units = [unit('a', 'diverter', 1, 17), unit('d', 'plain', 2, 24),
                 unit('h', 'hidden', 3, 31)]
        core = engine(types, units)
        alternate = copy.deepcopy(units)
        alternate[2]['pos'] = 48
        twin = engine(types, alternate)
        self.assertNotIn('h', {u['id'] for u in json.loads(core.observe(1))['units']})
        self.assertEqual(json.loads(core.forecast(1, 'a', 'd', 0, 1)),
                         json.loads(twin.forecast(1, 'a', 'd', 0, 1)))


if __name__ == '__main__':
    unittest.main()
