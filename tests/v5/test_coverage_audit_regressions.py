"""Capture fidelity checks for the independent rule-definition audit."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from lupa import LuaRuntime

from engine_lite.freeze import freeze_captures


ROOT = Path(__file__).resolve().parents[2]


def capture_declarations(abilities='{}', specials='{}', terrain_codes=('Gg',)):
    lua = LuaRuntime(unpack_returned_tuples=True)
    lua.execute("local abilities=" + abilities + "; local specials=" + specials + """
        local cfg = {id='Audit Unit', {'abilities', abilities}}
        wesnoth = {game_config={version='1.18.8'}, terrain_types=setmetatable({Gg={}},{__index=function() return {} end}),
            unit_types={['Audit Unit']={cost=10, advances_to={}, __cfg=cfg, variations={}}},
            units={create=function()
                return {max_hitpoints=30, max_moves=5, vision=5, level=1,
                    max_experience=40, alignment='neutral', status={},
                    attacks={{name='audit', damage=3, number=2, type='blade', range='melee',
                        __cfg={{'specials', specials}}}},
                    __cfg=cfg, movement_on=function() return 1 end,
                    defense_on=function() return 60 end,
                    resistance_against=function() return 0 end}
            end}}
    """)
    exporter = lua.execute((ROOT / 'engine_lite/lua/export_rules.lua').read_text(encoding='utf-8'))
    return exporter.capture(lua.table_from(dict(
        source_version='1.18.8', source_build_sha256='audit-build', scope='core',
        terrain_codes=lua.table_from(terrain_codes)))).units['Audit Unit']


class StandardDeclarationCaptureTests(unittest.TestCase):
    def test_healing_amount_and_poison_are_taken_from_the_declaration(self):
        for amount in (4, 8):
            unit = capture_declarations("{{'heals', {id='healing', value=" + str(amount) + """,
                poison='slowed', affect_allies=true, affect_self=false,
                {'affect_adjacent', {}}}},
                {'heals', {id='curing', poison='cured', affect_allies=true,
                    affect_self=false, {'affect_adjacent', {}}}}}
            """)
            self.assertEqual(unit.healing_amount, amount)
            self.assertEqual(unit.healing_poison, 'cured')

    def test_illumination_and_typed_plague_use_semantic_tags(self):
        unit = capture_declarations("""{{'illuminates', {id='illumination', value=25,
            max_value=25, cumulative=false, affect_self=true}}}""",
            "{{'plague', {id='plague(Audit Egg)', type='Audit Egg'}}}")
        self.assertEqual(list(unit.abilities.values()), ['illuminates'])
        self.assertEqual(list(unit.weapons[1].specials.values()), ['plague'])
        self.assertEqual(unit.weapons[1].plague_type, 'Audit Egg')
        self.assertEqual(len(unit.unsupported), 0)

    def test_custom_event_and_nonstandard_parameters_are_not_mapped(self):
        unit = capture_declarations("""{{'illuminates', {id='illumination', value=50,
            max_value=50, cumulative=false, affect_self=true}},
            {'heals', {id='healing', value=32, poison='cured', affect_allies=true,
                affect_self=false, {'affect_adjacent', {}}}}}""",
            "{{'dummy', {id='SotA_plague'}}, {'plague', {id='plague', {'filter_opponent', {level=1}}}}}")
        self.assertIn('SotA_plague', list(unit.weapons[1].specials.values()))
        self.assertIn('illuminates_parameters:illumination', list(unit.unsupported.values()))
        self.assertIn('heals_parameters:healing', list(unit.unsupported.values()))
        self.assertIn('plague_parameters:plague', list(unit.unsupported.values()))

    def test_standard_hides_expand_actual_terrain_layers(self):
        terrain_codes=('Gg', 'Gg^Vh', 'Wog', 'Wog^Vm', 'Gg^Fet', 'Hh^Qhhf')
        for identifier, pattern, expected in (
            ('concealment', '*^V*', ['Gg^Vh', 'Wog^Vm']),
            ('ambush', '*^F*,*^Qhhf,*^Qhuf', ['Gg^Fet', 'Hh^Qhhf']),
            ('submerge', 'Wo*^*', ['Wog', 'Wog^Vm']),
        ):
            unit = capture_declarations("{{'hides', {id='"+identifier+"""', affect_self=true,
                {'filter', {{'filter_location', {terrain='"""+pattern+"'}}}}}}}",
                terrain_codes=terrain_codes)
            self.assertEqual(list(unit.concealment_terrains.values()), expected)
            self.assertEqual(len(unit.unsupported), 0)

    def test_feeding_is_only_the_unfiltered_standard_dummy(self):
        ordinary = capture_declarations("{{'dummy', {id='feeding'}}}")
        self.assertEqual(list(ordinary.abilities.values()), ['feeding'])
        self.assertEqual(len(ordinary.unsupported), 0)
        conditional = capture_declarations("{{'dummy', {id='feeding', {'filter', {level=2}}}}}")
        self.assertIn('feeding_parameters', list(conditional.unsupported.values()))


class StandardHealingEngineTests(unittest.TestCase):
    def healing_game(self, *, healer_side=2, amount=8, poison='cured',
                     patient_side=2, poisoned=False, resting=False):
        from tests.v5 import helpers as H
        rules = H.rules()
        rules['units']['Healer'] = H._unit_type('Healer', abilities=['healing', 'curing'],
            healing_amount=amount, healing_poison=poison)
        patient = H._unit('patient', 'Fighter', patient_side, 4, 2, hp=20, leader=True)
        patient['acted'] = not resting
        patient['status'] = ['poisoned'] if poisoned else []
        healer = H._unit('healer', 'Fighter', healer_side, 3, 2, leader=True)
        healer['unit_type'] = 'Healer'
        spec = H.spec(sides=3, fog=False, units=[patient, healer,
            H._unit('leader1', 'Fighter', 1, 0, 0, leader=True),
            H._unit('leader2', 'Fighter', 2, 7, 0, leader=True),
            H._unit('leader3', 'Fighter', 3, 7, 5, leader=True)])
        for side in spec['sides'][1:]:
            side['team'] = 'allies'
        engine = H.engine(game_spec=spec, rules_data=rules)
        H.step(engine, dict(kind='end_turn'))
        return next(u for u in H.observe(engine, patient_side)['units'] if u['id']=='patient')

    def test_heal_eight_and_allied_patient_use_the_healers_turn(self):
        self.assertEqual(self.healing_game()['hp'], 28)
        self.assertEqual(self.healing_game(patient_side=3)['hp'], 28)

    def test_own_curer_cures_but_allied_curer_only_suppresses_poison(self):
        own = self.healing_game(poisoned=True)
        self.assertEqual(own['hp'], 20)
        self.assertNotIn('poisoned', own['status'])
        allied = self.healing_game(poisoned=True, healer_side=3)
        self.assertEqual(allied['hp'], 20)
        self.assertIn('poisoned', allied['status'])

    def test_rest_healing_is_added_even_while_poison_is_suppressed(self):
        patient = self.healing_game(poisoned=True, poison='slowed', resting=True)
        self.assertEqual(patient['hp'], 22)
        self.assertIn('poisoned', patient['status'])


class StandardConcealmentEngineTests(unittest.TestCase):
    def test_village_hider_is_revealed_and_stops_a_skirmisher(self):
        from tests.v5 import helpers as H
        rules = H.rules()
        rules['units']['Hider'] = H._unit_type('Hider', level=0,
            abilities=['concealment'], concealment_terrains=['Gg^Vh'])
        rules['units']['Fighter']['abilities'] = ['skirmisher']
        hidden = H._unit('hidden', 'Fighter', 2, 2, 2)
        hidden['unit_type'] = 'Hider'
        spec = H.spec(fog=False, units=[hidden,
            H._unit('player', 'Fighter', 1, 0, 0, leader=True),
            H._unit('enemy', 'Fighter', 2, 7, 5, leader=True)])
        engine = H.engine(game_spec=spec, rules_data=rules)
        self.assertNotIn('hidden', [u['id'] for u in H.observe(engine, 1)['units']])
        H.step(engine, dict(kind='move', unit='player', to=9))
        units = {u['id']: u for u in H.observe(engine, 1)['units']}
        self.assertIn('hidden', units)
        self.assertEqual(units['player']['moves'], 0)


class StandardFeedingEngineTests(unittest.TestCase):
    def feeding_game(self, *, defending=False, immune=False, advance=False):
        from tests.v5 import helpers as H
        rules = H.rules()
        rules['units']['Feeder'] = H._unit_type('Feeder', hp=40, abilities=['feeding'],
            weapons=[dict(id='bite', damage=8, strikes=1, damage_type='blade', range='melee')],
            experience=8 if advance else 100, advances_to=['Fed Veteran'] if advance else [])
        rules['units']['Fed Veteran'] = H._unit_type('Fed Veteran', hp=50, abilities=['feeding'])
        rules['units']['Victim'] = H._unit_type('Victim', hp=40,
            abilities=['unplagueable'] if immune else [],
            weapons=[dict(id='tap', damage=0, strikes=1, damage_type='blade', range='melee')])
        feeder = H._unit('feeder', 'Fighter', 2 if defending else 1, 4 if defending else 3, 2, hp=20, leader=True)
        feeder['unit_type'] = 'Feeder'
        victim = H._unit('victim', 'Fighter', 1 if defending else 2, 3 if defending else 4, 2, hp=1)
        victim['unit_type'] = 'Victim'
        spec = H.spec(fog=False, units=[feeder, victim,
            H._unit('leader1', 'Fighter', 1, 0, 0, leader=True),
            H._unit('leader2', 'Fighter', 2, 7, 5, leader=True)])
        engine = H.engine(game_spec=spec, rules_data=rules)
        engine.inject_hits(json.dumps([True, True]))
        H.step(engine, dict(kind='attack', unit='victim' if defending else 'feeder',
                           target='feeder' if defending else 'victim', weapon=0))
        return H, engine

    def test_feeding_works_on_attack_and_retaliation_and_survives_snapshot(self):
        for defending in (False, True):
            H, engine = self.feeding_game(defending=defending)
            unit = next(u for u in H.snapshot(engine)['game']['units'] if u['id']=='feeder')
            self.assertEqual(unit['hp'], 21)
            self.assertEqual(unit['feeding_bonus'], 1)
            saved = H.snapshot(engine)
            H.restore(engine, saved)
            self.assertEqual(H.snapshot(engine), saved)

    def test_unplagueable_victims_do_not_feed(self):
        H, engine = self.feeding_game(immune=True)
        unit = next(u for u in H.snapshot(engine)['game']['units'] if u['id']=='feeder')
        self.assertEqual(unit['hp'], 20)
        self.assertEqual(unit.get('feeding_bonus', 0), 0)

    def test_feeding_max_hp_bonus_is_preserved_on_advancement(self):
        H, engine = self.feeding_game(advance=True)
        unit = next(u for u in H.snapshot(engine)['game']['units'] if u['id']=='feeder')
        self.assertEqual(unit['unit_type'], 'Fed Veteran')
        self.assertEqual(unit['hp'], 51)
        self.assertEqual(unit['feeding_bonus'], 1)


class RawDefinitionCaptureTests(unittest.TestCase):
    def test_capture_preserves_nested_wml_in_json_object_keys(self):
        lua = LuaRuntime(unpack_returned_tuples=True)
        lua.execute("""
            local cfg = {id='Audit Unit', hitpoints=30,
                {'abilities', {{'illuminates', {id='illumination', value=25}}}},
                {'event', {name='die', {'lua', {code='return true'}}}},
                {'trait', {id='audit_trait', {'effect', {apply_to='hitpoints', increase=4}}}}}
            wesnoth = {game_config={version='1.18.8'},
                terrain_types={Gg={}},
                unit_types={['Audit Unit']={cost=10, advances_to={}, __cfg=cfg,
                    variations={test={__cfg={id='Audit Unit', {'attack', {damage=3}}}}}}},
                units={create=function()
                    return {max_hitpoints=30, max_moves=5, vision=5, level=1,
                        max_experience=40, alignment='neutral', status={}, attacks={},
                        __cfg=cfg, movement_on=function() return 1 end,
                        defense_on=function() return 60 end,
                        resistance_against=function() return 0 end}
                end}}
        """)
        exporter = lua.execute((ROOT / 'engine_lite/lua/export_rules.lua').read_text(encoding='utf-8'))
        captured = exporter.capture(lua.table_from(dict(
            source_version='1.18.8', source_build_sha256='audit-build', scope='core',
            terrain_codes=lua.table_from(['Gg']))))

        def json_object(value):
            if not hasattr(value, 'items'):
                return value
            result = {}
            for key, child in value.items():
                # Mixed numeric/attribute keys have no portable JSON table shape.
                self.assertIsInstance(key, str)
                result[key] = json_object(child)
            return result

        raw = json.loads(json.dumps(json_object(captured.raw_definitions)))['Audit Unit']
        self.assertEqual(raw['id'], 'Audit Unit')
        self.assertEqual(raw['1']['1'], 'abilities')
        self.assertEqual(raw['1']['2']['1']['2']['value'], 25)
        self.assertEqual(raw['2']['2']['1']['2']['code'], 'return true')
        self.assertEqual(raw['3']['2']['1']['2']['increase'], 4)
        variants = json_object(captured.variations)
        self.assertEqual(variants['Audit Unit']['test']['1']['2']['damage'], 3)


class RawDefinitionFreezeTests(unittest.TestCase):
    def capture(self):
        manifest = dict(files=[dict(path='data/core.cfg', sha256='audit')],
                        required_scopes=['core'])
        digest = hashlib.sha256(json.dumps(manifest, sort_keys=True,
                                          separators=(',', ':')).encode()).hexdigest()
        manifest['manifest_sha256'] = digest
        unit = dict(id='Audit Unit', hp=30, moves=5, experience=40,
                    movement={'Gg': 1}, defense={'Gg': 40},
                    resistance={kind: 100 for kind in
                                ('blade', 'pierce', 'impact', 'fire', 'cold', 'arcane')},
                    abilities=[], weapons=[], advances_to=[])
        return dict(source_version='1.18.8', source_build_sha256=digest,
                    source_manifest=manifest, scope='core', expected_units=['Audit Unit'],
                    units={'Audit Unit': unit}, terrains={'Gg': dict(id='Gg')},
                    raw_definitions={'Audit Unit': {'id': 'Audit Unit',
                        '1': {'1': 'trait', '2': {'id': 'audit_trait'}}}},
                    variations={'Audit Unit': {'test': {'id': 'Audit Unit',
                        '1': {'1': 'attack', '2': {'damage': 3}}}}})

    def freeze(self, capture):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'capture.json'
            path.write_text(json.dumps(capture), encoding='utf-8')
            return freeze_captures([path], Path(directory) / 'frozen')

    def test_valid_raw_capture_keeps_acceptance_pending(self):
        catalog = self.freeze(self.capture())
        self.assertFalse(catalog['complete'])
        self.assertFalse(catalog['native_accepted'])
        self.assertFalse(catalog['performance_accepted'])

    def test_freeze_rejects_null_wml_children_in_raw_definitions_and_variations(self):
        for field in ('raw_definitions', 'variations'):
            with self.subTest(field=field):
                capture = copy.deepcopy(self.capture())
                cfg = capture[field]['Audit Unit']
                if field == 'variations':
                    cfg = cfg['test']
                cfg['1'] = None
                with self.assertRaisesRegex(ValueError, 'null WML child'):
                    self.freeze(capture)


if __name__ == '__main__':
    unittest.main()
