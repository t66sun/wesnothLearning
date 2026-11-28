"""Run the single bounded #306 terminal-return comparison on Ubuntu."""
import argparse
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from unittest.mock import patch

import torch

from learning import coordinator, experiment, ppo
from learning.common import ROOT, read_json, sha256
from learning.export import export, load_model
from learning.maps import SPLITS, freeze_map, frozen_map
from learning.sample import collect
from learning.tasks import value_target
from verification.duel_ppo_comparison_20261106.audit import (
    board_digest, initial_audit, shard_boards, write_new,
)
from verification.duel_ppo_comparison_20261106.contract import (
    aliases, crossed_statistics, ledger, production_trainer,
)
from verification.duel_ppo_comparison_20261106.panels import panel_scores, role
from verification.ppo_batch_comparison_20261107 import panels
from verification.ppo_batch_comparison_20261107.driver import bc_endpoint, worker_identity
from verification.ppo_batch_contract_20261107 import driver as paired

PARENT = Path('/home/tongshu/acceptance/duel_comparison_20261106_43325b3/source/runs/'
              'duel_ppo_comparison_20261106/runs/bc')
ASSETS = Path('/home/tongshu/myDev/wesnothLearning/WesnothLearning')
WESNOTH_DATA = ASSETS/'.runtime/install/share/wesnoth/data'
CATALOG = ASSETS/'rules/1.18.8/catalog.json'
RULES = Path(paired.configuration('', 0, 1)['rules_dir'])
BASE = panels.INPUTS['base_bc']
SEEDS = (202611081, 202611082, 202611083)
ORDER = ((1., SEEDS[0]), (.95, SEEDS[0]), (.95, SEEDS[1]), (1., SEEDS[1]),
         (1., SEEDS[2]), (.95, SEEDS[2]))
HOLDOUT = {
    'road_to_weldyn': 'campaigns/Delfadors_Memoirs/maps/03_The_Road_to_Weldyn.map',
    'summer_of_storms': 'campaigns/The_Rise_Of_Wesnoth/maps/01_A_Summer_of_Storms.map',
}
SECONDS = dict(preparation=1800, cell=14400, admission=14100, ppo=86400,
               validation=3600, holdout=12600, report=3600, total=108000)
MIN_FREE = 55 * 1024**3
WORKERS = 8


def cell_name(lam, seed):
    return f'lambda-{lam}-{seed}'


def prepare(output, commit, archive, started):
    identity = initial_audit()
    source = dict(source=str(ROOT), commit=commit, archive=str(archive), archive_sha256=sha256(archive),
                  extension=identity['extension'], extension_sha256=identity['extension_sha256'])
    worker = worker_identity(source)
    endpoint = bc_endpoint(PARENT)['endpoint']
    if any(endpoint[key] != value for key, value in BASE.items()):
        raise ValueError('the #227 qualifying BC identity differs')
    parent = read_json(PARENT/'manifest.json')
    control = parent['opponents'][0]['path']
    if sha256(control) != panels.INPUTS['astra']['teacher_parent_sha256']:
        raise ValueError('the frozen Astra package differs')
    free = shutil.disk_usage(output).free
    if free < MIN_FREE:
        raise RuntimeError(f'PPO disk preflight requires {MIN_FREE} bytes free, found {free}')

    official = {name for names in SPLITS['duel'].values() for name in names}
    maps = {name: dict(board_sha256=board_digest(board), file_sha256=digest)
            for name in sorted(official) for board, digest in [frozen_map(name)]}
    arena = ROOT/'vendor/arena/maps/arena2.json'
    maps['arena2'] = dict(board_sha256=board_digest(read_json(arena)), file_sha256=sha256(arena))
    exposed = {record['board_sha256'] for record in maps.values()}
    exposed.add(panels.INPUTS['holdout']['board_sha256'])
    for audit in (endpoint['exposure'], identity['exposure']):
        exposed.update(digest for boards in audit['boards'].values() for digest in boards)

    terrains = read_json(RULES/'rules.json')['terrains']
    holdout = {}
    for name, filename in HOLDOUT.items():
        path = freeze_map(WESNOTH_DATA/filename, name, output=output/'boards', catalog=CATALOG)
        data = read_json(path)
        board = data['board']
        digest = board_digest(board)
        if digest in exposed or len(board['starts']) != 2:
            raise ValueError(f'{name} repeats an exposed board or lacks two starts')
        if {cell for row in board['terrain'] for cell in row} - terrains.keys():
            raise ValueError(f'{name} has terrain outside the frozen rule catalog')
        if not all(terrains[board['terrain'][y-1][x-1]]['keep'] for x, y in board['starts']):
            raise ValueError(f'{name} does not put both duel seats on keeps')
        exposed.add(digest)
        holdout[name] = dict(path=str(path), source_sha256=data['source_sha256'], board_sha256=digest,
                             file_sha256=sha256(path), width=board['width'], height=board['height'],
                             starts=board['starts'])
        # Exercise the exact ordered roster, rotation and physical board plan without playing games.
        jobs = panels.plan_jobs(output, 'learner', control, parent['baseline']['path'],
                                'preflight', started+SECONDS['total'], str(RULES), 'holdout',
                                data | dict(file_sha256=sha256(path)))
        if len(jobs) != 60 or len({job['scenario_family'] for job in jobs}) != 30:
            raise ValueError(f'{name} does not supply 30 two-seat paired blocks')

    (output/'human-empty').mkdir()
    prepared = time.time()
    if prepared - started > SECONDS['preparation']:
        raise RuntimeError('input preparation exceeded its frozen allocation')
    settings = experiment.default_config('cpu') | paired.configuration(output/'human-empty', 0, 4)
    for key in ('seed', 'gae_lambda', 'hours'):
        del settings[key]
    settings.update(rollout_games=8, branch_reset_optimizer=True)
    write_new(output/'launch.json', dict(source=source, worker=worker, parent=str(PARENT),
              endpoint=endpoint, initializer=identity, astra=dict(path=control, **panels.INPUTS['astra']),
              rules=dict(path=str(RULES), sha256=panels.INPUTS['rules_sha256']),
              training_and_prior_boards=maps, holdout=holdout, config=settings, order=ORDER,
              ppo=dict(learning_rate=1e-4, kl_limit=ppo.KL_LIMIT),
              evaluation=dict(validation_seed=panels.INPUTS['validation_seed'],
                              holdout_seed=panels.INPUTS['holdout_seed'],
                              bootstrap_seed=panels.INPUTS['bootstrap_seed'],
                              bootstrap_samples=panels.INPUTS['bootstrap_samples'],
                              validation_blocks=15, holdout_blocks_per_map=30),
              disk=dict(free_bytes=free, minimum_bytes=MIN_FREE),
              seconds=SECONDS, preparation_started=started, prepared=prepared,
              hard_deadline=started+SECONDS['total']))
    print(f'Prepared {output}/launch.json', flush=True)


class TerminalReturnExperiment(paired.PairedExperiment):
    def finish_train(self, prepared_bc=None, *, prepared_ppo=None):
        budget = read_json(self.directory.parent/'budget.json')
        batch = self.state['batch']
        pending = self.state['pending_train']
        first = batch == budget['first_batch']
        observed = {}
        real_advantages = ppo.advantages

        def trace(rows, **kwargs):
            adv, returns = real_advantages(rows, **kwargs)
            lam = self.config['gae_lambda']
            if {row['reward_config']['gae_lambda'] for row in rows} != {lam}:
                raise ValueError('PPO input lambda differs from its frozen run')
            if not all(row['value_valid'] and not row['truncated'] for row in rows):
                raise ValueError('the first batch did not contain complete task trajectories')
            if lam == 1.:
                for row, advantage, target in zip(rows, adv, returns):
                    expected = value_target(row)
                    if not (math.isclose(target, expected, abs_tol=1e-9) and
                            math.isclose(advantage, expected-row['value'], abs_tol=1e-9)):
                        raise ValueError('the first lambda=1 update missed its complete-return target')
            observed.update(gae_lambda=lam, rows=len(rows), complete_returns_checked=lam == 1.)
            return adv, returns

        if first:
            with patch.object(ppo, 'advantages', trace):
                settled = super().finish_train(prepared_bc, prepared_ppo=prepared_ppo)
        else:
            settled = super().finish_train(prepared_bc, prepared_ppo=prepared_ppo)
        settled_at = time.time()
        if settled and settled_at <= budget['hard_deadline']:
            wall = self.directory/'wall.pt'
            candidate = wall.with_suffix('.next')
            os.link(self.directory/'latest.pt', candidate)
            candidate.replace(wall)
            if first:
                schedule = self.directory/'schedules'/f'ppo-batch-{batch:06}.json'
                jobs = read_json(schedule)
                lam = self.config['gae_lambda']
                if (len(jobs) != 8 or {job['reward_config']['gae_lambda'] for job in jobs} != {lam}
                        or pending['reward_config']['gae_lambda'] != lam or not observed):
                    raise ValueError('first PPO batch missed the frozen eight-game reward contract')
                entry = self.state['history'][-1]
                write_new(self.directory.parent/'first-online.json', dict(
                    observed, games=len(jobs), committed_steps=entry['committed_steps'],
                    kl_stopped=entry.get('kl_stopped', False), settled_at=settled_at,
                    schedule_sha256=sha256(schedule), versions=sorted({j['meta']['version'] for j in jobs})))
        return settled


def trainer_main(*args, **kwargs):
    coordinator.FormatExperiment = TerminalReturnExperiment
    return production_trainer(*args, **kwargs)


def resume_arm(run):
    with patch.object(coordinator, 'trainer_main', trainer_main):
        return coordinator.Experiment(run, resume=True).run()


def train(output, launch, deadline, lam, seed):
    run = output/'cells'/cell_name(lam, seed)
    with patch.object(paired, 'resume_arm', resume_arm), patch.object(
            paired, 'configuration', lambda _, seed, hours: launch['config'] |
            dict(seed=seed, hours=hours, gae_lambda=lam)):
        result = paired.start_arm(run, PARENT, output/'human-empty', launch['endpoint'],
                                  seed=seed, rollout_games=8, admission=deadline-300, deadline=deadline)
    if result['status'] != 'stage_complete':
        raise RuntimeError(f'PPO did not settle normally in {run}')
    return result


def evaluate(output, launch, roles, deadline, partition):
    unique, mapping = aliases(roles)
    output.mkdir()
    parent = read_json(PARENT/'manifest.json')
    control = launch['astra']['path']
    if sha256(control) != launch['astra']['teacher_parent_sha256']:
        raise ValueError('the panel Astra package differs')
    addons = {}
    for key, record in unique.items():
        path = record['path']
        if role(path) != record:
            raise ValueError('checkpoint changed after freezing')
        model, state = load_model(path, 'duel')
        destination = output/'policies'/key
        export({'duel': model}, destination, name='DuelComparison', package=False,
               version=str(record['version']))
        torch.save(dict(model=model.state_dict(), features=state['features'],
                        architecture=state['architecture'], format='duel'), destination/'model.pt')
        addons[key] = str(destination/'DuelComparison')

    maps = launch['holdout'] if partition == 'holdout' else {'hamlets': None}
    reports = {}
    for name, board_info in maps.items():
        folder = output/name
        folder.mkdir()
        board = None
        if board_info:
            path = board_info['path']
            board = read_json(path) | dict(file_sha256=sha256(path))
            if board['file_sha256'] != board_info['file_sha256']:
                raise ValueError('holdout map changed after freezing')
        jobs = [job for key, addon in addons.items() for job in panels.plan_jobs(
            folder, addon, control, parent['baseline']['path'], key, deadline,
            launch['rules']['path'], partition, board)]
        jobs.sort(key=lambda j: (j['meta']['block'], j['meta']['rotation'], j['meta']['weights_sha256']))
        blocks = len(panels.roster(partition))
        plan = dict(partition=partition, blocks=blocks, roles=roles, aliases=mapping, jobs=jobs)
        write_new(folder/'plan.json', plan)
        results = collect(jobs, WORKERS, folder/'results.jsonl')
        scored = panel_scores(plan, results)
        scored.update(planned_games=len(jobs), actual_games=sum(
            row['status'] == 'complete' and not row['result'].get('faults') for row in results))
        write_new(folder/'summary.json', scored)
        reports[name] = scored
    return reports


def compare(reports, launch):
    counts = {name: dict(planned=panel['planned_games'], actual=panel['actual_games'],
                         missing=panel['missing']) for name, panel in reports.items()}
    if not all(panel['complete'] for panel in reports.values()):
        return dict(status='incomplete', games=counts)

    def statistics(panels_for_comparison):
        scores = {name: {scene: score for panel in panels_for_comparison
                         for scene, score in panel['roles'][name].items()}
                  for name in panels_for_comparison[0]['roles']}
        maps = {scene: name for panel in panels_for_comparison
                for scene, name in panel['scenario_maps'].items()}
        return crossed_statistics(
            {seed: scores[cell_name(.95, seed)] for seed in SEEDS},
            {seed: scores[cell_name(1., seed)] for seed in SEEDS},
            scores['bc'], maps, seed=launch['evaluation']['bootstrap_seed'],
            samples=launch['evaluation']['bootstrap_samples'])

    overall = statistics(list(reports.values()))
    return dict(status='observed', overall=overall, games=counts,
                per_map={name: statistics([panel]) for name, panel in reports.items()},
                candidate=(overall['interval95']['b_minus_a'][0] > 0 and
                           overall['interval95']['b_minus_bc'][0] > 0))


def stage(output, request):
    launch = read_json(output/'launch.json')
    action = request['action']
    deadline = request['deadline']
    if time.time() >= deadline:
        raise RuntimeError(f'{action} entered after its frozen deadline')
    if action == 'ppo':
        result = train(output, launch, deadline, request['lambda'], request['seed'])
    elif action in ('validation', 'holdout'):
        roles = read_json(output/'endpoints.json')
        result = evaluate(output/action, launch, roles, deadline, action)
    else:
        holdout = read_json(output/'holdout-result.json')
        result = compare(holdout, launch)
        validation = read_json(output/'validation-result.json')
        result['validation'] = compare(validation, launch)
        if result['validation']['status'] == 'incomplete':
            result.update(status='incomplete', candidate=False)
    write_new(output/f"{request['label']}-result.json", result)


def run_stage(output, label, action, deadline, **options):
    request = output/f'{label}-request.json'
    write_new(request, dict(action=action, label=label, deadline=deadline, **options))
    command = [sys.executable, '-u', '-m', __spec__.name, 'stage', str(output),
               '--request', str(request)]
    started = time.time()
    if started >= deadline:
        raise RuntimeError(f'{label} has no remaining allocation')
    with (output/f'{label}.log').open('x', encoding='utf-8') as stream:
        process = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        write_new(output/f'{label}-process.json', dict(command=command, pid=process.pid, started=started))
        timed_out = False
        try:
            code = process.wait(timeout=max(0, deadline-time.time()))
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            code = process.wait()
    finished = time.time()
    outcome = dict(started=started, deadline=deadline, finished=finished,
                   wall_seconds=finished-started, exit_code=code, timed_out=timed_out)
    write_new(output/f'{label}-exit.json', outcome)
    print(label, outcome, flush=True)
    if code and not (action == 'ppo' and timed_out):
        raise RuntimeError(f'{label} failed with exit {code}')
    return outcome


def settle(output, label, outcome, forbidden):
    root = output/'cells'/label
    wall = root/'duel/wall.pt'
    if not (root/'first-online.json').is_file() or not wall.is_file():
        raise RuntimeError(f'{label} has no accepted online batch and wall checkpoint')
    budget = read_json(root/'budget.json')
    if outcome['finished'] < budget['admission_deadline']:
        raise RuntimeError(f'{label} stopped before its full PPO admission window')
    state = torch.load(wall, map_location='cpu', weights_only=False)['runner']
    stats = ledger(state, budget | dict(fresh_targets=math.inf))
    del stats['budget_complete'], stats['overshoot']
    stats['fresh_per_hour'] = stats['fresh_targets'] * 3600 / outcome['wall_seconds']
    exposure = shard_boards(state)
    if forbidden & {digest for hashes in exposure['boards'].values() for digest in hashes}:
        raise ValueError(f'{label} touched a reserved holdout board')
    record = role(wall)
    latest = read_json(root/'duel/state.json')
    write_new(output/f'{label}-ledger.json', dict(stats, endpoint=record, exposure=exposure,
              pending_at_stop=latest.get('pending_train'), validation_pending=latest.get('pending_validation')))
    stream = []
    for entry in state['history'][budget['history_start']:]:
        jobs = read_json(root/'duel/schedules'/f"ppo-batch-{entry['batch']:06}.json")
        for job in jobs:
            seat = job['meta']['seat']
            stream.append((job['scenario_family'], job['game_family'], job['seed'], job['factions'],
                           seat, job['learning']['sides'][str(seat)]['sampling_seed']))
    return record, stream


def run(output):
    launch = read_json(output/'launch.json')
    worker_identity(launch['source'])
    if tuple(map(tuple, launch['order'])) != ORDER or launch['seconds'] != SECONDS:
        raise ValueError('the frozen order or allocation differs')
    if shutil.disk_usage(output).free < MIN_FREE:
        raise RuntimeError('insufficient disk at formal launch')
    started = time.time()
    total = launch['hard_deadline']
    if started-launch['preparation_started'] > SECONDS['preparation']:
        raise RuntimeError('launch exceeded the frozen preparation ceiling')
    write_new(output/'run-start.json', dict(started=started, pid=os.getpid(), deadline=total))
    roles = {'bc': role(PARENT/'duel/last_bc.pt')}
    if roles['bc']['checkpoint_sha256'] != BASE['checkpoint_sha256']:
        raise ValueError('shared BC changed before formal launch')
    forbidden = {record['board_sha256'] for record in launch['holdout'].values()}
    streams = {}
    bookkeeping = 0.
    for lam, seed in ORDER:
        label = cell_name(lam, seed)
        deadline = time.time() + SECONDS['cell']
        if deadline > total:
            raise RuntimeError('total deadline cannot fund the next full PPO cell')
        outcome = run_stage(output, label, 'ppo', deadline, **{'lambda': lam, 'seed': seed})
        before = time.monotonic()
        roles[label], streams[lam, seed] = settle(output, label, outcome, forbidden)
        bookkeeping += time.monotonic()-before

    before = time.monotonic()
    pairs = {}
    for seed in SEEDS:
        a, b = streams[.95, seed], streams[1., seed]
        paired_count = min(len(a), len(b))
        if a[:paired_count] != b[:paired_count]:
            raise ValueError(f'the realized PPO scenario streams differ for seed {seed}')
        pairs[seed] = dict(paired_games=paired_count, baseline_games=len(a), terminal_return_games=len(b))
    write_new(output/'training-pairs.json', pairs)
    write_new(output/'endpoints.json', roles)
    bookkeeping += time.monotonic()-before
    write_new(output/'settlement-accounting.json', dict(report_seconds=bookkeeping))
    for action in ('validation', 'holdout', 'report'):
        allocation = SECONDS[action] - (bookkeeping if action == 'report' else 0.)
        run_stage(output, action, action, min(total, time.time()+allocation))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run', 'stage'))
    parser.add_argument('output', type=Path)
    parser.add_argument('--commit')
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--started', type=float)
    parser.add_argument('--request', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare':
        args.output.mkdir(parents=True, exist_ok=False)
        prepare(args.output, args.commit, args.archive, args.started)
    elif args.action == 'run':
        run(args.output)
    else:
        stage(args.output, read_json(args.request))


if __name__ == '__main__':
    main()
