"""Only the declaration forms added by the rule coverage completion."""
import unittest

from tests.v5.test_coverage_audit_regressions import capture_declarations


class RuleExportCompletionTests(unittest.TestCase):
    def test_core_hides_compile_terrain_and_full_movement_condition(self):
        codes = ('Gg', 'Ds', 'Gg^Fet', 'Ss', 'Ww')
        burrow = capture_declarations("""{{'hides', {id='burrow', affect_self=true,
            {'filter', {formula='if(self.moves = self.max_moves, 1, 0)',
                {'filter_location', {terrain='*^F*,*^Qhhf,*^Qhuf,D*^*'}}}}}}}""",
            terrain_codes=codes)
        self.assertTrue(burrow.concealment_requires_full_moves)
        self.assertEqual(list(burrow.concealment_terrains.values()), ['Ds', 'Gg^Fet'])
        self.assertEqual(list(burrow.unsupported.values()), [])
        swamp = capture_declarations("""{{'hides', {id='swamp_lurk', affect_self=true,
            {'filter', {{'filter_location', {terrain='S*^*'}}}}}}}""", terrain_codes=codes)
        self.assertEqual(list(swamp.concealment_terrains.values()), ['Ss'])
        self.assertEqual(list(swamp.unsupported.values()), [])

    def test_parameterized_weapon_semantics_use_tags(self):
        unit = capture_declarations(specials="""{
            {'drains', {id='greater drains', value=100}},
            {'damage', {id='absorb', apply_to='opponent', multiply=0.6}},
            {'chance_to_hit', {id='deflect', active_on='defense',
                apply_to='opponent', sub=10, cumulative=true}},
            {'attacks', {id='swift', active_on='offense', apply_to='opponent', value=0}},
            {'firststrike', {id='deterrentstrike'}}, {'stun', {id='stun'}}}""")
        weapon = unit.weapons[1]
        self.assertEqual(weapon.drain_percent, 100)
        self.assertEqual(weapon.opponent_damage_percent, 60)
        self.assertEqual(weapon.defense_cth_sub, 10)
        self.assertEqual(weapon.opponent_attacks, 0)
        self.assertEqual(set(weapon.specials.values()),
                         {'drains', 'absorb', 'deflect', 'swift', 'firststrike', 'stun'})
        self.assertEqual(list(unit.unsupported.values()), [])

    def test_regeneration_darkening_and_allied_skirmisher_are_compiled(self):
        unit = capture_declarations("""{
            {'regenerate', {id='regenerates_yec', value=150, poison='cured', affect_self=true}},
            {'illuminates', {id='darkens', value=-25, min_value=-25,
                cumulative=false, affect_self=true}},
            {'skirmisher', {id='distract', affect_self=false, affect_allies=true,
                {'affect_adjacent', {}}}}}""")
        self.assertEqual(unit.regeneration_amount, 150)
        self.assertEqual(unit.regeneration_poison, 'cured')
        self.assertEqual(unit.illumination, -25)
        self.assertIn('distract', list(unit.abilities.values()))
        self.assertEqual(list(unit.unsupported.values()), [])

    def test_unimplemented_filters_are_not_accepted_as_parameterized_rules(self):
        unit = capture_declarations(specials="""{
            {'damage', {id='absorb', apply_to='opponent', multiply=0.6,
                {'filter_opponent', {level=2}}}},
            {'drains', {id='greater drains', value=100, active_on='defense'}}}""")
        self.assertIsNone(unit.weapons[1].opponent_damage_percent)
        self.assertIsNone(unit.weapons[1].drain_percent)
        self.assertGreater(len(unit.unsupported), 0)

    def test_conditional_regeneration_and_healing_preserve_target_filters(self):
        unit = capture_declarations("""{
            {'regenerate', {value=6, affect_self=true,
                {'filter_self', {{'filter_location', {terrain='Dd^*,Ds^*,Hd^*,Rb^*,Rd^*,Re^*'}}}}}},
            {'heals', {id='healing', value=8, poison='slowed', affect_allies=true,
                affect_self=false, {'affect_adjacent', {{'filter', {{'not',
                    {status='dehydration_slowed_by_healer'}}}}}}}},
            {'heals', {id='curing', poison='cured', affect_allies=true,
                affect_self=false, {'affect_adjacent', {}}}}}""",
            terrain_codes=('Gg', 'Ds', 'Dd', 'Hd', 'Rb', 'Re', 'Ss'))
        self.assertEqual(unit.regeneration_amount, 6)
        self.assertEqual(unit.regeneration_poison, 'none')
        self.assertEqual(set(unit.regeneration_terrains.values()), {'Ds', 'Dd', 'Hd', 'Rb', 'Re'})
        self.assertEqual(unit.healing_excluded_status, 'dehydration_slowed_by_healer')
        self.assertTrue(unit.curing_unfiltered)
        self.assertEqual(list(unit.unsupported.values()), [])

    def test_inspire_initiative_and_vanguard_have_finite_compiled_forms(self):
        vanguard = ','.join("""{'leadership', {id='vanguard%d', add=%d,
            affect_allies=false, affect_self=true,
            {'filter_self', {{'filter_adjacent', {count=%d}}}}}}""" % (count-1, 25*(count-1), count)
            for count in range(2, 7))
        unit = capture_declarations("""{
            {'leadership', {id='inspire', value='(25 * (level - other.level + 1))',
                cumulative=false, affect_self=false,
                {'affect_adjacent', {{'filter', {formula='level <= other.level'}}}}}},
            {'firststrike', {id='initiative', affect_allies=true, affect_self=false,
                {'filter_opponent', {{'filter_weapon', {range='melee'}}}},
                {'affect_adjacent', {}}}},
            {'dummy', {id='vanguard'}},""" + vanguard + '}')
        self.assertEqual(set(unit.abilities.values()), {'inspire', 'initiative', 'vanguard'})
        self.assertEqual(list(unit.unsupported.values()), [])


if __name__ == '__main__':
    unittest.main()
