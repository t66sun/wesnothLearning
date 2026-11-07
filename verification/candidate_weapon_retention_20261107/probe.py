"""Pair production Lite decisions and check the same weapon forecast in native."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import time

import _engine_lite

from learning.lite_host import host_modules
from learning.native_transport import NativeTransport
from learning.rules_catalog import resolve_dir
from tests.v5.test_candidate_weapon_retention import combat_slots, engine, witness


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def real_position(path):
    raw = path.read_bytes()
    recorded = json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)
    game = recorded['snapshot']['game']
    # A fresh current-profile game starts from the recorded live units and board.
    # The older expected-damage snapshot itself keeps its original identity.
    spec = dict(game['spec'], units=[u for u in game['units'] if u['hp'] > 0],
                sides=game['sides'], village_owner={i: owner for i, owner in enumerate(game['village_owner']) if owner})
    return spec, recorded['side'], game['turn']


def intent(candidate):
    fields = ('kind', 'x', 'y', 'tx', 'ty', 'ex', 'ey', 'type', 'weapon', 'full')
    return {field: candidate[field] for field in fields if field in candidate}


def paired(rules, spec, side, turn, baseline):
    previous = host_modules()
    for name in ('candidate_selection.lua', 'candidates.lua'):
        previous[name] = (baseline / 'lua' / name).read_text(encoding='utf-8')
    previous['features.lua'] = previous['features.lua'].replace('work-12000-v9', 'work-12000-v8')
    engines = {name: _engine_lite.LiteEngine(json.dumps(rules), json.dumps(spec)) for name in ('v8', 'v9')}
    for name, game in engines.items():
        game.configure_host(json.dumps(previous if name == 'v8' else host_modules()))
        state = json.loads(game.snapshot())
        state['game'].update(current=side, turn=turn)
        game.restore(json.dumps(state))
        game.decision(side)  # One warmup per arm on the uninstrumented production path.

    measures = {name: [] for name in engines}
    final = {}
    for order in (('v8', 'v9'), ('v9', 'v8')):
        for name in order:
            started = time.perf_counter_ns()
            row = json.loads(engines[name].decision(side))
            elapsed_ms = (time.perf_counter_ns() - started) / 1e6
            timing = row['timing']
            assert timing['budget'] == f'work-12000-{name}'
            assert timing['predictions'] <= 36 and timing['work'] <= 12000
            assert len(row['candidates']) == 37
            measures[name].append(dict(decision_ms=elapsed_ms, construction_ms=timing['ms'],
                                       candidates=len(row['candidates']), timing=timing))
            final[name] = row

    before, after = (final[name] for name in ('v8', 'v9'))
    changes = [(intent(a), intent(b)) for a, b in zip(before['candidates'], after['candidates']) if intent(a) != intent(b)]
    for old, new in changes:
        assert old['kind'] in ('attack', 'move_attack') and old['weapon'] != new['weapon'], changes
        assert {k: v for k, v in old.items() if k != 'weapon'} == {k: v for k, v in new.items() if k != 'weapon'}, changes
    a, b = before['timing'], after['timing']
    assert b['work'] - a['work'] == (b['predictions'] - a['predictions']) * 30
    return dict(measurements=measures, slot_changes=changes)


def native_parity(rules, spec, wesnoth):
    lite = engine(rules, spec)
    expected = witness(json.loads(lite.decision(1)))[2]['features'][14:18]
    action = dict(kind='attack', unit='archer-04', target='target-04', weapon=1)
    with NativeTransport(dict(spec, differential_probe=True), wesnoth=str(wesnoth)) as native:
        actual = witness(native.decision(1))
        assert set(actual) == {2}, actual.keys()
        features = actual[2]['features'][14:18]
        assert actual[2]['features'][23] == 1
        assert all(abs(a - b) <= 1e-9 for a, b in zip(features, expected)), (features, expected)
        assert action in native.legal_actions(1)
        oracle = native.step(action)['differential']['oracle']
        forecast = json.loads(lite.forecast(1, action['unit'], action['target'], action['weapon']))
        for role in ('attacker', 'defender'):
            a, b = oracle[role], forecast[role]
            for field in ('average_hp', 'poisoned', 'slowed'):
                assert abs(a[field] - b[field]) <= 1e-9, (role, field, a, b)
            for hp in a['hp_chance'].keys() | b['hp_chance'].keys():
                assert abs(a['hp_chance'].get(hp, 0) - b['hp_chance'].get(hp, 0)) <= 1e-9, (role, hp, a, b)
    return dict(executable_sha256=digest(wesnoth), action=action, native_features=features,
                lite_features=expected, native_forecast=oracle, lite_forecast=forecast)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--real-board', type=Path)
    parser.add_argument('--wesnoth', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    path = resolve_dir() / 'rules.json'
    rules = json.loads(path.read_text())
    spec = combat_slots(rules)
    result = dict(rules_sha256=digest(path), extension_sha256=digest(_engine_lite.__file__))
    if args.wesnoth:
        result['native_parity'] = native_parity(rules, spec, args.wesnoth)
    else:
        archived, side, turn = real_position(args.real_board)
        result.update(real_fixture_sha256=digest(args.real_board), real_side=side, real_turn=turn,
                      combat_slots=paired(rules, spec, 1, 1, args.baseline),
                      real_board=paired(rules, archived, side, turn, args.baseline))
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
