"""Freeze and statically check the single paired #328 design."""
import argparse
from pathlib import Path

from learning.common import read_json, sha256
from learning.lite_policy import game_spec
from learning.maps import bind_scenario, freeze_map, run_family
from learning.schedule import evaluation_jobs
from learning.tasks import reward_config
from verification.duel_ppo_comparison_20261106.audit import board_digest, initial_audit, write_new
from verification.ppo_batch_comparison_20261107.panels import INPUTS as BASE, roster
from verification.ppo_opponent_protocol_20261114.preflight import INPUTS as OPPONENT, exposure
from verification.ppo_terminal_return_20261108.driver import CATALOG, PARENT, RULES, WESNOTH_DATA

HERE = Path(__file__).resolve().parent
MAPS = {'fallenstar_lake': '2p_Fallenstar_Lake.map', 'sullas_ruins': '2p_Sullas_Ruins.map'}
MAP_SEEDS = {'fallenstar_lake': 2026111451, 'sullas_ruins': 2026111452}
ROLES = ('greedy', 'astra')


def schedule(output, inputs, addon, control, wesnoth, deadline, board_dir=HERE/'boards'):
    jobs = []
    for name, identity in inputs['maps'].items():
        path = board_dir/f'{name}.json'
        captured = read_json(path)
        board = captured['board']
        if sha256(path) != identity['file_sha256'] or board_digest(board) != identity['board_sha256']:
            raise ValueError(f'frozen evaluation board differs for {name}')
        for role in ROLES:
            for job in evaluation_jobs(output, addon, control, [control], 30, identity['seed'],
                                       deadline, wesnoth, label=f'final-{name}-{role}',
                                       formats=['duel'], scenarios=roster('holdout')):
                job.update(engine='lite', rules_dir=str(RULES), allow_approximate=True,
                           score_only_astra=True, score_only_policy=True, map_override=board,
                           task_id=inputs['task_id'], reward_config=reward_config(mode='fixed'),
                           combat_choice=role)
                job['meta'].update(map=name, map_sha256=identity['file_sha256'],
                                   rules_sha256=inputs['rules_sha256'], combat_choice=role)
                job['game_family'] = run_family(job)
                bind_scenario(job)
                jobs.append(job)
    return sorted(jobs, key=lambda job: (job['meta']['map'], job['meta']['block'],
                                       job['meta']['rotation'], job['combat_choice']))


def preflight(jobs, rules):
    pairs = {}
    for job in jobs:
        meta = job['meta']
        seat, = meta['policy_sides']
        spec = game_spec(job, rules)
        if len(spec['units']) != 2 or not all(unit['leader'] for unit in spec['units']):
            raise ValueError('holdout does not initialize a standard duel')
        if any(unit not in rules['units'] for side in spec['sides'] for unit in side['recruit']):
            raise ValueError('holdout recruit roster is incomplete')
        key = meta['map'], meta['block'], meta['rotation']
        role = job['combat_choice']
        pair = pairs.setdefault(key, {})
        if role in pair:
            raise ValueError('duplicate matched role')
        pair[role] = [job['scenario_family'], job['seed'], job['factions'], seat]
    if len(jobs) != 240 or len(pairs) != 120 or len({j['id'] for j in jobs}) != 240:
        raise ValueError('holdout needs 240 unique jobs over 120 paired slots')
    for name in MAPS:
        blocks = set()
        for block in range(30):
            rows = [pairs[name, block, rotation] for rotation in (0, 1)]
            if any(set(row) != set(ROLES) or row['astra'] != row['greedy'] for row in rows):
                raise ValueError('holdout roles are not paired')
            first, second = [row['greedy'] for row in rows]
            if first[:3] != second[:3] or {first[3], second[3]} != {1, 2}:
                raise ValueError('holdout block lacks matching seat rotations')
            blocks.add(tuple(first[2]))
        if blocks != {tuple(row['factions']) for row in roster('holdout')}:
            raise ValueError('holdout faction pair roster differs')
    return [{'map': name, 'block': block, 'rotation': rot,
             'scenario': row['greedy'][0], 'seed': row['greedy'][1],
             'factions': row['greedy'][2], 'learner_seat': row['greedy'][3]}
            for (name, block, rot), row in sorted(pairs.items())]


def freeze(output, opportunity_path, commit, archive):
    opportunity = read_json(opportunity_path)
    if not opportunity['passed']:
        raise ValueError('combat disagreement opportunity did not pass')
    excluded, files = exposure(initial_audit(), opportunity['endpoint'])
    excluded.update(entry['board_sha256'] for entry in OPPONENT['holdout'].values())
    if sha256(RULES/'rules.json') != BASE['rules_sha256']:
        raise ValueError('rules identity differs')
    rules = read_json(RULES/'rules.json')
    boards = output/'boards'
    boards.mkdir(parents=True)
    assets = output/'original'
    assets.mkdir()
    chosen = {}
    for name, filename in MAPS.items():
        source = WESNOTH_DATA/'multiplayer/maps'/filename
        original = read_json(freeze_map(source, name, assets, CATALOG))
        board = original['board']
        source_board = board_digest(board)
        edits = []
        for y, row in enumerate(board['terrain'], 1):
            for x, code in enumerate(row, 1):
                if code == 'Mm^Vhh':
                    row[x-1] = 'Hh^Vhh'
                    edits.append(dict(x=x, y=y, original=code, derived=row[x-1]))
        physical = board_digest(board)
        cells = [code for row in board['terrain'] for code in row]
        if (len(edits) != 2 or excluded & {source_board, physical} or len(set(map(tuple, board['starts']))) != 2
                or not all(code in rules['terrains'] for code in cells)
                or not all(rules['terrains'][board['terrain'][y-1][x-1]]['keep'] for x, y in board['starts'])):
            raise ValueError(f'ineligible held-out board {name}')
        villages = sum(bool(rules['terrains'][code]['village']) for code in cells)
        if not villages:
            raise ValueError(f'holdout lacks villages: {name}')
        excluded.update((source_board, physical))
        del original['source_path']
        original.update(source_asset=str(source.relative_to(WESNOTH_DATA)), source_board_sha256=source_board,
                        terrain_edits=edits)
        destination = boards/f'{name}.json'
        write_new(destination, original)
        chosen[name] = dict(asset=original['source_asset'], source_sha256=original['source_sha256'],
                            source_board_sha256=source_board, board_sha256=physical,
                            file_sha256=sha256(destination), villages=villages,
                            terrain_edits=edits, seed=MAP_SEEDS[name])
    inputs = dict(source_commit=commit, source_archive_sha256=sha256(archive),
                  task_id=BASE['task_id'], rules_sha256=BASE['rules_sha256'], astra=BASE['astra'],
                  checkpoint=BASE['base_bc'], extension_sha256=opportunity['extension_sha256'],
                  opportunity_sha256=sha256(opportunity_path), workers=8,
                  seconds=dict(prepare=600, games=2700, audit=300, total=3600),
                  bootstrap_seed=2026111459, bootstrap_samples=10000, minimum_gain=.05,
                  maps=chosen)
    parent = read_json(PARENT/'manifest.json')
    jobs = schedule(output, inputs, 'greedy-v38', parent['opponents'][0]['path'],
                    parent['baseline']['path'], 0, boards)
    slots = preflight(jobs, rules)
    inputs['slots'] = slots
    write_new(output/'inputs.json', inputs)
    write_new(output/'exposure.json', dict(historical_files=files, excluded_boards=sorted(
        excluded - {value[key] for value in chosen.values() for key in ('board_sha256', 'source_board_sha256')})))
    print({name: (row['villages'], row['terrain_edits']) for name, row in chosen.items()}, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('opportunity', type=Path)
    parser.add_argument('commit')
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    freeze(args.output, args.opportunity, args.commit, args.archive)
