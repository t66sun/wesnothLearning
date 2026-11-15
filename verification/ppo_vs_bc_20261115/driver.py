"""Prepare or execute the one authorized #349 score-only panel."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tarfile
import time

import torch

from learning.common import read_json, sha256
from learning.manifest import tree_hashes
from learning.sample import collect
from verification.duel_ppo_comparison_20261106.audit import write_new

from lineage import INPUTS, adapter_identity, audit_boards, exposure, read_cohort, require, worker
from panel import NUM_JOBS, build_schedule, export_policies, recount, verify_schedule


def prepare(output, archive, commit):
    adapter = adapter_identity(archive, commit)
    runtime = worker()
    cohort = read_cohort()
    exposed, old_seeds = exposure(cohort)
    boards = audit_boards(set(exposed['excluded_boards']), runtime)
    output.mkdir(exist_ok=False)
    policies = export_policies(output)
    source_launch = read_json(Path(INPUTS['old_launch']))
    parent_manifest = read_json(Path(source_launch['parent'])/'manifest.json')
    schedule = build_schedule(output, runtime, boards, policies, parent_manifest['baseline']['path'])
    require(not {job['seed'] for job in schedule} & old_seeds, 'combat seeds overlap the #306 lineage')
    write_new(output/'lineage.json', dict(cohort=cohort, exposure=exposed))
    write_new(output/'schedule.json', schedule)
    launch = dict(issue=349, adapter=adapter, runtime=runtime, boards=boards, policies=policies,
                  roles=cohort['roles'], task=schedule[0]['task_id'],
                  games=NUM_JOBS, paired_slots=NUM_JOBS//len(cohort['roles']),
                  workers=INPUTS['workers'], seconds=INPUTS['seconds'],
                  bootstrap_seed=INPUTS['bootstrap_seed'], bootstrap_samples=INPUTS['bootstrap_samples'],
                  minimum_gain_pp=INPUTS['minimum_gain_pp'], interval_lower_bound=0,
                  schedule_sha256=sha256(output/'schedule.json'), lineage_sha256=sha256(output/'lineage.json'))
    write_new(output/'launch.json', launch)
    print(json.dumps(dict(launch=str(output/'launch.json'), launch_sha256=sha256(output/'launch.json'),
                          schedule_sha256=launch['schedule_sha256'], jobs=len(schedule),
                          paired_slots=launch['paired_slots'], lineage_sha256=launch['lineage_sha256']),
                     indent=2))


def preflight(output, launch):
    adapter = launch['adapter']
    require(adapter_identity(Path(adapter['archive']), adapter['commit']) == adapter,
            'score-only adapter changed')
    require(worker() == launch['runtime'], 'scoring runtime changed')
    require(sha256(output/'schedule.json') == launch['schedule_sha256']
            and sha256(output/'lineage.json') == launch['lineage_sha256'], 'prepared inputs changed')
    for name, role in launch['roles'].items():
        require(sha256(Path(role['path'])) == role['checkpoint_sha256'], f'checkpoint changed: {name}')
        policy = launch['policies'][name]
        require(tree_hashes(Path(policy['folder'])) == policy['files'], f'greedy export changed: {name}')
    verify_schedule(read_json(output/'schedule.json'))


def score_games(output):
    jobs = read_json(output/'runtime-schedule.json')
    verify_schedule(jobs)
    replies = collect(jobs, INPUTS['workers'], output/'results.jsonl')
    print(json.dumps(dict(expected=len(jobs), replies=len(replies),
                          complete=sum(row['status'] == 'complete' for row in replies))), flush=True)


def audit_games(output):
    frozen = read_json(output/'schedule.json')
    deadline = read_json(output/'panel-exit.json')['deadline']
    jobs = read_json(output/'runtime-schedule.json')
    require(jobs == [dict(job, deadline=deadline) for job in frozen], 'active schedule changed')
    with (output/'results.jsonl').open(encoding='utf-8') as stream:
        result = recount(jobs, [json.loads(line) for line in stream])
    write_new(output/'audit-result.json', result)
    with tarfile.open(output/'raw-metadata.tar.gz', 'x:gz', compresslevel=1) as bundle:
        for path in sorted(output.iterdir()):
            if path.is_file() and path.suffix in ('.json', '.jsonl', '.log') and path.name != 'audit.log':
                bundle.add(path, arcname=path.name)
    print(json.dumps(result), flush=True)


def run_stage(output, stage, deadline):
    started = time.time()
    require(started < deadline, f'{stage} has no remaining budget')
    with (output/f'{stage}.log').open('x', encoding='utf-8') as stream:
        command = [sys.executable, '-u', str(Path(__file__).resolve()), stage, str(output)]
        process = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        timed_out = False
        try:
            code = process.wait(timeout=max(0, deadline-time.time()))
        except (subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
            os.killpg(process.pid, signal.SIGKILL)
            code = process.wait()
            timed_out = isinstance(exc, subprocess.TimeoutExpired)
    finished = time.time()
    outcome = dict(started=started, deadline=deadline, finished=finished,
                   wall_seconds=finished-started, exit_code=code, timed_out=timed_out)
    write_new(output/f'{stage}-exit.json', outcome)
    print(stage, json.dumps(outcome), flush=True)
    require(code == 0 and not timed_out and finished <= deadline, f'{stage} failed or exceeded the budget')


def run(output, expected):
    launch_path = output/'launch.json'
    require(sha256(launch_path) == expected, 'launch differs from the approved SHA-256')
    launch = read_json(launch_path)
    limits = launch['seconds']
    started = time.time()
    deadline = started + limits['total']
    write_new(output/'run-start.json', dict(started=started, deadline=deadline, launch_sha256=expected))
    result = 'incomplete'
    try:
        preflight(output, launch)
        prepared = time.time()
        require(prepared-started <= limits['preflight'], 'launch preflight exceeded its budget')
        panel_deadline = min(prepared+limits['panel'], deadline-limits['audit'])
        jobs = [dict(job, deadline=panel_deadline) for job in read_json(output/'schedule.json')]
        write_new(output/'runtime-schedule.json', jobs)
        run_stage(output, 'panel', panel_deadline)
        run_stage(output, 'audit', min(time.time()+limits['audit'], deadline))
        audited = read_json(output/'audit-result.json')['verdict']
        require(time.time() <= deadline, 'run exceeded the total budget')
        result = audited
    finally:
        finished = time.time()
        write_new(output/'run-exit.json', dict(verdict=result, started=started, deadline=deadline,
                                               finished=finished, wall_seconds=finished-started))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'run', 'panel', 'audit'))
    parser.add_argument('output', type=lambda path: Path(path).resolve())
    parser.add_argument('--adapter-archive', type=lambda path: Path(path).resolve())
    parser.add_argument('--commit')
    parser.add_argument('--launch-sha256')
    args = parser.parse_args()
    torch.set_num_threads(1)
    if args.action == 'prepare':
        if not args.adapter_archive or not args.commit:
            parser.error('prepare needs --adapter-archive and --commit')
        prepare(args.output, args.adapter_archive, args.commit)
    elif args.action == 'run':
        if not args.launch_sha256:
            parser.error('run needs the approved --launch-sha256')
        run(args.output, args.launch_sha256)
    elif args.action == 'panel':
        score_games(args.output)
    else:
        audit_games(args.output)
