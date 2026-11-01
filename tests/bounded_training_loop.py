"""Explicit manual full-loop acceptance; never imported by test discovery.

Run only on instruction. Each stage uses the ordinary CLI and gates.
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
FORMATS = ['duel', 'ffa4', 'team2v2']
RUN = ROOT / 'runs/bounded_loop'
OUT = ROOT / 'verification/bounded_loop_observed'


def read(path):
    return json.loads(path.read_text()) if path.exists() else {}


def states():
    return {fmt: read(RUN / fmt / 'state.json') for fmt in FORMATS}


def command(*args):
    return [PYTHON, '-u', '-m', 'learning', *map(str, args)]


def stage(name, args, seconds, batch_limit=None):
    start = time.time()
    with (OUT / (name + '.log')).open('w') as log:
        process = subprocess.Popen(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        reason = None
        while process.poll() is None:
            snapshot = states()
            if time.time() - start >= seconds:
                reason = 'stage_wall_limit'
            if batch_limit is not None and any(s.get('batch', 0) >= batch_limit for s in snapshot.values()):
                reason = 'committed_batch_limit'
            if reason:
                os.killpg(process.pid, signal.SIGTERM)
                time.sleep(2)
                # Terminate only this stage's process group, including its workers.
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
                break
            time.sleep(1)
        code = process.wait()
    result = dict(stage=name, command=args, seconds=time.time()-start, exit_code=code,
                  stop_reason=reason, states=states())
    (OUT / (name + '.json')).write_text(json.dumps(result, indent=2))
    return code == 0 and reason is None


def phase(name, hours):
    subprocess.run(command('phase', name, '--run-dir', RUN, '--hours', hours),
                   cwd=ROOT, check=True, stdout=(OUT / ('request-'+name+'.log')).open('a'))


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    plan = dict(source=os.environ['SOURCE_COMMIT'], formats=FORMATS, workers=8,
                trainer_threads=1, seed=20261101, engine='lite', evaluation_engine='lite',
                bc_seconds=1200, bc_committed_batches_max=5, bc_game_targets=[24,24,24],
                bc_records=2048, bc_validation_records=1024, epochs=4, minibatch=256,
                ppo_seconds=900, ppo_batch_limit=4, rollout_games=4,
                turn_limit=30, final_blocks=30, evaluation_seconds=900,
                export_seconds=300, total_stage_ceiling_seconds=3300,
                limits='Stage timeout is a hard stop; polling may observe one in-flight batch beyond a committed-batch cap. No automatic retry, forced PPO or gate edits.')
    (OUT / 'plan.json').write_text(json.dumps(plan, indent=2))
    args = command('run', '--run-dir', RUN, '--hours', .32, '--phase', 'bc',
                   '--formats', *FORMATS, '--workers', 8, '--trainer-threads', 1,
                   '--seed', 20261101, '--bc-games', 24,24,24, '--native-bc-games', 0,0,0,
                   '--bc-records', 2048, '--bc-validation-records', 1024,
                   '--training-max-turns', plan['turn_limit'],
                   '--wesnoth', os.environ['WESNOTH_EXE'])
    if not stage('bc', args, 1200, batch_limit=5):
        return finish('FAIL', 'BC execution or bounded batch/time limit')
    if not all(s.get('effective') for s in states().values()):
        return finish('FAIL', 'ordinary BC gate not passed')
    # Two separately budgeted ordinary phases exercise stop/resume from committed state.
    for name in ('ppo_first', 'ppo_resume'):
        initial = {fmt: s.get('batch',0) for fmt,s in states().items()}
        phase('ppo', .12)
        if not stage(name, command('run','--resume',RUN),450,batch_limit=min(initial.values())+4):
            return finish('FAIL', name+' execution or time limit')
        (OUT / (name+'-boundary.json')).write_text(json.dumps(dict(before=initial,after=states()),indent=2))
    if not all(s.get('history') and sum(h.get('updates',0) for h in s['history'] if h.get('method')=='ppo')>=2 for s in states().values()):
        return finish('FAIL', 'fewer than two committed PPO updates')
    phase('evaluate', .24)
    if not stage('evaluate', command('run','--resume',RUN),900):
        return finish('FAIL', 'final evaluation execution or time limit')
    audit = ROOT / 'runs/audit_inputs'
    audit.mkdir()
    for fmt in FORMATS:
        (audit/fmt).symlink_to(RUN/fmt/'data',target_is_directory=True)
    export_args = command('export','--audit-data',audit,'--output',ROOT/'delivery/bounded_loop')
    for fmt in FORMATS: export_args.extend(['--'+fmt,str(RUN/fmt/'selected.pt')])
    if not stage('export',export_args,300):
        return finish('FAIL','audited export')
    return finish('OBSERVED', 'review final panel completeness and all per-format gates before acceptance')


def finish(status, reason):
    (OUT/'result.json').write_text(json.dumps(dict(status=status,reason=reason,states=states()),indent=2))
    print(status,reason,flush=True)
    return 0 if status=='OBSERVED' else 1


if __name__=='__main__':
    raise SystemExit(main())
