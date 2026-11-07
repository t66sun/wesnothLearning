"""Commit archive, fresh Ubuntu checkout, recorded command; no git on the host."""
import datetime
import json
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
label, *command = sys.argv[1:]
source = 'HEAD'
if command[:1] == ['--commit']:
    source, command = command[1], command[2:]
if command and command[0] == '--': command = command[1:]
if not command: raise SystemExit('provide a command')
commit = subprocess.check_output(['git', 'rev-parse', source], cwd=ROOT, text=True).strip()
stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S')
name = f'{stamp}_{label}_{commit[:12]}'
base = '/home/tongshu/myDev/wesnothLearning'
evidence = f'{base}/verification/teacher_integration_20261107'
tree = f'{evidence}/sources/{name}'
report = f'{evidence}/checks/{name}'
archive = ROOT/'.ops/teacher_integration'/f'{name}.tar'
paths = subprocess.check_output(['git', 'ls-tree', '--name-only', '-z', commit], cwd=ROOT).decode().split('\0')
paths = [path for path in paths if path and path != 'verification']
subprocess.run(['git', 'archive', '--format=tar', f'--output={archive}', commit, '--', *paths], cwd=ROOT, check=True)
remote = f'/tmp/teacher_integration_{name}.tar'
subprocess.run(['scp', '-q', str(archive), 'cpuServer:'+remote], check=True)
identity = json.dumps(dict(source_commit=commit, source_tree=tree, command=command, label=label))
q = shlex.quote
script = f'''set -eu
mkdir -p {q(evidence+'/sources')} {q(evidence+'/checks')}
mkdir {q(tree)} {q(report)}
tar -xf {q(remote)} -C {q(tree)}
cd {q(tree)}
printf '%s\\n' {q(commit)} > SOURCE_COMMIT
mkdir -p data/rules .runtime
for item in 1.18.8 1.18.8-training; do
  ln -s {q(base+'/WesnothLearning/data/rules')}/"$item" "data/rules/$item"
done
ln -s /home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered data/rules/1.18.8-combat-filtered
ln -s {q(base+'/WesnothLearning/data/opponents')} data/opponents
ln -s {q(base+'/WesnothLearning/.runtime/install')} .runtime/install
cc -O2 -fPIC -shared -o .runtime/entropy.so vendor/arena/entropy.c -ldl
export PYTHONPATH="$PWD" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
export WESNOTH_EXE="$PWD/.runtime/install/bin/wesnoth"
printf '%s\\n' {q(identity)} > {q(report+'/identity.json')}
printf 'SOURCE=%s\\nTREE=%s\\nREPORT=%s\\n' {q(commit)} {q(tree)} {q(report)}
set +e
set -o pipefail
{shlex.join(command)} 2>&1 | tee {q(report+'/output.txt')}
result=${{PIPESTATUS[0]}}
printf '%s\\n' "$result" > {q(report+'/exit_code')}
exit "$result"
'''
subprocess.run(['ssh', '-o', 'BatchMode=yes', 'cpuServer', 'bash', '-s'], input=script.encode(), check=True)

