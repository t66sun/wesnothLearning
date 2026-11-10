"""Run the six frozen #312 cells with the production paired trainer."""
import argparse
from functools import partial
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from unittest.mock import patch


def load(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def check_arm(plan, arm):
    from learning.common import ROOT
    from learning.maps import SPLITS, frozen_map
    from verification.ppo_batch_comparison_20261107.driver import worker_identity

    record = plan['arms'][arm]
    worker_identity(record)
    maps = {name: frozen_map(name)[1]
            for split in ('train', 'validation') for name in SPLITS['duel'][split]}
    maps['arena2'] = digest(ROOT / 'vendor/arena/maps/arena2.json')
    if maps != record['maps']:
        raise ValueError(f'{arm}: frozen map identities differ')


def cell(stage, plan, arm, seed, admission, deadline):
    from learning.phases import request_phase
    from verification.ppo_batch_contract_20261107 import driver as paired
    from verification.ppo_batch_comparison_20261107.driver import worker_identity

    record = plan['arms'][arm]
    worker_identity(record)
    root = Path(record['source']) / 'runs' / 'ppo312' / str(seed)
    with patch.object(paired, 'configuration', lambda _, seed, hours:
                      plan['config'] | dict(seed=seed, hours=hours)), patch.object(
                      paired, 'request_phase',
                      partial(request_phase, ppo_batches=plan['successful_batches_per_cell'])):
        result = paired.start_arm(root, plan['parent'], stage / 'human-empty', plan['endpoint'],
                                  seed=seed, rollout_games=plan['config']['rollout_games'],
                                  admission=admission, deadline=deadline)
    state = load(root / 'duel/state.json')
    budget = load(root / 'budget.json')
    history = state['history'][budget['history_start']:]
    positive = sum(row['method'] == 'ppo' and row['committed_steps'] > 0 for row in history)
    write(stage / 'cells' / f'{arm}-{seed}-settled.json',
          dict(root=str(root), stage=state['stage'], pending_train=state.get('pending_train'),
               pending_validation=state.get('pending_validation'), positive_batches=positive,
               all_batches=len(history), result=result))
    if (result['status'] != 'stage_complete' or state['stage'] != 'ppo_complete'
            or state.get('pending_train') or state.get('pending_validation')
            or positive != plan['successful_batches_per_cell']):
        raise RuntimeError(f'{arm}-{seed} did not reach the frozen settled-work boundary')


def launch_args(stage, plan, arm, action, *args):
    record = plan['arms'][arm]
    source = Path(record['source'])
    environment = dict(os.environ, PYTHONPATH=f"{source}:{Path(record['extension']).parent}",
                       WESNOTH_RULES_DIR=plan['rules']['path'], PYTHONDONTWRITEBYTECODE='1',
                       PYTHONHASHSEED='0', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
                       OPENBLAS_NUM_THREADS='1')
    command = [sys.executable, '-u', __file__, action, str(stage), arm, *map(str, args)]
    return command, source, environment


def validate(stage, plan, deadline):
    if shutil.disk_usage(stage).free < plan['min_free_bytes']:
        raise RuntimeError('insufficient free space for the frozen comparison')
    parent = Path(plan['parent'])
    originals = [(plan['previous_launch'], plan['previous_launch_sha256']),
                 (parent / 'duel/last_bc.pt', plan['endpoint']['checkpoint_sha256']),
                 (parent / 'duel/bc_gate.json', plan['endpoint']['gate_sha256']),
                 (Path(plan['rules']['path']) / 'rules.json', plan['rules']['sha256']),
                 (plan['astra']['path'], plan['astra']['teacher_parent_sha256'])]
    originals.extend((arm['archive'], arm['archive_sha256']) for arm in plan['arms'].values())
    if any(digest(path) != expected for path, expected in originals):
        raise ValueError('one frozen #312 input changed')
    if any((stage / 'human-empty').iterdir()):
        raise ValueError('the frozen empty human corpus is no longer empty')
    for arm in plan['arms']:
        command, source, environment = launch_args(stage, plan, arm, 'check')
        subprocess.run(command, cwd=source, env=environment, check=True,
                       timeout=max(0, deadline - time.time()))


def run_cell(stage, plan, arm, seed, latest):
    label = f'{arm}-{seed}'
    started = time.time()
    clock = time.monotonic()
    budget = plan['budget_seconds']
    deadline = min(started + budget['cell_hard'], latest)
    admission = min(started + budget['cell_admission'],
                    deadline - (budget['cell_hard'] - budget['cell_admission']))
    if admission <= started:
        raise RuntimeError('remaining training budget cannot admit a cell')
    command, source, environment = launch_args(stage, plan, arm, 'cell', seed, admission, deadline)
    records = stage / 'cells'
    with (records / f'{label}.log').open('x') as log:
        process = subprocess.Popen(command, cwd=source, env=environment, stdout=log,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        write(records / f'{label}-process.json', dict(started=started, admission=admission,
              deadline=deadline, pid=process.pid, command=command, source=str(source)))
        print('CELL START', label, process.pid, flush=True)
        timed_out = False
        try:
            status = process.wait(timeout=max(0, deadline - time.time()))
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            status = process.wait()
    result = dict(arm=arm, seed=seed, started=started, admission=admission, deadline=deadline,
                  finished=time.time(), wall_seconds=time.monotonic() - clock,
                  exit_code=status, timed_out=timed_out)
    write(records / f'{label}-exit.json', result)
    print('CELL EXIT', json.dumps(result), flush=True)
    if status or timed_out:
        raise RuntimeError(f'{label} failed, see its recorded exit and log')


def run(stage, expected):
    plan_path = stage / 'launch.json'
    if digest(plan_path) != expected:
        raise ValueError('frozen launch identity differs')
    plan = load(plan_path)
    started = time.time()
    end = started + plan['budget_seconds']['total']
    latest = end - plan['budget_seconds']['report']
    write(stage / 'run-start.json', dict(started=started, deadline=end, training_deadline=latest,
                                         pid=os.getpid(), launch_sha256=expected,
                                         runner_sha256=digest(__file__)))
    status = 'failed'
    try:
        validate(stage, plan, latest)
        (stage / 'cells').mkdir()
        for seed, arm in plan['order']:
            run_cell(stage, plan, arm, seed, latest)
        status = 'complete'
    finally:
        write(stage / 'run-exit.json', dict(status=status, finished=time.time(), deadline=end))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('run', 'check', 'cell'))
    parser.add_argument('stage', type=Path)
    parser.add_argument('arguments', nargs='+')
    args = parser.parse_args()
    if args.action == 'run':
        expected, = args.arguments
        return run(args.stage, expected)
    plan = load(args.stage / 'launch.json')
    if args.action == 'check':
        arm, = args.arguments
        return check_arm(plan, arm)
    arm, seed, admission, deadline = args.arguments
    return cell(args.stage, plan, arm, int(seed), float(admission), float(deadline))


if __name__ == '__main__':
    main()
