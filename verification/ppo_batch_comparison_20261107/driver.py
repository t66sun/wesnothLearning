"""Run the frozen PPO comparison only after its shared launch is authorized."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import torch

from learning import coordinator
from learning.bc_anchor import _endpoint, weights_sha256
from learning.common import ROOT, read_json, sha256
from learning.experiment import bc_effective
from learning.maps import freeze_map
from learning.teachers import lineage
from verification.duel_ppo_comparison_20261106.audit import board_digest, shard_boards, write_new
from verification.duel_ppo_comparison_20261106.driver import configuration
from verification.duel_ppo_comparison_20261106.mc import diagnose

from . import arm, panels

HERE = Path(__file__).resolve().parent
EVIDENCE_ROOT = HERE.parents[1]
INPUTS = arm.INPUTS
CONTRACTS = ('base', 'b', 'c')


def cell_contract(route):
    return 'base' if route == 'a' else route


def bc_endpoint(parent):
    gate_path = parent/'duel/bc_gate.json'
    gate = read_json(gate_path)
    if not bc_effective(gate):
        raise ValueError(f'BC gates did not qualify {parent}')
    path = parent/'duel/last_bc.pt'
    checkpoint = torch.load(path, map_location='cpu', weights_only=False)
    endpoint = _endpoint(checkpoint, 'duel')
    latest = torch.load(parent/'duel/latest.pt', map_location='cpu', weights_only=False)
    manifest_path = parent/'manifest.json'
    manifest = read_json(manifest_path)
    if (latest['runner'].get('pending_train') or
            weights_sha256(latest['model']) != endpoint['weights_sha256'] or
            sha256(manifest_path) != endpoint['manifest_sha256'] or
            endpoint['task_id'] != INPUTS['task_id'] or manifest['teacher'] != INPUTS['astra'] or
            manifest['rules']['rules_sha256'] != INPUTS['rules_sha256']):
        raise ValueError(f'BC endpoint identity does not match {parent}')
    config = manifest['config']
    if config['seed'] != INPUTS['bc_seed'] or config['bc_games']['duel'] != INPUTS['bc_games']:
        raise ValueError(f'BC work or teacher seed differs in {parent}')
    exposure = shard_boards(checkpoint['runner'])
    if INPUTS['holdout']['board_sha256'] in {digest for values in exposure['boards'].values() for digest in values}:
        raise ValueError('BC exposure overlaps Silverhead')
    endpoint.update(checkpoint_sha256=sha256(path), gate_sha256=sha256(gate_path), exposure=exposure)
    return dict(endpoint=endpoint, gate=gate)


def bc_gate(parent):
    path = parent/'duel/bc_gate.json'
    return read_json(path) if path.exists() else None


def worker_identity(contract):
    import _engine_lite
    if ROOT.resolve() != Path(contract['source']).resolve():
        raise ValueError('worker imported production from another source root')
    extension = Path(_engine_lite.__file__).resolve()
    teacher = lineage()
    if (extension != Path(contract['extension']).resolve() or
            sha256(extension) != contract['extension_sha256'] or teacher != INPUTS['astra']):
        raise ValueError('worker extension or frozen Astra lineage differs')
    return dict(source=str(ROOT), commit=contract['commit'], extension=str(extension),
                extension_sha256=contract['extension_sha256'], teacher=teacher)


def stage(request):
    started = time.time()
    contract = request['contract']
    identity = worker_identity(contract)
    name = request['stage']
    deadline = request['deadline']
    if started >= deadline:
        raise RuntimeError('stage reached its deadline before starting')
    output = Path(request['output'])
    if name == 'preflight':
        result = identity
        if 'parent' in request:
            record = bc_endpoint(Path(request['parent']))
            if any(record['endpoint'][key] != value for key, value in INPUTS['base_bc'].items()):
                raise ValueError('the accepted #227 BC endpoint differs')
            result['bc'] = record
    elif name == 'bc':
        initializer = Path(request['initializer'])
        if sha256(initializer/'duel/last_bc.pt') != request['initializer_sha256']:
            raise ValueError('BC actor initializer differs from its frozen identity')
        config = configuration(request['empty_human'], INPUTS['bc_seed'], (deadline-time.time())/3600)
        config.update(branch_weights_only=True, branch_checkpoint='last_bc')
        root = Path(request['parent'])
        summary = coordinator.Experiment(root, config=config, branch_from=initializer).run()
        report = summary['formats']['duel']
        if (summary['status'] != 'stage_complete' or report['status'] != 'stage_complete' or
                report['phase'] != 'bc' or report.get('error')):
            raise StageFailed(f'BC trainer failed in {root}')
        if report['pretraining_complete'] is True:
            result = dict(status='qualified', summary=summary, **bc_endpoint(root))
        else:
            gate = bc_gate(root)
            if report['pretraining_complete'] is not False or bc_effective(gate or {}):
                raise StageFailed(f'inconsistent BC qualification evidence in {root}')
            result = dict(status='unqualified', reason='gate_not_qualified', gate=gate, summary=summary)
    elif name == 'ppo':
        arm.start_arm(Path(request['run']), Path(request['parent']), request['empty_human'],
                      request['endpoint'], seed=request['seed'], rollout_games=request['rollout_games'],
                      admission=request['admission'], deadline=deadline)
        return
    elif name == 'validation':
        roles = request['roles']
        for cell in request['cells']:
            selected = panels.select_checkpoint(cell, deadline)
            roles[cell['name']+'/selected'] = selected
            request['full'].append(cell['name']+'/selected')
        panels.execute(output, request, deadline)
        return
    elif name == 'holdout':
        panels.execute(output, request, deadline)
        return
    else:
        result = diagnose(request['cells'], deadline=deadline)
    write_new(output, dict(result=result, wall_seconds=time.time()-started))


def run_stage(output, label, contract, stage_name, deadline, **options):
    """The #227 owned-process deadline, with an explicit source and extension."""
    request = output/f'{label}-request.json'
    result = output/f'{label}-result'
    write_new(request, dict(options, stage=stage_name, contract=contract, output=str(result), deadline=deadline))
    source = Path(contract['source'])
    command = [sys.executable, '-u', '-m', 'verification.ppo_batch_comparison_20261107.driver',
               'stage', '--request', str(request)]
    env = dict(os.environ, SOURCE_COMMIT=contract['commit'],
               PYTHONPATH=os.pathsep.join((str(source), str(Path(contract['extension']).parent), str(EVIDENCE_ROOT))),
               WESNOTH_RULES_DIR=configuration('', 0, 1)['rules_dir'],
               PYTHONDONTWRITEBYTECODE='1', PYTHONHASHSEED='0',
               OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1')
    started = time.time()
    timed_out = False
    if started >= deadline:
        raise StageFailed(f'{label} has no time in its frozen allocation')
    with (output/f'{label}.log').open('x', encoding='utf-8') as stream:
        process = subprocess.Popen(command, cwd=source, env=env, stdout=stream,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        write_new(output/f'{label}-process.json', dict(command=command, pid=process.pid,
                  process_group=process.pid, started=started, deadline=deadline, source_commit=contract['commit']))
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
    finished = time.time()
    outcome = dict(started=started, finished=finished, wall_seconds=finished-started,
                   exit_code=code, timed_out=timed_out)
    write_new(output/f'{label}-exit.json', outcome)
    print(label, json.dumps(outcome), flush=True)
    bc_deadline = stage_name == 'bc' and timed_out and code in (-signal.SIGTERM, -signal.SIGKILL)
    if code and not (bc_deadline or (stage_name == 'ppo' and timed_out)):
        raise StageFailed(f'{label} failed; see {label}.log')
    return result, outcome


class StageFailed(RuntimeError):
    pass


def freeze_board(output, launch):
    expected = INPUTS['holdout']
    native = Path(launch['holdout_map'])
    if native.name != expected['file'] or sha256(native) != expected['source_sha256']:
        raise ValueError('Silverhead native asset changed')
    path = freeze_map(native, expected['name'], output=output, catalog=launch['map_catalog'])
    data = read_json(path)
    board = data['board']
    rules = read_json(Path(launch['rules_dir'])/'rules.json')
    if (board_digest(board) != expected['board_sha256'] or
            {tile for row in board['terrain'] for tile in row} - rules['terrains'].keys()):
        raise ValueError('Silverhead board identity or terrain coverage differs')
    return dict(data, file_sha256=sha256(path))


def check_launch(launch):
    seconds = launch['seconds']
    contracts = launch['contracts']
    if set(contracts) != set(CONTRACTS) or contracts['base']['commit'] != INPUTS['base_source']:
        raise ValueError('launch requires the exact baseline and separate B-only/C-only contracts')
    if len({contract['commit'] for contract in contracts.values()}) != len(CONTRACTS):
        raise ValueError('the three execution contracts require distinct committed sources')
    stage_keys = ('preflight', 'validation', 'holdout', 'report', 'native')
    if any(type(seconds[key]) is not int or seconds[key] < (0 if key == 'native' else 1)
           for key in stage_keys):
        raise ValueError('freeze positive integer stage ceilings in seconds')
    stage_seconds = sum(seconds[key] for key in stage_keys)
    fixed = INPUTS['seconds']
    training = 2*fixed['bc_per_contract'] + len(INPUTS['cell_order'])*fixed['ppo_hard']
    if seconds['total'] != stage_seconds+training:
        raise ValueError('total budget must include both BC, all PPO and reserved evaluation time')
    if sha256(Path(launch['rules_dir'])/'rules.json') != INPUTS['rules_sha256']:
        raise ValueError('frozen rule catalog changed')
    if Path(launch['rules_dir']).resolve() != Path(configuration('', 0, 1)['rules_dir']).resolve():
        raise ValueError('the #271 arm binds the original #227 rules directory')
    if (EVIDENCE_ROOT.parent/'SOURCE_COMMIT').read_text().strip() != launch['evidence_commit']:
        raise ValueError('evidence driver source differs from the frozen launch')
    for contract in contracts.values():
        if sha256(contract['archive']) != contract['archive_sha256']:
            raise ValueError(f"source archive hash differs for {contract['commit']}")
        if Path(contract['source']).parent.joinpath('SOURCE_COMMIT').read_text().strip() != contract['commit']:
            raise ValueError('extraction source identity differs')


def qualification(output, launch, run_name, deadline, empty_human):
    records = {}
    for contract_name in ('b', 'c'):
        contract = launch['contracts'][contract_name]
        parent = Path(contract['source'])/'runs'/run_name/'bc'
        result, outcome = run_stage(output, f'bc-{contract_name}', contract, 'bc',
                                    min(deadline, time.time()+INPUTS['seconds']['bc_per_contract']),
                                    parent=str(parent), initializer=launch['actor_initializer'],
                                    initializer_sha256=INPUTS['actor_initializer_sha256'],
                                    empty_human=str(empty_human))
        if outcome['timed_out']:
            summary_path = parent/'summary.json'
            summary = read_json(summary_path) if summary_path.exists() else None
            if (parent/'duel/trainer_error.log').exists() or (summary and summary['status'] != 'stage_complete'):
                raise StageFailed(f'BC trainer failed before the deadline in {parent}')
            record = dict(status='unqualified', reason='deadline', gate=bc_gate(parent), summary=summary)
        else:
            record = read_json(result)['result']
            if record['status'] not in ('qualified', 'unqualified'):
                raise StageFailed(f'unexpected BC qualification outcome in {parent}')
        records[contract_name] = dict(record, parent=str(parent), stage=outcome)
        write_new(output/f'bc-{contract_name}-qualification.json', records[contract_name])
    return records


def check_first_online(base, large):
    def jobs(cell, batches):
        run = Path(cell['run'])/'duel/schedules'
        return [job for row in cell['ledger']['history'][:batches]
                for job in read_json(run/f"ppo-batch-{row['batch']:06}.json")]

    def physical(job):
        meta = job['meta']
        return (job['training_scenario']['index'], job['scenario_family'], job['game_family'],
                job['seed'], meta['seat'], job['factions'], job['learning']['sides'][str(meta['seat'])]['sampling_seed'])

    first_eight, paired_four = jobs(large, 1), jobs(base, 2)
    if (len(first_eight) != 8 or len(paired_four) != 8 or
            len({job['meta']['version'] for job in first_eight}) != 1 or
            list(map(physical, first_eight)) != list(map(physical, paired_four))):
        raise StageFailed(f"first real 8-game update does not match the fixed four-game stream for {large['seed']}")
    return large['ledger']['first_online_batch']


def panel_requests(cells, parents, partition, board):
    for name in CONTRACTS:
        if name not in parents:
            continue
        contract_cells = [cell for cell in cells if cell['contract'] == name]
        bc_name = name+'/bc'
        parent = parents[name]['parent']
        endpoint = parents[name]['endpoint']
        roles = {bc_name: dict(endpoint, path=str(Path(parent)/'duel/last_bc.pt'))}
        full, small = [bc_name], [bc_name] if partition == 'validation' else []
        for cell in contract_cells:
            for key, record in cell['roles'].items():
                if record is None or (partition == 'holdout' and key != 'wall'):
                    continue
                role_name = cell['name']+'/'+key
                roles[role_name] = record
                (small if key == '10000' else full).append(role_name)
        yield name, dict(parent=parent, cells=contract_cells if partition == 'validation' else [],
                         roles=roles, full=full, small=small, partition=partition, board=board)


def evaluate(output, launch, parents, cells, partition, board, deadline, shortfalls):
    reports = []
    for name, request in panel_requests(cells, parents, partition, board):
        result, _ = run_stage(output, f'{partition}-{name}', launch['contracts'][name], partition,
                              deadline, **request)
        reports.append(read_json(result/'summary.json'))
    return panels.summarize(reports, partition, shortfalls)


def run(output, launch_path):
    started = time.time()
    output = output.resolve()
    launch = read_json(launch_path)
    seconds = launch['seconds']
    hard = started + seconds['total']
    lite_end = hard - seconds['native']
    training_end = lite_end - sum(seconds[key] for key in ('validation', 'holdout', 'report'))
    output.mkdir(parents=True, exist_ok=False)
    write_new(output/'launch.json', dict(launch=launch, started=started, hard_deadline=hard,
              source_manifest_sha256=sha256(launch_path), inputs_sha256=sha256(HERE/'inputs.json'),
              protocol_sha256=sha256(HERE/'PROTOCOL.md')))
    cells = []
    shortfalls = {}
    try:
        check_launch(launch)
        board = freeze_board(output/'frozen', launch)
        empty_human = output/'human-empty'
        empty_human.mkdir()
        preflight = started + seconds['preflight']
        parents = {}
        for name, contract in launch['contracts'].items():
            options = {'parent': launch['base_bc_parent']} if name == 'base' else {}
            result, _ = run_stage(output, f'preflight-{name}', contract, 'preflight', preflight, **options)
            if name == 'base':
                parents[name] = dict(read_json(result)['result']['bc'], parent=launch['base_bc_parent'])
        bc = qualification(output, launch, output.name, training_end, empty_human)
        parents.update({name: record for name, record in bc.items() if record['status'] == 'qualified'})
        shortfalls = {name: record['reason'] for name, record in bc.items() if record['status'] == 'unqualified'}
        active_routes = [route for route in panels.ROUTES if cell_contract(route) in parents]
        for route, seed in INPUTS['cell_order']:
            source_name = cell_contract(route)
            if source_name not in parents:
                continue
            now = time.time()
            deadline = now + INPUTS['seconds']['ppo_hard']
            if deadline > training_end:
                raise StageFailed('the next PPO cell cannot receive its full frozen wall budget')
            name = f'{route}-{seed}'
            contract = launch['contracts'][source_name]
            parent = parents[source_name]
            root = Path(contract['source'])/'runs'/output.name/name
            _, outcome = run_stage(output, name, contract, 'ppo', deadline,
                                   run=str(root), parent=parent['parent'], empty_human=str(empty_human),
                                   endpoint=parent['endpoint'], seed=seed, rollout_games=8 if route=='a' else 4,
                                   admission=now+INPUTS['seconds']['ppo_admission'])
            if not (root/'budget.json').exists():
                raise StageFailed(f'{name} did not initialize before its wall deadline')
            cell = dict(arm.summarize(root, Path(parent['parent']), outcome), name=name, contract=source_name,
                        route=route, seed=seed, stage=outcome, run=str(root))
            write_new(output/f'{name}-ledger.json', cell)
            cells.append(cell)
            if cell['ledger']['error'] or not cell['ledger']['settled_batches']:
                raise StageFailed(f'{name} did not settle a valid PPO batch')
            if route in ('base', 'a'):
                pair = {item['route']: item for item in cells if item['seed'] == seed}
                if 'base' in pair and 'a' in pair:
                    write_new(output/f'first-online-a8-{seed}.json', check_first_online(pair['base'], pair['a']))
        write_new(output/'cells.json', cells)
        validation_end = min(lite_end-seconds['holdout']-seconds['report'], time.time()+seconds['validation'])
        validation = evaluate(output, launch, parents, cells, 'validation', board, validation_end, shortfalls)
        write_new(output/'validation.json', validation)
        if any(validation['contrasts'][route]['wall']['status'] != 'observed' for route in active_routes):
            raise StageFailed('the equal-wall validation panel is incomplete')
        chosen = panels.deployment_choice(validation)
        write_new(output/'deployment.json', dict(route=chosen, validation_sha256=sha256(output/'validation.json'),
                  endpoint='wall', native_seed=INPUTS['seeds'][1], frozen_before_holdout=True))
        holdout_end = min(lite_end-seconds['report'], time.time()+seconds['holdout'])
        holdout = evaluate(output, launch, parents, cells, 'holdout', board, holdout_end, shortfalls)
        write_new(output/'holdout.json', holdout)
        for name in parents:
            run_stage(output, f'mc-{name}', launch['contracts'][name], 'mc', lite_end,
                      cells=[cell for cell in cells if cell['contract'] == name])
        complete = all(holdout['contrasts'][route]['wall']['status'] == 'observed' for route in active_routes)
        status = 'incomplete_bc' if shortfalls else 'observed'
        result = dict(status=status if complete else 'incomplete_holdout', deployment_candidate=chosen,
                      validation=validation, holdout=holdout)
    except StageFailed as failure:
        result = dict(status='incomplete', reason=str(failure), completed_cells=len(cells))
    write_new(output/'result.json', dict(result, bc_shortfalls=shortfalls,
              wall_seconds=time.time()-started, hard_deadline=hard))
    return result['status'] == 'observed'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    launch = commands.add_parser('run')
    launch.add_argument('--output', type=Path, required=True)
    launch.add_argument('--launch', type=Path, required=True)
    child = commands.add_parser('stage')
    child.add_argument('--request', type=Path, required=True)
    args = parser.parse_args()
    torch.set_num_threads(INPUTS['trainer_threads'])
    if args.command == 'run':
        raise SystemExit(0 if run(args.output, args.launch) else 1)
    else:
        stage(read_json(args.request))


if __name__ == '__main__':
    main()
