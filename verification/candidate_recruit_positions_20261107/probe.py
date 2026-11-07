"""Compare B1 and B2 on two fixed production Lite decisions."""
import argparse
import json
from pathlib import Path
import time

import _engine_lite

from learning.lite_host import host_modules
from learning.rules_catalog import resolve_dir
from tests.v5.test_candidate_recruit_positions import frozen_recruit_support, low_pairs, recruitment_case, recruit_intents
from verification.candidate_weapon_retention_20261107.probe import digest, real_position


def measure(rules, spec, side, turn, baseline):
    modules = host_modules()
    previous = dict(modules)
    previous['candidates.lua'] = (baseline / 'lua/candidates.lua').read_text(encoding='utf-8')
    previous['features.lua'] = previous['features.lua'].replace('work-12000-v10', 'work-12000-v9')
    games = {}
    for name, sources in (('v9', previous), ('v10', modules)):
        game = _engine_lite.LiteEngine(json.dumps(rules), json.dumps(spec))
        game.configure_host(json.dumps(sources))
        state = json.loads(game.snapshot())
        state['game'].update(current=side, turn=turn)
        game.restore(json.dumps(state))
        game.decision(side)
        games[name] = game

    measurements = {name: [] for name in games}
    rows = {}
    for order in (('v9', 'v10'), ('v10', 'v9')):
        for name in order:
            started = time.perf_counter_ns()
            row = json.loads(games[name].decision(side))
            elapsed_ms = (time.perf_counter_ns() - started) / 1e6
            timing = row['timing']
            assert timing['budget'] == f'work-12000-{name}'
            assert timing['predictions'] <= 36 and timing['work'] <= 12000
            assert timing['reaches'] <= 28 and timing['recruit_probes'] <= 192
            assert len(row['candidates']) <= 37
            measurements[name].append(dict(decision_ms=elapsed_ms, construction_ms=timing['ms'],
                                           candidates=len(row['candidates']), timing=timing))
            rows[name] = row

    before, after = (recruit_intents(rows[name]) for name in ('v9', 'v10'))
    nonrecruits = [[a for a in rows[name]['candidates'] if a['kind'] != 'recruit'] for name in ('v9', 'v10')]
    return dict(measurements=measurements, v9_recruits=list(before), v10_recruits=list(after),
                added=sorted(after.keys() - before.keys()), removed=sorted(before.keys() - after.keys()),
                nonrecruits_equal=nonrecruits[0] == nonrecruits[1]), before, after, games['v10']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True, type=Path)
    parser.add_argument('--real-board', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    rules_path = resolve_dir() / 'rules.json'
    rules = json.loads(rules_path.read_text())
    fixture = recruitment_case(rules)
    witness, before, after, game = measure(rules, fixture, 1, 1, args.baseline)
    front, low = frozen_recruit_support()
    before_pairs, after_pairs = low_pairs(before, low), low_pairs(after, low)
    assert not before_pairs and after_pairs
    assert witness['nonrecruits_equal']
    for key in after_pairs[0]:
        assert json.loads(game.execute_candidate(json.dumps(after[key])))['committed']
    assert json.loads(game.observe(1))['sides'][0]['gold'] == 0
    witness.update(low_pairs_before=len(before_pairs), low_pairs_after=len(after_pairs),
                   executed_pair=after_pairs[0], preserved_frontline=sorted(after.keys() & front))

    spec, side, turn = real_position(args.real_board)
    real, *_ = measure(rules, spec, side, turn, args.baseline)
    assert real['measurements']['v9'][0]['timing']['recruit_probes'] > 0
    real.update(side=side, turn=turn, fixture_sha256=digest(args.real_board))
    result = dict(rules_sha256=digest(rules_path), extension_sha256=digest(_engine_lite.__file__),
                  recruit_positions=witness, recorded_turn=real)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
