"""L1 re-entry: run the final evaluation of a finished run from its frozen checkpoint.

The parent's selection is pinned verbatim, so the child evaluates exactly the artifact the
parent froze. A new run cannot start in the evaluate phase, so this creates the branch,
lets the coordinator write its own state, stops it before any batch commits, then requests
the evaluation and resumes.

Usage: python l1_reeval.py <repo-root> <parent-run> <child-run> <wesnoth-binary>
"""
import json, os, signal, subprocess, sys, time
from pathlib import Path

root = Path(sys.argv[1]).resolve()
parent = Path(sys.argv[2]).resolve()
child = Path(sys.argv[3]).resolve()
wesnoth = str(Path(sys.argv[4]).resolve())
os.chdir(root)
sys.path.insert(0, str(root))
for line in (root / '.runtime/environment.sh').read_text().splitlines():
    line = line.strip()
    if not line or line.startswith('#') or '=' not in line:
        continue
    key, value = line.split('=', 1)
    os.environ[key.replace('export ', '').strip()] = value.strip().strip('"').strip("'")
os.environ['WESNOTH_EXE'] = wesnoth
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

import shutil
from learning.coordinator import Experiment

config = dict(hours=0.5, workers=8, device='cpu', trainer_threads=1, seed=20261017,
              final_blocks=30, formats=['duel'], bc_batch_games=20, bc_records=2048,
              bc_validation_records=1024, validation_interval=100000, engine='lite',
              evaluation_engine='native', allow_approximate=True, phase='bc',
              bc_games={'duel': 40, 'ffa4': 1, 'team2v2': 1},
              native_bc_games={'duel': 0, 'ffa4': 0, 'team2v2': 0})

state_path = child / 'duel/state.json'
if child.exists():
    raise SystemExit(f'{child} already exists')
experiment = Experiment(child, config=config, wesnoth=wesnoth, branch_from=str(parent))
for name in ('duel/selected.pt', 'duel/selection.json'):
    shutil.copyfile(parent / name, child / name)
print('branch', json.dumps(json.loads((child / 'branch.json').read_text())['checkpoints'],
                           sort_keys=True), flush=True)
print('pinned', json.loads((child / 'duel/selection.json').read_text())['selected_sha256'],
      flush=True)

log = open(child.parent / 'c-eval.log', 'w', buffering=1)


def launch(*extra):
    command = [sys.executable, '-u', '-m', 'learning', 'run', '--run-dir', str(child), *extra]
    log.write(' '.join(command) + '\n')
    return subprocess.Popen(command, cwd=str(root), start_new_session=True,
                            stdout=log, stderr=subprocess.STDOUT, env=dict(os.environ))


def stop(process, note):
    for sig in (signal.SIGINT, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=180 if sig == signal.SIGINT else 60)
            log.write(f'{note}: stopped by {sig.name}\n')
            return
        except subprocess.TimeoutExpired:
            continue


process = launch('--resume', str(child))
deadline = time.time() + 600
while time.time() < deadline:
    if state_path.exists():
        break
    time.sleep(2)
stop(process, 'bootstrap')
state = json.loads(state_path.read_text())
print('bootstrap state', json.dumps({k: state.get(k) for k in ('stage', 'version')}), flush=True)

from learning.phases import request_phase
print('phase', json.dumps(request_phase(child, 'evaluate', hours=0.5)), flush=True)
process = launch('--resume', str(child))
code = process.wait()
log.write(f'evaluate exit {code}\n')
summary = json.loads((child / 'duel/report/summary.json').read_text())
print('result', json.dumps({k: summary.get(k) for k in ('status', 'version', 'selected_kind',
                                                        'evaluation_engine', 'checkpoint_sha256')},
                           sort_keys=True), flush=True)
print('controls', json.dumps({label: {k: row.get(k) for k in
                                      ('status', 'blocks', 'planned_blocks', 'missing_blocks',
                                       'distinct_scenarios', 'difference')}
                              for label, row in summary['controls'].items()}, sort_keys=True),
      flush=True)
