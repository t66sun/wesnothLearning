"""Freeze the #334 Lite duel panel without starting any games."""
import argparse
from pathlib import Path

from learning.common import read_json
from learning.lite_policy import game_spec
from learning.maps import bind_scenario, freeze_map, run_family
from learning.schedule import evaluation_jobs
from learning.tasks import reward_config
from verification.duel_learner_state_20261115 import corpus
from verification.duel_ppo_comparison_20261106.audit import board_digest, initial_audit, write_new
from verification.duel_ppo_comparison_20261106.contract import INPUTS as INIT
from verification.ppo_batch_comparison_20261107.panels import roster
from verification.ppo_opponent_protocol_20261114.preflight import INPUTS as MIXED
from verification.ppo_terminal_return_20261108.driver import CATALOG, HOLDOUT, PARENT, RULES, WESNOTH_DATA

SOURCE_306 = Path('/home/tongshu/acceptance/ppo306_20261108_Miwoyq/source/runs/ppo306')
MAPS = {
    'road_to_weldyn': (HOLDOUT['road_to_weldyn'], 2026111551,
                       'a0712d09f18da79296c9df4d1e62b0bb01af3607eb0cb0371747c6b859bad451'),
    'summer_of_storms': (HOLDOUT['summer_of_storms'], 2026111552,
                         'bb5972c96d25081eafb56c6f171e57dd35b170fe0d2caa6e6e5d4e007d9ee403'),
    'ur_thorodor': (MIXED['holdout']['ur_thorodor']['native_file'], 2026111553,
                    MIXED['holdout']['ur_thorodor']['board_sha256']),
}
CONTROL, TREATMENT = 'teacher', 'learner'
ORDER = [(role, seed) for index, seed in enumerate(corpus.SEEDS)
         for role in ((CONTROL, TREATMENT) if index != 1 else (TREATMENT, CONTROL))]
ROLES = ('bc', *(f'{role}-{seed}' for role, seed in ORDER))
LIMITS = dict(preflight=600, cell=1200, games=5400, audit=1200, total=14400)


def exposure(data, initializer):
    boards = {g['board'] for key in ('teacher', 'learner') for g in data[key]}
    boards.update(digest for values in initializer['exposure']['boards'].values() for digest in values)
    roots = [Path(INIT['parent'])/'duel', PARENT/'duel']
    roots.extend(corpus.SOURCE_RUN/'cells'/f'astra-{seed}'/'duel' for seed in corpus.SOURCE_SEEDS)
    files = 0
    for root in roots:
        paths = sorted((root/'schedules').glob('*.json'))
        if not paths:
            raise ValueError(f'exposure schedules unavailable: {root}')
        for path in paths:
            for job in read_json(path):
                if job['meta'].get('map_partition') in ('train', 'validation'):
                    boards.add(board_digest(job['map_override']))
            files += 1
    return boards, files


def schedule(destination, board_dir, inputs, policies, control, wesnoth, deadline):
    if list(policies) != list(ROLES):
        raise ValueError('panel must include all seven frozen roles')
    jobs = []
    scenarios = roster('holdout')
    for name, identity in inputs['maps'].items():
        path = board_dir/f'{name}.json'
        data = read_json(path)
        if corpus.file_sha(path) != identity['file_sha256'] or board_digest(data['board']) != identity['board_sha256']:
            raise ValueError(f'frozen board differs: {name}')
        for role, addon in policies.items():
            for job in evaluation_jobs(destination, addon, control, [control], 30, identity['seed'],
                                       deadline, wesnoth, label=f'final-{name}-{role}',
                                       formats=['duel'], scenarios=scenarios):
                job.update(engine='lite', rules_dir=str(RULES), allow_approximate=True,
                           score_only_astra=True, score_only_policy=True, map_override=data['board'],
                           task_id=corpus.BASE['task_id'], reward_config=reward_config(mode='fixed'))
                job['meta'].update(map=name, map_sha256=identity['file_sha256'], role=role,
                                   rules_sha256=corpus.BASE['rules_sha256'])
                job['game_family'] = run_family(job)
                bind_scenario(job)
                jobs.append(job)
    return sorted(jobs, key=lambda job: (job['meta']['map'], job['meta']['block'],
                                       job['meta']['rotation'], ROLES.index(job['meta']['role'])))


def slots(jobs, rules):
    layout = {}
    if len(jobs) != 1260 or len({j['id'] for j in jobs}) != 1260:
        raise ValueError('panel requires 1,260 unique job IDs')
    for job in jobs:
        meta = job['meta']
        seat, = meta['policy_sides']
        spec = game_spec(job, rules)
        if (len(spec['units']) != 2 or not all(unit['leader'] for unit in spec['units'])
                or any(unit not in rules['units'] for side in spec['sides'] for unit in side['recruit'])):
            raise ValueError('panel does not initialize a standard six-faction duel')
        row = layout.setdefault((meta['map'], meta['block'], meta['rotation']), {})
        role = meta['role']
        if role in row:
            raise ValueError('duplicate role in paired slot')
        row[role] = dict(scenario=job['scenario_family'], seed=job['seed'], seat=seat, factions=job['factions'])
    result = []
    for name in MAPS:
        distinct = set()
        for block in range(30):
            pair = [layout[name, block, rotation] for rotation in (0, 1)]
            if any(set(row) != set(ROLES) or any(value != row['bc'] for value in row.values()) for row in pair):
                raise ValueError('roles differ within a paired slot')
            left, right = [row['bc'] for row in pair]
            if ({left['seat'], right['seat']} != {1, 2}
                    or any(left[k] != right[k] for k in ('scenario', 'seed', 'factions'))):
                raise ValueError('seat rotation differs within scenario block')
            distinct.add(tuple(left['factions']))
            result.extend(dict(map=name, block=block, rotation=r, **row['bc']) for r, row in enumerate(pair))
        if distinct != {tuple(row['factions']) for row in roster('holdout')}:
            raise ValueError(f'incomplete faction-pair roster for {name}')
    return result


def freeze(output, data_dir, commit, archive):
    audit = read_json(data_dir/'audit.json')
    if not audit['passed']:
        raise ValueError('corpus did not pass the support gate')
    data = read_json(data_dir/'corpus.json')
    board_dir = output/'boards'
    board_dir.mkdir(parents=True)
    excluded, exposure_files = exposure(data, initial_audit())
    maps = {}
    rules = read_json(RULES/'rules.json')
    for name, (asset, seed, expected) in MAPS.items():
        path = freeze_map(WESNOTH_DATA/asset, name, board_dir, CATALOG)
        captured = read_json(path)
        board = captured['board']
        physical = board_digest(board)
        history = SOURCE_306 if name in HOLDOUT else corpus.SOURCE_RUN
        previous = read_json(history/'holdout'/name/'plan.json')['jobs'][0]
        if (physical != expected or board_digest(previous['map_override']) != physical
                or physical in excluded or len(set(map(tuple, board['starts']))) != 2):
            raise ValueError(f'physical holdout identity or exposure differs: {name}')
        terrains = rules['terrains']
        cells = [code for row in board['terrain'] for code in row]
        if any(code not in terrains for code in cells) or any(
                not terrains[board['terrain'][y-1][x-1]]['keep'] for x, y in board['starts']):
            raise ValueError(f'unsupported terrain or start: {name}')
        villages = sum(bool(terrains[code]['village']) for code in cells)
        if not villages:
            raise ValueError(f'holdout has no villages: {name}')
        maps[name] = dict(asset=asset, seed=seed, source_sha256=captured['source_sha256'],
                          file_sha256=corpus.file_sha(path), board_sha256=physical, villages=villages)
    inputs = dict(source_commit=commit, source_archive_sha256=corpus.file_sha(archive),
                  corpus_sha256=corpus.file_sha(data_dir/'corpus.json'), audit_sha256=corpus.file_sha(data_dir/'audit.json'),
                  environment=audit['worker'], checkpoint=corpus.BASE['base_bc'], task=corpus.BASE['task_id'],
                  rules_sha256=corpus.BASE['rules_sha256'], maps=maps, order=ORDER,
                  steps=corpus.STEPS, shared_per_step=corpus.SHARED, swapped_per_step=corpus.SWAPPED,
                  learning_rate=.0003, max_grad_norm=.5, marginal_weight=.1, trainer_threads=1, workers=8,
                  limits=LIMITS, bootstrap_seed=2026111559, bootstrap_samples=10000, minimum_gain=.05,
                  exposure=dict(files=exposure_files, board_sha256=sorted(excluded)))
    parent = read_json(PARENT/'manifest.json')
    jobs = schedule(output, board_dir, inputs, dict(zip(ROLES, ROLES)), parent['opponents'][0]['path'],
                    parent['baseline']['path'], 0)
    inputs['slots'] = slots(jobs, rules)
    write_new(output/'inputs.json', inputs)
    print(f"Frozen {len(jobs)} jobs across {len(inputs['slots'])} paired slots", flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('data', type=Path)
    parser.add_argument('commit')
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    freeze(args.output, args.data, args.commit, args.archive)
