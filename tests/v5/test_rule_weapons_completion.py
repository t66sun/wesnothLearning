"""Deterministic checks for newly captured stock weapon declarations only."""
import json
import unittest

from tests.v5 import helpers as H


def weapon(**overrides):
    row = dict(id='test', damage=7, strikes=1, damage_type='blade',
               range='melee', specials=[])
    row.update(overrides)
    return row


def fight(attack, defense, *, attacker_hp=40, defender_hp=40,
          defender_abilities=(), hits=(True,) * 8):
    from _engine_lite import LiteEngine
    rules = H.rules()
    for unit_type, selected in [('Fighter', attack), ('Skeleton', defense)]:
        rules['units'][unit_type] = H._unit_type(
            unit_type, alignment='neutral', weapons=[selected])
    rules['units']['Skeleton']['abilities'] = list(defender_abilities)
    units = [H._unit('a', 'Fighter', 1, 2, 2, leader=True, hp=attacker_hp),
             H._unit('d', 'Skeleton', 2, 3, 2, leader=True, hp=defender_hp)]
    spec = H.spec(units=units, terrain=['Gg'] * (H.WIDTH * H.HEIGHT), fog=False)
    engine = LiteEngine(json.dumps(rules), json.dumps(spec))
    engine.inject_hits(json.dumps(hits))
    result = H.step(engine, dict(kind='attack', unit='a', target='d', weapon=0))
    return engine, result['strikes']


def unit(engine, identifier):
    return next((u for u in H.observe(engine, 1)['units'] if u['id'] == identifier), None)


class WeaponCoverageCompletionTests(unittest.TestCase):
    def test_stun_requires_hit_and_surviving_target(self):
        for hits, hp, expected in [((True, False), 40, ['stunned']),
                                   ((False, False), 40, []),
                                   ((True,), 1, None)]:
            with self.subTest(hits=hits, hp=hp):
                engine, _ = fight(weapon(specials=['stun']), weapon(),
                                  defender_hp=hp, hits=hits)
                target = unit(engine, 'd')
                self.assertEqual(None if target is None else target['status'], expected)

    def test_absorb_uses_opponents_selected_weapon_on_both_sides(self):
        for percent, expected in [(60, 4), (75, 5)]:
            with self.subTest(percent=percent):
                _, strikes = fight(
                    weapon(specials=['absorb'], opponent_damage_percent=percent),
                    weapon(specials=['absorb'], opponent_damage_percent=percent))
                self.assertEqual([s['damage'] for s in strikes], [expected, expected])

    def test_deflect_applies_only_from_defending_weapon(self):
        _, strikes = fight(weapon(specials=['deflect'], defense_cth_sub=10),
                           weapon(specials=['deflect'], defense_cth_sub=10))
        self.assertEqual([(s['attacker'], s['chance']) for s in strikes],
                         [('a', 30), ('d', 40)])

    def test_greater_drains_default_rounding_immunity_and_overkill(self):
        for percent, hp, immune, expected in [(None, 40, False, 23),
                                             (100, 40, False, 27),
                                             (100, 3, False, 23),
                                             (100, 40, True, 20)]:
            with self.subTest(percent=percent, hp=hp, immune=immune):
                attack = weapon(specials=['drains'])
                if percent is not None:
                    attack['drain_percent'] = percent
                engine, _ = fight(attack, weapon(strikes=0), attacker_hp=20,
                                  defender_hp=hp,
                                  defender_abilities=['undrainable'] if immune else [])
                self.assertEqual(unit(engine, 'a')['hp'], expected)

    def test_shock_and_swift_limit_retaliation_only_on_offense(self):
        for special, limit in [('shock', 1), ('swift', 0)]:
            with self.subTest(special=special):
                _, strikes = fight(weapon(specials=[special], opponent_attacks=limit),
                                   weapon(strikes=3, damage=1))
                self.assertEqual(sum(s['attacker'] == 'd' for s in strikes), limit)
                _, strikes = fight(weapon(strikes=3, damage=1),
                                   weapon(specials=[special], opponent_attacks=limit))
                self.assertEqual(sum(s['attacker'] == 'a' for s in strikes), 3)


if __name__ == '__main__':
    unittest.main()
