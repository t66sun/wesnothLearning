"""Run and audit the single frozen #322 Lite duel comparison."""
import argparse
import json
from collections import Counter, defaultdict
import math
from pathlib import Path
import shutil
import tarfile
from statistics import mean
import time
from unittest.mock import patch

import torch

from learning import experiment
from learning.common import ROOT, read_json, sha256
from learning.export import export, load_model
from learning.sample import collect
from verification.duel_ppo_comparison_20261106.audit import board_digest, write_new
from verification.duel_ppo_comparison_20261106.contract import crossed_statistics, ledger
from verification.duel_ppo_comparison_20261106.panels import panel_scores, role
from verification.ppo_batch_comparison_20261107 import panels
from verification.ppo_batch_comparison_20261107.driver import bc_endpoint, worker_identity
from verification.ppo_batch_contract_20261107 import driver as paired
from verification.ppo_terminal_return_20261108 import driver as prior

from .opponents import INPUTS, PROTOCOL, export_opponent, resume, verify_opponent

LIMITS = INPUTS['seconds']
EVAL = INPUTS['evaluation']


def prepare(output, commit, archive):
    output.mkdir(parents=True)
    import _engine_lite
    source = dict(source=str(ROOT), commit=commit, archive=str(archive),
                  archive_sha256=sha256(archive), extension=str(Path(_engine_lite.__file__).resolve()),
                  extension_sha256='56dd77140411db987377d6de4ffbf562da4d0e5c76bc16d34780da67e60e5ae4')
    worker_identity(source)
    endpoint = bc_endpoint(prior.PARENT)['endpoint']
    if any(endpoint[key] != value for key, value in panels.INPUTS['base_bc'].items()):
        raise ValueError('qualified BC endpoint differs')
    parent = read_json(prior.PARENT/'manifest.json')
    astra = parent['opponents'][0]['path']
    (output/'human-empty').mkdir()
    config = experiment.default_config('cpu') | paired.configuration(output/'human-empty', 0, 1.5)
    for key in ('seed', 'hours'):
        del config[key]
    config.update(rollout_games=INPUTS['batch_games'], gae_lambda=INPUTS['gae_lambda'])
    opponent = export_opponent(prior.PARENT/'duel/last_bc.pt', output/'opponent')
    launch = dict(source=source, protocol_sha256=sha256(PROTOCOL/'inputs.json'), plan=INPUTS,
                  config=config, endpoint=endpoint, bc=opponent, astra=astra,
                  rules_sha256=sha256(prior.RULES/'rules.json'))
    verify_launch(output, launch)
    write_new(output/'launch.json', launch)
    print('launch_sha256', sha256(output/'launch.json'), flush=True)


def verify_launch(output, launch):
    worker_identity(launch['source'])
    if (launch['plan'] != INPUTS or sha256(PROTOCOL/'inputs.json') != launch['protocol_sha256']
            or sha256(launch['source']['archive']) != launch['source']['archive_sha256']
            or sha256(launch['astra']) != panels.INPUTS['astra']['teacher_parent_sha256']
            or sha256(prior.RULES/'rules.json') != panels.INPUTS['rules_sha256']
            or launch['rules_sha256'] != panels.INPUTS['rules_sha256']):
        raise ValueError('frozen launch inputs differ')
    if any((output/'human-empty').iterdir()):
        raise ValueError('frozen empty human corpus changed')
    verify_opponent(launch['bc'])
    if any(sha256(PROTOCOL/'boards'/(name+'.json')) != info['file_sha256']
           for name, info in INPUTS['holdout'].items()):
        raise ValueError('one of the frozen maps differs')
    if shutil.disk_usage(output).free < INPUTS['min_free_bytes']:
        raise ValueError('insufficient space for the frozen run')


def train(output, launch, label, arm, seed, deadline):
    root = output/'cells'/label
    def resume_cell(run):
        astra = read_json(run/'manifest.json')['opponents'][0]['path']
        write_new(run/'opponents.json', dict(arm=arm, astra=astra, bc=launch['bc']))
        return resume(run)

    with patch.object(paired, 'resume_arm', resume_cell), patch.object(
            paired, 'configuration', lambda _, seed, hours: launch['config'] |
            dict(seed=seed, hours=hours)):
        result = paired.start_arm(root, prior.PARENT, output/'human-empty', launch['endpoint'],
                                  seed=seed, rollout_games=INPUTS['batch_games'],
                                  admission=deadline-(LIMITS['cell']-LIMITS['admission']),
                                  deadline=deadline)
    if result['status'] != 'stage_complete':
        raise RuntimeError(f'{label} did not finish at its PPO boundary')
    return result


def evaluate(output, launch, roles, deadline, partition):
    output.mkdir()
    parent = read_json(prior.PARENT/'manifest.json')
    policies = {}
    for name, record in roles.items():
        checkpoint = record['path']
        if role(checkpoint) != record:
            raise ValueError(f'{name} checkpoint identity differs')
        model, _ = load_model(checkpoint, 'duel')
        destination = output/'policies'/name
        policies[name] = str(export(model, destination, name='DuelComparison',
                                    package=False, version=str(record['version'])))
        shutil.copyfile(checkpoint, destination/'model.pt')
    maps = INPUTS['holdout'] if partition == 'holdout' else {'hamlets': None}
    for name, identity in maps.items():
        folder = output/name
        folder.mkdir()
        board = (read_json(PROTOCOL/'boards'/(name+'.json')) |
                 dict(file_sha256=identity['file_sha256'])) if identity else None
        jobs = [job for key, addon in policies.items() for job in panels.plan_jobs(
            folder, addon, launch['astra'], parent['baseline']['path'], key, deadline,
            str(prior.RULES), partition, board)]
        jobs.sort(key=lambda j: (j['meta']['block'], j['meta']['rotation'], j['meta']['weights_sha256']))
        blocks = EVAL['holdout_blocks_per_map' if identity else 'validation_blocks']
        write_new(folder/'plan.json', dict(partition=partition, blocks=blocks, roles=roles,
                                          aliases={name: name for name in roles}, jobs=jobs))
        results = collect(jobs, 8, folder/'results.jsonl')
        plan = read_json(folder/'plan.json')
        scored = panel_scores(plan, results)
        scored.update(planned_games=len(jobs), actual_games=sum(
            row['status'] == 'complete' and not row['result'].get('faults') for row in results))
        write_new(folder/'summary.json', scored)
        if scored['actual_games'] != blocks * len(roles) * 2 or not scored['complete']:
            raise RuntimeError(f'{name} panel is incomplete')


def read_lines(path):
    with path.open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def settled(output, label, result, arm):
    root = output/'cells'/label
    budget = read_json(root/'budget.json')
    wall = root/'duel/wall.pt'
    checkpoint = torch.load(wall, map_location='cpu', weights_only=False)
    state = checkpoint['runner']
    if state['pending_train'] or result['finished'] < budget['admission_deadline']:
        raise ValueError(f'{label} has an incomplete endpoint or admission window')
    stats = ledger(state, budget | dict(fresh_targets=math.inf))
    del stats['budget_complete'], stats['overshoot']
    endpoint = role(wall)
    contract = read_json(root/'opponents.json')
    initialization = read_json(root/'initialization.json')
    if (initialization['weights_sha256'] != panels.INPUTS['base_bc']['weights_sha256']
            or initialization['optimizer_states'] != 0 or contract['arm'] != arm):
        raise ValueError(f'{label} initialization or arm differs')
    verify_opponent(contract['bc'])
    actual = read_lines(root/'duel/jobs.jsonl')
    replies = {row['id']: row for row in actual}
    if len(replies) != len(actual):
        raise ValueError(f'{label} contains duplicate game replies')
    stream, opponents, decisions = [], Counter(), Counter()
    forbidden = {record['board_sha256'] for record in INPUTS['holdout'].values()}
    history = state['history'][budget['history_start']:]
    for index, entry in enumerate(history):
        jobs = read_json(root/'duel/schedules'/f"ppo-batch-{entry['batch']:06}.json")
        if not jobs or len(jobs) != 8:
            raise ValueError(f'{label} did not settle eight jobs')
        counts, mixed_seats = Counter(), set()
        slots = INPUTS['bc_slots'][index % len(INPUTS['bc_slots'])]
        for ordinal, job in enumerate(jobs):
            active = job['meta']['seat']
            other = job['meta']['experimental_opponent']
            is_bc = other['kind'] == 'frozen_bc'
            learned = job['learning']['sides']
            recorded = replies[job['id']]
            if (is_bc != (arm == 'mixed' and ordinal in slots)
                    or other['sha256'] != (contract['bc']['weights_sha256'] if is_bc
                                           else panels.INPUTS['astra']['teacher_parent_sha256'])
                    or other['side'] != 3-active or other['ordinal'] != len(stream)
                    or job['bots'][other['side']-1] != (contract['bc']['path'] if is_bc else contract['astra'])
                    or set(learned) != {str(active)} or job['learning']['dagger_teacher'] != contract['astra']
                    or recorded['status'] != 'complete' or recorded['result']['bots'] != job['bots']
                    or recorded['result'].get('faults') or board_digest(job['map_override']) in forbidden):
                raise ValueError(f'{label} causal identity differs at {job["id"]}')
            if is_bc:
                mixed_seats.add(active)
            written = recorded['training_shard']['written']
            if written < 1 or not recorded['training_eligible']:
                raise ValueError(f'{job["id"]} has no eligible learner decisions')
            decisions[other['kind']] += written
            counts[other['kind']] += 1
            stream.append([job['scenario_family'], job['game_family'], job['seed'],
                           job['factions'], active, learned[str(active)]['sampling_seed']])
        if counts != (dict(astra=6, frozen_bc=2) if arm == 'mixed' else dict(astra=8)):
            raise ValueError(f'{label} opponent quota differs')
        if arm == 'mixed' and mixed_seats != {1, 2}:
            raise ValueError(f'{label} opponent seat rotation differs')
        opponents.update(counts)
    interruptions = sum(row['status'] == 'budget_interrupted' for row in replies.values()
                        if row['id'].startswith('rollout-'))
    write_new(output/f'{label}-ledger.json', dict(stats, endpoint=endpoint,
              opponents=opponents, learner_decisions=decisions,
              interruptions=interruptions, stream=stream))
    return endpoint, stream


def compare(panels_for_comparison):
    scores = {name: {scene: score for panel in panels_for_comparison
                     for scene, score in panel['roles'][name].items()}
              for name in panels_for_comparison[0]['roles']}
    maps = {scene: name for panel in panels_for_comparison
            for scene, name in panel['scenario_maps'].items()}
    stats = crossed_statistics({seed: scores[f'astra-{seed}'] for seed in INPUTS['seeds']},
                               {seed: scores[f'mixed-{seed}'] for seed in INPUTS['seeds']},
                               scores['bc'], maps, seed=EVAL['bootstrap_seed'],
                               samples=EVAL['bootstrap_samples'])
    map_names = set(maps.values())
    stats['score_means'] = {role: mean(mean(score for scene, score in rows.items() if maps[scene] == name)
                                      for name in map_names) for role, rows in scores.items()}
    difference, interval = stats['differences'], stats['interval95']
    stats['pass'] = (difference['b_minus_a'] >= EVAL['minimum_vs_astra']
                     and difference['b_minus_bc'] >= EVAL['minimum_vs_bc']
                     and interval['b_minus_a'][0] > 0 and interval['b_minus_bc'][0] > 0)
    return stats


def audit_panel(folder, plan, board, control):
    jobs = plan['jobs']
    replies = read_lines(folder/'results.jsonl')
    rows = {row['id']: row for row in replies}
    if len(rows) != len(replies) or set(rows) != {job['id'] for job in jobs}:
        raise ValueError('panel replies do not match planned jobs')
    by_role, design, names = defaultdict(lambda: defaultdict(dict)), defaultdict(set), {}
    for job in jobs:
        row = rows[job['id']]
        result, meta = row['result'], job['meta']
        seat, = meta['policy_sides']
        key, scene, rotation = meta['weights_sha256'], job['scenario_family'], meta['rotation']
        if (row['status'] != 'complete' or result.get('faults') or not result['task_terminal']
                or result['bots'] != job['bots'] or job['bots'][2-seat] != control
                or row['meta']['weights_sha256'] != key or key not in plan['roles']
                or meta['map_sha256'] != board['file_sha256']
                or board_digest(job['map_override']) != board['board_sha256']
                or rotation in by_role[key][scene] or result['winner'] not in (0, 1, 2)):
            raise ValueError(f'panel game differs at {job["id"]}')
        points = 1 if result['winner'] == 0 else 3 if result['winner'] == seat else 0
        by_role[key][scene][rotation] = (seat, points/3)
        design[key].add((scene, rotation, seat, job['seed'], tuple(job['factions'])))
        names[scene] = meta['map']
    first = next(iter(design.values()))
    blocks = plan['blocks']
    if (set(design) != set(plan['roles']) or len(first) != blocks*2
            or any(value != first for value in design.values())):
        raise ValueError('panel roles have different paired scenarios')
    if plan['partition'] == 'holdout' and {item[4] for item in first} != {
            tuple(row['factions']) for row in panels.roster('holdout')}:
        raise ValueError('holdout faction roster differs')
    scores = {}
    for role_name, scenes in by_role.items():
        scores[role_name] = {}
        for scene, pair in scenes.items():
            if set(pair) != {0, 1} or {side for side, _ in pair.values()} != {1, 2}:
                raise ValueError('panel roles lack both learner seat rotations')
            scores[role_name][scene] = mean(score for _, score in pair.values())
    result = dict(roles=scores, scenario_maps=names, planned_games=len(jobs),
                  actual_games=len(replies), complete=True, missing=[])
    if result != read_json(folder/'summary.json'):
        raise ValueError('independent panel scores differ from recorded summary')
    return result


def audit(output):
    roles = read_json(output/'endpoints.json')
    checks = {}
    control = read_json(output/'launch.json')['astra']
    for partition, maps in (('holdout', INPUTS['holdout']),
                            ('validation', {'hamlets': None})):
        checks[partition] = {}
        for name, frozen in maps.items():
            if frozen:
                board = frozen
            else:
                from learning.maps import frozen_map
                hamlets, file_sha = frozen_map('hamlets')
                board = dict(file_sha256=file_sha, board_sha256=board_digest(hamlets))
            folder = output/partition/name
            plan = read_json(folder/'plan.json')
            blocks = EVAL['holdout_blocks_per_map' if frozen else 'validation_blocks']
            if len(plan['jobs']) != len(roles)*blocks*2:
                raise ValueError(f'{name} job count differs')
            if plan['roles'] != roles or plan['blocks'] != blocks:
                raise ValueError(f'{name} panel roles or blocks differ')
            checks[partition][name] = audit_panel(folder, plan, board, control)
    holdout = checks['holdout']
    costs = {f'{arm}-{seed}': read_json(output/f'{arm}-{seed}-exit.json')
             for arm, seed in INPUTS['order']}
    ppo = sum(record['wall_seconds'] for record in costs.values())
    if ppo > LIMITS['ppo'] or any(record['exit_code'] or record['timed_out']
                                  for record in costs.values()):
        raise ValueError('PPO wall budget or process exit differs')
    return dict(ppo_seconds=ppo, cells=costs, overall=compare(list(holdout.values())),
                per_map={name: compare([panel]) for name, panel in holdout.items()},
                validation=compare(list(checks['validation'].values())))


def stage(output, request):
    launch = read_json(output/'launch.json')
    action, deadline = request['action'], request['deadline']
    if time.time() >= deadline:
        raise RuntimeError(f'{action} entered after its allocation')
    if action == 'ppo':
        result = train(output, launch, request['label'], request['arm'], request['seed'], deadline)
    elif action in ('holdout', 'validation'):
        evaluate(output/action, launch, read_json(output/'endpoints.json'), deadline, action)
        result = dict(complete=True)
    else:
        result = audit(output)
    write_new(output/f"{request['label']}-result.json", result)


def archive_metadata(output):
    path = output/'raw-metadata.tar.gz'
    with tarfile.open(path, 'x:gz', compresslevel=1) as bundle:
        for entry in sorted(output.rglob('*')):
            if entry.is_file() and entry.suffix in ('.json', '.jsonl', '.log'):
                bundle.add(entry, arcname=entry.relative_to(output), recursive=False)
    write_new(output/'archive.json', dict(path=str(path), sha256=sha256(path),
                                          bytes=path.stat().st_size))


def run(output, expected):
    launch_path = output/'launch.json'
    if sha256(launch_path) != expected:
        raise ValueError('launch manifest SHA-256 differs')
    started = time.time()
    deadline = started + LIMITS['total']
    write_new(output/'run-start.json', dict(started=started, deadline=deadline, launch_sha256=expected))
    status = 'incomplete'
    try:
        launch = read_json(launch_path)
        verify_launch(output, launch)
        if time.time() - started > LIMITS['prepare']:
            raise ValueError('launch verification exceeded its allocation')
        roles = {'bc': role(prior.PARENT/'duel/last_bc.pt')}
        streams, durations = {}, []
        for arm, seed in INPUTS['order']:
            label = f'{arm}-{seed}'
            cell_deadline = time.time() + LIMITS['cell']
            if cell_deadline > deadline:
                raise ValueError('total budget cannot fund the next full cell')
            outcome = run_stage(output, label, 'ppo', cell_deadline, arm=arm, seed=seed)
            durations.append(outcome['wall_seconds'])
            if outcome['exit_code'] or outcome['timed_out']:
                raise RuntimeError(f'{label} exceeded its process deadline or failed')
            roles[label], streams[label] = settled(output, label, outcome, arm)
        pairs = {}
        for seed in INPUTS['seeds']:
            a, b = streams[f'astra-{seed}'], streams[f'mixed-{seed}']
            length = min(len(a), len(b))
            if not length or a[:length] != b[:length]:
                raise ValueError(f'{seed} training stream does not match')
            pairs[seed] = dict(astra_games=len(a), mixed_games=len(b), common_games=length)
        write_new(output/'training-pairs.json', pairs)
        write_new(output/'endpoints.json', roles)
        for action in ('validation', 'holdout', 'audit'):
            run_stage(output, action, action, min(deadline, time.time()+LIMITS[action]))
        archive_metadata(output)
        if sum(durations) > LIMITS['ppo'] or time.time() > deadline:
            raise ValueError('frozen wall budget exceeded')
        status = 'complete'
    finally:
        write_new(output/'run-exit.json', dict(status=status, started=started,
                  finished=time.time(), deadline=deadline))


def run_stage(output, *args, **kwargs):
    # Reuse the stage subprocess recorder with this module as its child entry point.
    with patch.object(prior, '__spec__', __spec__):
        return prior.run_stage(output, *args, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run', 'stage'))
    parser.add_argument('output', type=Path)
    parser.add_argument('--commit')
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--launch-sha256')
    parser.add_argument('--request', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.output, args.commit, args.archive)
    elif args.action == 'run':
        run(args.output, args.launch_sha256)
    else:
        stage(args.output, read_json(args.request))


if __name__ == '__main__':
    main()
