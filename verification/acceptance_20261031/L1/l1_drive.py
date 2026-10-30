"""L1 acceptance driver: BC -> PPO, stop/resume at a committed batch, twin, final evaluation.

Usage: python l1_drive.py <src-root> <work-dir> <wesnoth-binary> [--eval-only]
"""
import json, os, signal, subprocess, sys, time
from pathlib import Path

src = Path(sys.argv[1]).resolve()
work = Path(sys.argv[2]).resolve()
wesnoth = str(Path(sys.argv[3]).resolve())
phase_only = '--eval-only' in sys.argv
work.mkdir(parents=True, exist_ok=True)
py = os.environ.get('L1_PYTHON', str(Path.home() / 'venv/bin/python'))
env = dict(os.environ)
env.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy', OMP_NUM_THREADS='1',
           MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', PYTHONPATH=str(src),
           WESNOTH_EXE=wesnoth, PYTHONUNBUFFERED='1')
environment = src / '.runtime/environment.sh'
if environment.exists():
    out = subprocess.run(['bash', '-c', f'set -a; . {environment}; env -0'],
                         capture_output=True, text=True)
    for item in out.stdout.split('\0'):
        if '=' in item:
            key, value = item.split('=', 1)
            if key not in ('_', 'PWD', 'OLDPWD', 'SHLVL'):
                env[key] = value

FLAGS = ['--engine', 'lite', '--evaluation-engine', 'native', '--device', 'cpu',
         '--workers', '8', '--trainer-threads', '1', '--formats', 'duel',
         '--bc-games', '40', '1', '1', '--native-bc-games', '0', '0', '0',
         '--bc-batch-games', '20', '--bc-records', '2048',
         '--bc-validation-records', '1024', '--validation-interval', '100000',
         '--final-blocks', '30', '--seed', '20261017', '--wesnoth', wesnoth]
log = work / 'timeline.log'


def note(message):
    line = f'{time.strftime("%H:%M:%S")} {message}'
    print(line, flush=True)
    with log.open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(line + '\n')


def state(run):
    path = Path(run) / 'duel/state.json'
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def applied(run):
    return sum(1 for row in state(run).get('history', [])
               if row.get('method') == 'ppo' and (row.get('updates') or 0) > 0)


def launch(tag, args):
    handle = (work / f'{tag}.log').open('ab')
    proc = subprocess.Popen([py, '-u', '-m', 'learning', *args], cwd=str(src), env=env,
                            stdout=handle, stderr=subprocess.STDOUT, start_new_session=True)
    note(f'{tag}: pid {proc.pid} {" ".join(args)}')
    return proc, handle


def wait_step(tag, proc, done, cap, interval=10):
    started = time.time()
    while True:
        if proc.poll() is not None:
            note(f'{tag}: exited {proc.returncode}')
            return proc.returncode
        if done():
            note(f'{tag}: condition met after {int(time.time() - started)}s')
            return None
        if time.time() - started > cap:
            note(f'{tag}: cap {cap}s reached')
            return None
        time.sleep(interval)


def interrupt(tag, proc, handle):
    if proc.poll() is None:
        note(f'{tag}: SIGINT')
        os.killpg(proc.pid, signal.SIGINT)
        try:
            proc.wait(timeout=180)
        except subprocess.TimeoutExpired:
            note(f'{tag}: SIGINT ignored, SIGKILL')
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=60)
    handle.close()
    note(f'{tag}: stopped rc={proc.returncode}')


def run_phase(name, run_dir, tag):
    proc, handle = launch(tag, ['run', '--run-dir', run_dir, '--phase', 'bc', '--hours', '0.25', *FLAGS])
    wait_step(tag, proc, lambda: state(run_dir).get('stage') in ('bc_complete', 'ppo_complete', 'finished'), 1800)
    interrupt(tag, proc, handle)
    current = state(run_dir)
    note(f'{tag}: stage={current.get("stage")} effective={current.get("effective")}')
    out = subprocess.run([py, '-m', 'learning', 'phase', 'ppo', '--run-dir', run_dir,
                          '--formats', 'duel', '--hours', '0.25'], cwd=str(src), env=env,
                         capture_output=True, text=True)
    note(f'{tag}: phase ppo rc={out.returncode} {out.stdout.strip()} {out.stderr.strip()}')
    if out.returncode != 0 and not current.get('effective'):
        forced = subprocess.run([py, '-m', 'learning', 'phase', 'ppo', '--run-dir', run_dir,
                                 '--formats', 'duel', '--hours', '0.25', '--force',
                                 '--reason', 'L1 reduced panel: duel BC gate not reached in 40 games'],
                                cwd=str(src), env=env, capture_output=True, text=True)
        note(f'{tag}: phase ppo forced rc={forced.returncode} {forced.stdout.strip()} '
             f'{forced.stderr.strip()}')


def run_ppo(name, run_dir, tag, stop_after=None, cap=2400):
    proc, handle = launch(tag, ['run', '--run-dir', run_dir, '--resume', run_dir])
    if stop_after is None:
        done = lambda: state(run_dir).get('stage') in ('ppo_complete', 'finished')
    else:
        done = lambda: (applied(run_dir) >= stop_after
                        and state(run_dir).get('pending_train') is None
                        and state(run_dir).get('stage') not in ('bc', 'finished'))
    wait_step(tag, proc, done, cap)
    interrupt(tag, proc, handle)
    current = state(run_dir)
    note(f'{tag}: applied={applied(run_dir)} pending={current.get("pending_train")} '
         f'stage={current.get("stage")} version={current.get("version")} '
         f'kl_stops={current.get("kl_stops")}')


def run_eval(name, run_dir, tag, cap=2400):
    out = subprocess.run([py, '-m', 'learning', 'phase', 'evaluate', '--run-dir', run_dir,
                          '--formats', 'duel', '--hours', '0.4'], cwd=str(src), env=env,
                         capture_output=True, text=True)
    note(f'{tag}: phase evaluate rc={out.returncode} {out.stdout.strip()} {out.stderr.strip()}')
    proc, handle = launch(tag, ['run', '--run-dir', run_dir, '--resume', run_dir])
    wait_step(tag, proc, lambda: state(run_dir).get('status') == 'finished', cap)
    interrupt(tag, proc, handle)
    note(f'{tag}: status={state(run_dir).get("status")} stage={state(run_dir).get("stage")}')


def compare(a, b, stop_batch):
    def history(run):
        return {row['batch']: dict(method=row.get('method'), updates=row.get('updates') or 0,
                                   after=row.get('policy_sha256_after'))
                for row in state(run).get('history', [])}
    left, right = history(a), history(b)
    batches = [key for key in sorted(left) if key >= stop_batch
               and left[key]['method'] == 'ppo' and left[key]['updates'] > 0]
    verdict = all(left[key] == right.get(key) for key in batches)
    report = dict(stop_batch=stop_batch, compared=batches, identical=verdict,
                  applied_a=applied(a), applied_b=applied(b),
                  batches_a=left, batches_b=right)
    (work / 'same_future.json').write_text(json.dumps(report, indent=1, sort_keys=True) + '\n',
                                           encoding='utf-8', newline='\n')
    note(f'compare: batches={batches} identical={verdict}')
    return report


def main():
    a, b = str(work / 'a'), str(work / 'b')
    if not phase_only:
        note('A: BC phase')
        run_phase('a', a, 'a-bc')
        note('A: PPO until two applied updates')
        run_ppo('a', a, 'a-ppo-stop', stop_after=2)
        stop_batch = state(a).get('batch')
        boundary = state(a)
        (work / 'boundary.json').write_text(
            json.dumps({key: boundary.get(key) for key in
                        ('batch', 'version', 'pending_train', 'stage', 'counters',
                         'kl_stops', 'effective')}, indent=1, sort_keys=True) + '\n',
            encoding='utf-8', newline='\n')
        note(f'A: resumed after batch {stop_batch}')
        note('A: PPO to completion')
        run_ppo('a', a, 'a-ppo-finish', cap=2400)
        note('A: final evaluation')
        run_eval('a', a, 'a-eval')
        note('B: twin, uninterrupted')
        run_phase('b', b, 'b-bc')
        run_ppo('b', b, 'b-ppo-finish', cap=2400)
        if stop_batch is not None:
            compare(a, b, int(stop_batch))
    else:
        run_eval('a', a, 'a-eval')
    note('done')


main()
