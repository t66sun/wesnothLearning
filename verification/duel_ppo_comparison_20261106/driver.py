"""Explicit launch of the reviewed eight-hour duel experiment; no implicit run."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import torch

from learning import coordinator
from learning.bc_anchor import _endpoint, weights_sha256
from learning.common import read_json, sha256
from learning.experiment import bc_effective
from learning.phases import request_phase
from verification.duel_ppo_comparison_20261106.audit import initial_audit, shard_boards, write_new
from verification.duel_ppo_comparison_20261106.contract import HERE, INPUTS, ledger, trainer_main


def configuration(empty_human, seed, hours, mode='historical_action'):
    return dict(formats=['duel'], phase='bc', hours=hours, seed=seed, device='cpu',
                engine='lite', evaluation_engine='lite', workers=INPUTS['workers'],
                trainer_threads=1, rules_dir=INPUTS['rules_dir'], reward_mode='fixed',
                human_data=str(empty_human), ppo_aux_target=mode)


def cell_name(mode, seed):
    return ('a' if mode == 'historical_action' else 'b') + str(INPUTS['seeds'].index(seed)+1)


def stage(args):
    output = Path(args.output)
    if args.stage == 'bc':
        config = configuration(output/'human-empty', INPUTS['bc_seed'], (args.deadline-time.time())/3600)
        config.update(branch_weights_only=True, branch_checkpoint='last_bc')
        run = coordinator.Experiment(output/'runs/bc', config=config, branch_from=INPUTS['parent'])
        result = run.run()
    elif args.stage == 'ppo':
        endpoint = read_json(output/'bc-endpoint.json')
        parent = output/'runs/bc'
        if sha256(parent/'duel/last_bc.pt') != endpoint['checkpoint_sha256']:
            raise ValueError('shared BC endpoint changed')
        root = output/'runs'/cell_name(args.mode, args.seed)
        config = configuration(output/'human-empty', args.seed, (args.deadline-time.time())/3600, args.mode)
        config['branch_reset_optimizer'] = True
        run = coordinator.Experiment(root, config=config, branch_from=parent)
        write_new(root/'budget.json', dict(admission_deadline=args.admission, hard_deadline=args.deadline,
            fresh_targets=INPUTS['fresh_targets'], history_start=endpoint['history_entries']))
        # The inherited qualified BC phase returns without collecting/updating.
        run.run()
        initialized = torch.load(root/'duel/latest.pt', map_location='cpu', weights_only=False)
        if weights_sha256(initialized['model']) != endpoint['weights_sha256'] or initialized['optimizer']['state']:
            raise ValueError('PPO cell did not initialize from common weights and fresh Adam')
        write_new(root/'initialization.json', dict(weights_sha256=endpoint['weights_sha256'],
            checkpoint_sha256=sha256(root/'duel/latest.pt'), optimizer_states=0))
        request_phase(root, 'ppo', hours=(args.deadline-time.time())/3600)
        coordinator.trainer_main = trainer_main
        result = coordinator.Experiment(root, resume=True).run()
    else:
        from verification.duel_ppo_comparison_20261106.panels import execute
        cells = read_json(output/'cells.json')
        result = execute(output/'evaluation', output/'runs/bc', cells, args.deadline)
    print(json.dumps(dict(stage=args.stage, result=result)), flush=True)


def run_stage(output, label, arguments, deadline):
    command = [sys.executable, '-u', str(Path(__file__).resolve()), 'stage',
               '--output', str(output), '--deadline', str(deadline)] + arguments
    started = time.time()
    with (output/(label+'.log')).open('x', encoding='utf-8') as stream:
        process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        write_new(output/(label+'-process.json'), dict(command=command, pid=process.pid, process_group=process.pid,
            started=started, deadline=deadline, source_commit=os.environ['SOURCE_COMMIT']))
        timed_out = False
        try:
            code = process.wait(timeout=max(0, deadline-time.time()))
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                code = process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                code = process.wait()
    outcome = dict(started=started, finished=time.time(), wall_seconds=time.time()-started,
                   exit_code=code, timed_out=timed_out)
    write_new(output/(label+'-exit.json'), outcome)
    print(label, json.dumps(outcome), flush=True)
    return outcome


def summarize_cell(root):
    state = read_json(root/'duel/state.json')
    budget = read_json(root/'budget.json')
    value = ledger(state, budget)
    jobs = [json.loads(line) for line in (root/'duel/jobs.jsonl').read_text().splitlines() if line.strip()]
    policy = {row['id']: row for row in jobs if row.get('meta', {}).get('phase') == 'ppo'}
    value['sampled_eligible_decisions'] = sum((r.get('training_shard') or {}).get('written', 0) for r in policy.values())
    value['unsettled_eligible_decisions'] = value['sampled_eligible_decisions']-value['fresh_targets']
    value['policy_games'] = len(policy)
    value['policy_game_statuses'] = {status: sum(r['status']==status for r in policy.values())
                                    for status in sorted({r['status'] for r in policy.values()})}
    value['physical_exposure'] = shard_boards(state)
    value['history'] = state['history'][budget['history_start']:]
    value['error'] = state.get('error')
    return value


def run(output):
    output = output.resolve()
    if not output.is_relative_to(ROOT):
        raise ValueError('experiment output must stay inside the archived source')
    output.mkdir(parents=True, exist_ok=False)
    started = time.time()
    hard = started + INPUTS['seconds']['total']
    write_new(output/'launch.json', dict(started=started, hard_deadline=hard, pid=os.getpid(),
        command=sys.argv, source_commit=os.environ['SOURCE_COMMIT'],
        protocol_sha256=sha256(HERE/'PROTOCOL.md'), inputs_sha256=sha256(HERE/'inputs.json')))
    write_new(output/'input-audit.json', initial_audit())
    if time.time()-started >= INPUTS['seconds']['preflight']:
        raise RuntimeError('preflight budget exhausted')
    (output/'human-empty').mkdir()
    bc_end = min(hard, time.time()+INPUTS['seconds']['bc'])
    outcome = run_stage(output, 'bc', ['--stage', 'bc'], bc_end)
    bc_root = output/'runs/bc'
    gate_path = bc_root/'duel/bc_gate.json'
    gate = read_json(gate_path) if gate_path.exists() else {}
    if outcome['exit_code'] != 0 or not bc_effective(gate):
        write_new(output/'result.json', dict(status='prerequisite_failed', gate=gate,
            wall_seconds=time.time()-started, stage=outcome))
        return
    bc_path = bc_root/'duel/last_bc.pt'
    loaded = torch.load(bc_path, map_location='cpu', weights_only=False)
    endpoint = _endpoint(loaded, 'duel')
    latest = torch.load(bc_root/'duel/latest.pt', map_location='cpu', weights_only=False)
    if weights_sha256(latest['model']) != endpoint['weights_sha256'] or latest['runner'].get('pending_train'):
        raise ValueError('BC latest does not match the complete qualified endpoint')
    endpoint.update(checkpoint_sha256=sha256(bc_path), gate_sha256=sha256(gate_path),
                    history_entries=len(loaded['runner']['history']), exposure=shard_boards(loaded['runner']))
    write_new(output/'bc-endpoint.json', endpoint)
    del loaded, latest
    cells = []
    for mode, seed in INPUTS['cell_order']:
        now = time.time()
        deadline = min(hard, now+INPUTS['seconds']['cell_hard'])
        name = cell_name(mode, seed)
        outcome = run_stage(output, name, ['--stage', 'ppo', '--mode', mode, '--seed', str(seed),
            '--admission', str(now+INPUTS['seconds']['cell_admission'])], deadline)
        root = output/'runs'/name
        record = dict(name=name, run=str(root), mode=mode, seed=seed, stage=outcome)
        if (root/'duel/state.json').exists() and (root/'budget.json').exists():
            record['ledger'] = summarize_cell(root)
        write_new(output/(name+'-ledger.json'), record)
        cells.append(record)
        if (outcome['exit_code'] != 0 and not outcome['timed_out']) or record.get('ledger', {}).get('error'):
            write_new(output/'result.json', dict(status='infrastructure_error', cells=cells, wall_seconds=time.time()-started))
            return
    write_new(output/'cells.json', cells)
    evaluation_end = min(hard-INPUTS['seconds']['report'], time.time()+INPUTS['seconds']['evaluation'])
    outcome = run_stage(output, 'evaluation', ['--stage', 'evaluate'], evaluation_end)
    from verification.duel_ppo_comparison_20261106.mc import diagnose
    write_new(output/'mc-diagnostics.json', diagnose(cells, deadline=hard))
    panel_path = output/'evaluation/summary.json'
    panels = read_json(panel_path) if panel_path.exists() else None
    budgets = all(cell.get('ledger', {}).get('budget_complete') for cell in cells)
    complete = bool(panels and panels['holdout']['complete'] and outcome['exit_code'] == 0)
    write_new(output/'result.json', dict(status='observed' if budgets and complete else 'incomplete',
        budgets_complete=budgets, panels_complete=complete, cells=cells, evaluation=outcome,
        panels=panels, wall_seconds=time.time()-started, hard_deadline=hard))
    print('EXPERIMENT COMPLETE', str(output/'result.json'), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    launch = commands.add_parser('run')
    launch.add_argument('--output', type=Path, required=True)
    execute = commands.add_parser('stage')
    execute.add_argument('--output', required=True)
    execute.add_argument('--stage', choices=['bc', 'ppo', 'evaluate'], required=True)
    execute.add_argument('--deadline', type=float, required=True)
    execute.add_argument('--admission', type=float)
    execute.add_argument('--mode', choices=['historical_action', 'frozen_bc_kl'])
    execute.add_argument('--seed', type=int)
    args = parser.parse_args()
    if args.command == 'run':
        run(args.output)
    else:
        stage(args)


if __name__ == '__main__':
    torch.set_num_threads(1)
    main()
