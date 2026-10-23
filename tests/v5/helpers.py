"""Shared deterministic fixtures for the V5 contract suite.

No real Wesnoth data or native binary is required here. The Rust lite engine is
exercised with an explicit synthetic rules catalogue, and Lua receives the same
rules through the real host bridge. This is rule-validation evidence only; the
tests never claim native-1.18.8 or P1/P2 acceptance.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import math
import random
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT), str(ROOT / 'vendor' / 'arena')):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import torch

from learning.features import VERSION, ACTION, ENTITY, GLOBAL, GEOMETRY, OPPONENT, SPATIAL_CHANNELS, UNIT_TYPES
from learning.formats import FORMATS
from learning.rewards import RewardConfig, FORMULA_ID

WIDTH, HEIGHT = 8, 6

TERRAINS = ('Gg', 'Gg^Fet', 'Gg^Vh', 'Gg^Ch', 'Gg^Kh', 'Hh', 'Mm', 'Ww', 'Ss')
MOVEMENT = {t: 1 for t in TERRAINS}
MOVEMENT.update({'Mm': 2, 'Hh': 2, 'Ss': 2, 'Ww': 99})
DEFENSE = {t: 40 for t in TERRAINS}
DEFENSE.update({'Mm': 50, 'Hh': 50, 'Ss': 60, 'Ww': 60})
RESISTANCE = {t: 100 for t in ('blade', 'pierce', 'impact', 'fire', 'cold', 'arcane')}


def _unit_type(identifier, **overrides):
    value = dict(id=identifier, scope='test', hp=40, moves=5, vision=5, level=1, cost=14,
                 experience=40, alignment='lawful', advances_to=[], weapons=[],
                 movement=dict(MOVEMENT), defense=dict(DEFENSE),
                 resistance=dict(RESISTANCE), abilities=[], unsupported=[],
                 approximation_reasons=[])
    value.update(overrides)
    return value


def rules():
    units = {
        'Fighter': _unit_type('Fighter', weapons=[
            dict(id='sword', damage=5, strikes=3, damage_type='blade', range='melee')]),
        'Archer': _unit_type('Archer', hp=32, cost=15, alignment='neutral', weapons=[
            dict(id='bow', damage=4, strikes=3, damage_type='pierce', range='ranged'),
            dict(id='dagger', damage=3, strikes=2, damage_type='blade', range='melee')]),
        'Skeleton': _unit_type('Skeleton', hp=36, moves=4, cost=13, alignment='chaotic', weapons=[
            dict(id='axe', damage=6, strikes=3, damage_type='blade', range='melee')]),
        'Mage': _unit_type('Mage', hp=28, moves=5, cost=18, experience=44, weapons=[
            dict(id='fireball', damage=7, strikes=3, damage_type='fire', range='ranged',
                 specials=['magical'])]),
        'Ghost': _unit_type('Ghost', hp=30, moves=5, cost=20, weapons=[
            dict(id='touch', damage=4, strikes=4, damage_type='arcane', range='melee',
                 specials=['drains'])]),
    }
    return dict(source_version='1.18.8', rules_version='synthetic-v5', source_hash='synthetic-test-rules',
                units=units,
                terrains={t: dict(id=t, village=t.endswith('^Vh'), castle=t.endswith('^Ch'),
                                  keep=t.endswith('^Kh'), healing=0) for t in TERRAINS})


def terrain_grid(width=WIDTH, height=HEIGHT):
    grid = ['Gg'] * (width * height)

    def put(x, y, code):
        if 0 <= x < width and 0 <= y < height:
            grid[y * width + x] = code
    put(2, 2, 'Gg^Vh')
    put(3, 2, 'Gg^Kh')
    put(3, 1, 'Gg^Ch')
    put(4, 2, 'Gg^Ch')
    put(5, 3, 'Ww')
    put(0, 5, 'Mm')
    put(6, 1, 'Hh')
    put(2, 4, 'Ss')
    return grid


def _unit(identifier, unit_type, side, x, y, *, width=WIDTH, leader=False, hp=None):
    data = rules()['units'][unit_type]
    return dict(id=identifier, unit_type=unit_type, side=side, pos=y * width + x,
                hp=data['hp'] if hp is None else hp, moves=data['moves'], attacks_left=1,
                leader=leader, xp=0, status=[], traits=[], acted=False)


def spec(*, sides=2, seed=7, max_turns=12, width=WIDTH, height=HEIGHT, units=None,
         terrain=None, allow_approximate=True, fog=True, shroud=False):
    team_names = {1: 'A', 2: 'B', 3: 'A', 4: 'B'}
    side_rows = []
    for side in range(1, sides + 1):
        recruits = ['Fighter', 'Archer'] if side in (1, 3) else ['Fighter', 'Skeleton']
        side_rows.append(dict(id=side, team=team_names[side], gold=100, recruit=recruits,
                              fog=fog, shroud=shroud, share_view=False, share_maps=False))
    if units is None:
        units = [
            _unit('p1', 'Fighter', 1, 3, 2, leader=True, width=width),
            _unit('p2', 'Archer', 1, 2, 3, width=width),
            _unit('e1', 'Fighter', 2, 4, 2, leader=True, width=width),
            _unit('e2', 'Skeleton', 2, 5, 4, width=width),
        ]
        if sides >= 3:
            units.append(_unit('a1', 'Mage', 3, 1, 0, leader=True, width=width))
        if sides >= 4:
            units.append(_unit('b1', 'Ghost', 4, 7, 5, leader=True, width=width))
    return dict(width=width, height=height, terrain=terrain or terrain_grid(width, height),
                sides=side_rows, units=units, seed=seed, max_turns=max_turns,
                allow_approximate=allow_approximate)


def host_modules():
    from learning.lite_host import host_modules as build
    return build()


def engine(*, game_spec=None, rules_data=None):
    from _engine_lite import LiteEngine
    rules_data = rules_data or rules()
    game_spec = game_spec or spec()
    instance = LiteEngine(json.dumps(rules_data), json.dumps(game_spec))
    instance.configure_host(json.dumps(host_modules()))
    return instance


def load(value):
    return json.loads(value) if isinstance(value, str) else value


def observe(instance, side=1):
    return load(instance.observe(side))


def legal(instance, side=1):
    return load(instance.legal_actions(side))


def step(instance, action):
    return load(instance.step(json.dumps(action)))


def decision(instance, side=1, *, teacher=False, budget_ms=500):
    return load(instance.decision(side, budget_ms, teacher))


def snapshot(instance):
    return load(instance.snapshot())


def restore(instance, value):
    return load(instance.restore(value if isinstance(value, str) else json.dumps(value)))


def config(**overrides):
    from dataclasses import asdict
    base = asdict(RewardConfig())
    base.update(overrides)
    return base


def record_from_decision(decision_row, *, format_name='duel', source='astra', game_id='game-1',
                         game_family='family-1', side=None, choice=0, actual=None,
                         teacher='gpt6astra', version='v5-test', engine_id='lite-0.1',
                         raw=None):
    side = decision_row.get('side', 1) if side is None else side
    candidates = decision_row['candidates']
    choice = max(0, min(int(choice), len(candidates) - 1))
    if actual is None:
        candidate = candidates[choice]
        fields = {'end_turn': (), 'recruit': ('type', 'x', 'y'),
                  'move': ('x', 'y', 'tx', 'ty', 'full'),
                  'attack': ('x', 'y', 'tx', 'ty', 'weapon'),
                  'move_attack': ('x', 'y', 'tx', 'ty', 'ex', 'ey', 'weapon')}[candidate['kind']]
        actual = dict(kind=candidate['kind'], **{key: candidate[key] for key in fields})
    row = dict(decision_row)
    row.update(schema=VERSION, format=format_name, source=source, game_id=game_id,
               game_family=game_family, side=side, role='astra' if source == 'astra' else source,
               teacher=teacher if source == 'astra' else None, version=version,
               engine_id=engine_id, rules_version='synthetic-v5', rng_version='xoshiro256++-1',
               candidate_version=f'schema{VERSION}-fixed-20000-v3', reward_version=0,
               reward_formula_id=FORMULA_ID, architecture_id='relational_v5',
               reward_config=config(), choice=choice, actual=actual)
    if raw is not None:
        row['reward_raw'] = raw
    elif source == 'policy':
        row['reward_raw'] = dict(economy=0., control=0., explored=0.)
    return row


def validate(row, format_name=None):
    from learning.data import validate_record
    validate_record(row, format_name)
    return row


def pad_candidates(row, count=128):
    candidates = row['candidates']
    while len(candidates) < count:
        copy = json.loads(json.dumps(candidates[len(candidates) % len(candidates)]))
        candidates.append(copy)
    row['candidates'] = candidates
    return row


def model(*, format_name='duel', seed=11):
    from learning.model import Policy
    torch.manual_seed(seed)
    instance = Policy(format_name)
    instance.eval()
    return instance


def synthetic_decision_row(seed=0, *, format_name='duel', source='astra', game_id='game-1',
                           game_family='family-1', turn=1, choice=0):
    """A finite schema-4 row generated through the real Lua capture path."""
    instance = engine(game_spec=spec(seed=seed))
    row = record_from_decision(decision(instance, 1), format_name=format_name, source=source,
                               game_id=game_id, game_family=game_family, choice=choice)
    row['turn'] = turn
    validate(row, format_name)
    return row


def memory_row(row):
    return dict(turn=row.get('turn', 1), global_=row['global'], global_features=row['global'],
                opponents=row['opponents'], spatial=row['spatial'])


def sequence_rows(turns=3, *, decisions_per_turn=2, format_name='duel', source='astra',
                  game_id='seq-1', game_family='family-1', seed=3):
    """Chronological rows whose memory snapshots are real captures from one game."""
    instance = engine(game_spec=spec(seed=seed))
    rows = []
    for turn in range(1, turns + 1):
        input_row = decision(instance, 1)
        for index in range(decisions_per_turn):
            row = record_from_decision(input_row, format_name=format_name, source=source,
                                       game_id=game_id, game_family=game_family,
                                       choice=index % len(input_row['candidates']))
            row['turn'] = turn
            row['decision'] = index
            rows.append(row)
        # Advance one own turn through the real engine.
        for _ in range(2):
            legal_rows = legal(instance, 1)
            if not legal_rows:
                break
            step(instance, {'kind': 'end_turn'})
            break
        while load(instance.observe(1))['current_side'] != 1:
            step(instance, {'kind': 'end_turn'})
    return rows


def attach(rows, prefixes=None):
    from learning.sequences import attach_histories
    return attach_histories(rows, prefixes)


@contextlib.contextmanager
def temporary_directory():
    with tempfile.TemporaryDirectory(dir=ROOT / 'verification' if (ROOT / 'verification').exists() else None) as directory:
        yield Path(directory)


def write_rules_dir(directory, rules_data=None, *, accepted=False, complete=False,
                    native_accepted=False, performance_accepted=False):
    """Build a frozen rules directory for LiteAdapter acceptance tests."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    rules_data = rules_data or rules()
    rules_path = directory / 'rules.json'
    rules_path.write_text(json.dumps(rules_data, sort_keys=True), encoding='utf-8')
    digest = hashlib.sha256(rules_path.read_bytes()).hexdigest()
    catalog = dict(complete=complete, native_accepted=native_accepted,
                   performance_accepted=performance_accepted,
                   rules_file_sha256=digest, source_hash=rules_data['source_hash'])
    (directory / 'catalog.json').write_text(json.dumps(catalog), encoding='utf-8')
    return directory


def stable_step(instance, action):
    """Execute and fail loudly; useful in tests that build deterministic sequences."""
    result = step(instance, action)
    assert result.get('intent') is not None or result.get('finished'), result
    return result


def lua_hex(index, width=WIDTH):
    """One-based Wesnoth hex for a zero-based row-major tile index."""
    return (index % width + 1, index // width + 1)


def ledger_owner(snapshot, side, x, y):
    """Village owner Astra's ledger holds for one one-based hex, or ``None``.

    host.lua files every observed village as ``x*1000+y`` before a teacher
    query, so a stale embedded host.lua shows up here as a missing entry.
    """
    owners = (snapshot.get('host') or {}).get('teacher_memory', {}).get(str(side), {}).get('owners', {})
    return owners.get(str(x * 1000 + y))


def cube_distance(a, b):
    ax, ay = a
    bx, by = b
    aq = ax - 1
    ar = ay - 1 - (aq - (aq % 2)) // 2
    bq = bx - 1
    br = by - 1 - (bq - (bq % 2)) // 2
    return max(abs(aq - bq), abs(ar - br), abs(aq + ar - bq - br))
