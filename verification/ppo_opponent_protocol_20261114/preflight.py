"""Verify the frozen opponent experiment inputs without collecting any games."""
from collections import Counter, defaultdict
import json
from pathlib import Path
import shutil

from learning.common import ROOT, read_json, sha256
from learning.lite_policy import game_spec
from learning.maps import SPLITS, frozen_map
from verification.duel_ppo_comparison_20261106.audit import board_digest, initial_audit
from verification.ppo_batch_comparison_20261107 import panels
from verification.ppo_batch_comparison_20261107.driver import bc_endpoint
from verification.ppo_batch_contract_20261107.driver import ordinal_rollouts
from verification.ppo_terminal_return_20261108.driver import CATALOG, PARENT, RULES, WESNOTH_DATA

HERE = Path(__file__).resolve().parent
INPUTS = read_json(HERE / 'inputs.json')
ACCEPTANCE = PARENT.parents[5]


def add_boards(value, exposed):
    if isinstance(value, list):
        for row in value:
            add_boards(row, exposed)
    elif isinstance(value, dict):
        if 'map_override' in value:
            exposed.add(board_digest(value['map_override']))
            return
        for key, item in value.items():
            if key == 'board_sha256':
                exposed.add(item)
            elif key != 'terrain':
                add_boards(item, exposed)


def exposure(initializer, endpoint):
    exposed = {digest for source in (initializer, endpoint)
               for digests in source['exposure']['boards'].values() for digest in digests}
    names = {name for split in SPLITS.values() for maps in split.values() for name in maps}
    exposed.update(board_digest(frozen_map(name)[0]) for name in names)
    exposed.update(board_digest(read_json(path)) for path in (ROOT / 'vendor/arena/maps').glob('arena*.json'))
    old = ACCEPTANCE / 'ppo306_20261108_Miwoyq/source/runs/ppo306'
    batch = ACCEPTANCE / 'ppo269_shared_20261107_gzzXd6/experiment'
    paths = list((PARENT.parents[1] / 'evaluation').glob('*/plan.json'))
    assert len(paths) == 2
    batch_plans = list(batch.glob('*-result/plan.json'))
    assert len(batch_plans) == 6
    terminal_plans = list(old.glob('holdout/*/plan.json')) + list(old.glob('validation/*/plan.json'))
    assert len(terminal_plans) == 3
    terminal_schedules = list((old / 'cells').glob('*/duel/schedules/*.json'))
    assert terminal_schedules
    paths += batch_plans + terminal_plans + terminal_schedules
    paths += [old / 'launch.json', ACCEPTANCE / 'ppo312_20261110_lNyy9W/launch.json',
              ROOT / 'verification/ppo_batch_comparison_20261107/inputs.json',
              ROOT / 'verification/duel_ppo_comparison_20261106/inputs.json']
    for path in paths:
        add_boards(read_json(path), exposed)
    return exposed, len(paths)


def check_holdout(exposed, parent):
    catalog = read_json(CATALOG)
    inventory = {digest for capture in catalog['captures']
                 for digest in capture['source_manifest']['files'].values()}
    rules = read_json(RULES / 'rules.json')
    assert sha256(RULES / 'rules.json') == panels.INPUTS['rules_sha256']
    report = {}
    for name, frozen in INPUTS['holdout'].items():
        path = HERE / 'boards' / (name + '.json')
        source = WESNOTH_DATA / frozen['native_file']
        data = read_json(path)
        board = data['board']
        physical = board_digest(board)
        assert sha256(source) == data['source_sha256'] == frozen['source_sha256'] in inventory
        assert sha256(path) == frozen['file_sha256']
        assert physical == frozen['board_sha256'] and physical not in exposed
        exposed.add(physical)
        terrains = rules['terrains']
        assert all(cell in terrains for row in board['terrain'] for cell in row)
        assert len(set(map(tuple, board['starts']))) == 2
        assert all(terrains[board['terrain'][y-1][x-1]]['keep'] for x, y in board['starts'])
        assert sum(bool(terrains[cell].get('village')) for row in board['terrain']
                   for cell in row) == frozen['villages']
        jobs = panels.plan_jobs(HERE, 'learner', parent['opponents'][0]['path'],
                                parent['baseline']['path'], 'design', 0, str(RULES), 'holdout',
                                data | dict(file_sha256=sha256(path)))
        blocks = defaultdict(list)
        for job in jobs:
            blocks[job['scenario_family']].append(job)
            spec = game_spec(job, rules)
            assert len(spec['units']) == 2 and all(unit['leader'] for unit in spec['units'])
        assert len(jobs) == 60 and len(blocks) == 30
        assert len({tuple(job['factions']) for job in jobs}) == 30
        for pair in blocks.values():
            assert {job['meta']['policy_sides'][0] for job in pair} == {1, 2}
            assert len({job['seed'] for job in pair}) == 1
        report[name] = dict(board_sha256=physical, jobs=len(jobs), blocks=len(blocks),
                            starts=board['starts'], villages=frozen['villages'])
    return report


def check_training(parent):
    slots = INPUTS['bc_slots']
    assert len(slots) == 9
    totals = {}
    for seed in INPUTS['seeds']:
        maps, factions, seats = Counter(), Counter(), Counter()
        for batch in range(3 * len(slots)):
            jobs = ordinal_rollouts(HERE, 'learner', [], [parent['opponents'][0]['path']],
                                    'support', 38, batch, seed, 0, 'wesnoth',
                                    INPUTS['batch_games'], first_batch=0)
            assert len(jobs) == 8
            bc_jobs = [jobs[i] for i in slots[batch % len(slots)]]
            assert {job['meta']['seat'] for job in bc_jobs} == {1, 2}
            if batch < len(slots):
                for job in bc_jobs:
                    side = job['meta']['seat']
                    maps[job['meta']['map']] += 1
                    factions[job['factions'][side-1]] += 1
                    seats[side] += 1
        assert maps == dict(arena2=9, the_freelands=3, sablestone_delta=3, weldyn_channel=3)
        assert len(factions) == 6 and set(factions.values()) == {3}
        assert seats == {1: 9, 2: 9}
        totals[seed] = dict(maps=maps, factions=factions, seats=seats)
    return totals


def main():
    initial = initial_audit()
    endpoint = bc_endpoint(PARENT)['endpoint']
    assert all(endpoint[key] == value for key, value in panels.INPUTS['base_bc'].items())
    assert endpoint['version'] == 38
    parent = read_json(PARENT / 'manifest.json')
    prior, files = exposure(initial, endpoint)
    free = shutil.disk_usage(ROOT).free
    assert free >= INPUTS['min_free_bytes']
    assert INPUTS['evaluation']['validation_seed'] == panels.INPUTS['validation_seed']
    assert INPUTS['evaluation']['holdout_seed'] == panels.INPUTS['holdout_seed']
    print(json.dumps(dict(source=str(ROOT), prior_files=files, prior_boards=len(prior),
                          initializer_shards=initial['exposure']['shards'],
                          qualified_bc_shards=endpoint['exposure']['shards'],
                          free_bytes=free, holdout=check_holdout(prior, parent),
                          training=check_training(parent)), indent=2))


if __name__ == '__main__':
    main()
