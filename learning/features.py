"""Ordered input contract. Lua consumes the same exported names and scales."""
from pathlib import Path
import json
import os

from .rules_catalog import load as load_catalog, resolve_dir

VERSION = 5
RULES_DIR = resolve_dir()
RULES_PATH = RULES_DIR / 'catalog.json'
if (RULES_DIR / 'rules.json').exists():
    _CATALOG = load_catalog(RULES_DIR, require_accepted=False)
    VOCABULARY = _CATALOG['vocabulary']
else:
    _CATALOG = None
    VOCABULARY = json.loads(Path(__file__).with_name('unit_vocabulary.json').read_text(encoding='utf-8'))
UNIT_TYPES = VOCABULARY['units'] if isinstance(VOCABULARY, dict) else VOCABULARY
DAMAGE_TYPES = ('blade', 'pierce', 'impact', 'fire', 'cold', 'arcane')
TERRAINS = dict(flat='Gg', forest='Gg^Fet', hills='Hh', mountain='Mm', water='Ww', swamp='Ss')
SPECIALS = ('poison', 'slow', 'drains', 'magical', 'marksman', 'charge', 'firststrike', 'berserk')
GLOBAL = [
    ('initial_opponents', 8), ('size_duel', 1), ('size_medium', 1), ('size_large', 1),
    ('known_alive', 8), ('alive_unknown', 1), ('gold', 200), ('income', 20),
    ('own_units', 40), ('own_hp', 1500), ('leader_hp_fraction', 1),
    ('leader_visible_threat', 10), ('lawful_bonus', 25), ('turn', 30),
    ('visible_enemies', 40), ('known_owned_villages', 20),
    ('teammates', 8), ('visible_allied_units', 40), ('visible_allied_hp', 1500),
    ('nearest_allied_leader', 50),
]
OPPONENT = [
    ('visible_units', 40), ('visible_hp', 1500), ('visible_cost', 600),
    ('visible_leaders', 2), ('nearest_to_own_leader', 50),
    ('known_villages', 20), ('ever_seen', 1), ('alive_unknown', 1),
]
ACTION = [
    ('end_turn', 1), ('recruit', 1), ('move', 1), ('attack', 1), ('move_attack', 1),
    ('unit_hp_fraction', 1), ('unit_cost', 50), ('movement_used', 10),
    ('enemy_approach', 20), ('village_gain', 1), ('healing', 8), ('defense', 100),
    ('friendly_support', 10), ('visible_threat', 10), ('expected_enemy_damage', 50),
    ('expected_self_damage', 50), ('kill_probability', 1), ('death_probability', 1),
    ('target_leader', 1), ('own_leader', 1), ('gold_cost', 50),
    ('village_approach', 20), ('remaining_moves', 10), ('combat_predicted', 1),
]

COMPOSITION = [('level0', 40), ('level1', 40), ('level2plus', 40), ('fast', 40), ('injured', 40)]
COMPOSITION += [(f'damage_{t}', 40) for t in DAMAGE_TYPES]
GLOBAL += [(prefix + name, scale) for prefix in ('own_', 'enemy_') for name, scale in COMPOSITION]
GLOBAL += [('remaining_unit_moves', 200), ('previous_end_turns', 30), ('repeated_moves', 100)]
OPPONENT += COMPOSITION
ACTION += [('max_hp', 100), ('max_moves', 10), ('unit_level', 4)]
ACTION += [('alignment_' + a, 1) for a in ('lawful', 'neutral', 'chaotic', 'liminal')]
ACTION += [('resistance_' + t, 100) for t in DAMAGE_TYPES]
ACTION += [(field + '_' + t, scale) for t in TERRAINS for field, scale in [('move_cost', 10), ('terrain_defense', 100)]]
for slot in range(1, 4):
    ACTION += [(f'weapon{slot}_{name}', scale) for name, scale in [('damage', 50), ('strikes', 10), ('melee', 1), ('ranged', 1)]]
    ACTION += [(f'weapon{slot}_{t}', 1) for t in DAMAGE_TYPES + SPECIALS]
ACTION += [('village_' + owner, 1) for owner in ('own', 'ally', 'neutral', 'enemy', 'unknown')]
ACTION += [('goal_progress', 50), ('repeated_move', 1), ('unit_type_index', 1)]

ENTITY = [('x', 1), ('y', 1), ('hp', 100), ('max_hp', 100), ('moves', 10),
          ('max_moves', 10), ('attacks_left', 2), ('experience', 100), ('max_experience', 100),
          ('level', 4), ('leader', 1), ('own', 1), ('ally', 1), ('enemy', 1),
          ('poisoned', 1), ('slowed', 1), ('petrified', 1), ('age', 30)]
ENTITY += [(name, scale) for name, scale in ACTION[27:-8]]
# Keep the legacy entity fields independent of candidate-only tactical features.
ENTITY += [('next_round', 1)]
MOVE_FEATURES = [('move_tactical', 50), ('move_gain', 25), ('move_risk', 50),
                 ('move_risk_delta', 50), ('move_home_distance', 50),
                 ('move_own_support', 10), ('move_primary', 1)]
# Unit identity remains the final field consumed by the embedding in Python/Lua.
ACTION[-1:-1] = MOVE_FEATURES

GEOMETRY = ('actor_x', 'actor_y', 'target_x', 'target_y', 'dest_x', 'dest_y',
            'dx', 'dy', 'target_dx', 'target_dy', 'move_distance', 'target_distance',
            'has_actor', 'has_target', 'weapon', 'full')
SPATIAL_CHANNELS = ('known', 'visible', 'own_hp', 'ally_hp', 'enemy_hp', 'village', 'castle', 'water', 'terrain_identity')
TERRAIN_TYPES = VOCABULARY.get('terrains', ['<unknown>']) if isinstance(VOCABULARY, dict) else ['<unknown>']


def select_rules(rules_dir):
    """Bind vocabulary before constructing models; spawned workers inherit it."""
    global RULES_DIR, RULES_PATH, _CATALOG, VOCABULARY
    directory = resolve_dir(rules_dir)
    metadata = load_catalog(directory, require_accepted=False)
    RULES_DIR, RULES_PATH = directory, directory / 'catalog.json'
    _CATALOG = metadata
    VOCABULARY = metadata['vocabulary']
    # Model modules import these lists, so keep their object identities.
    UNIT_TYPES[:] = VOCABULARY['units']
    TERRAIN_TYPES[:] = VOCABULARY['terrains']
    os.environ['WESNOTH_RULES_DIR'] = str(directory)


def _rules_sha256():
    """Resolve the active catalog's rule-file hash without rereading 49 MB.

    Tests and validation tools replace `RULES_PATH` with a synthetic catalog.
    A frozen catalog has the small summary beside it; synthetic directories may
    carry only the catalog, whose embedded hash is still authoritative.
    """
    if not RULES_PATH.exists():
        return None
    summary = RULES_PATH.parent / 'catalog-summary.json'
    if summary.exists():
        metadata = json.loads(summary.read_text(encoding='utf-8'))
    else:
        metadata = json.loads(RULES_PATH.read_text(encoding='utf-8'))
    return metadata.get('rules_file_sha256')


def schema():
    return dict(version=VERSION, candidate_selection=dict(version='fixed-20000-v4', combat=12, recruit=12, move=12, actionable=36, end_turn=1), normalization='value / scale, clipped to [-4, 4]; unit_type_index is an unscaled integer',
                global_features=GLOBAL, opponent_features=OPPONENT, action_features=ACTION,
                unit_types=UNIT_TYPES, damage_types=DAMAGE_TYPES, terrains=TERRAINS, weapon_specials=SPECIALS,
                entity_features=ENTITY, geometry=list(GEOMETRY), spatial_channels=list(SPATIAL_CHANNELS),
                terrain_types=TERRAIN_TYPES, architecture_id='relational_v5',
                coordinates='1-based odd-q offset; normalized x/width,y/height; cube hex distance',
                rules_sha256=_rules_sha256(),
                unknown_alive='known_alive=0, alive_unknown=1; no hidden-unit inference',
                missing_village_owner='unknown until tile observed; last observed owner retained')
