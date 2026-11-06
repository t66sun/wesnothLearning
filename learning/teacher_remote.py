"""Ship one committed teacher change and run a command in a fresh Ubuntu tree."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shlex
import subprocess
from .common import ROOT


def ship(command, *, host='cpuServer', destination=None):
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    name = f'{stamp}_{commit[:12]}'
    parent = '/home/tongshu/myDev/wesnothLearning'
    destination = destination or f'{parent}/verification/teacher_search_20261107/sources/{name}'
    artifacts = ROOT / '.ops' / 'teacher_search'
    artifacts.mkdir(parents=True, exist_ok=True)
    archive = artifacts / f'{name}.tar'
    subprocess.run(['git', 'archive', '--format=tar', f'--output={archive}', commit], cwd=ROOT, check=True)
    remote_archive = f'/tmp/teacher_{name}.tar'
    subprocess.run(['scp', '-q', str(archive), f'{host}:{remote_archive}'], check=True)
    q = shlex.quote
    script = f'''set -eu
mkdir -p {q(destination)}
test ! -e {q(destination + '/SOURCE_COMMIT')}
tar -xf {q(remote_archive)} -C {q(destination)}
cd {q(destination)}
printf '%s\\n' {q(commit)} > SOURCE_COMMIT
mkdir -p data .runtime
ln -s {q(parent + '/WesnothLearning/data/rules')} data/rules
ln -s {q(parent + '/WesnothLearning/.runtime/install')} .runtime/install
cc -O2 -fPIC -shared -o .runtime/entropy.so vendor/arena/entropy.c -ldl
export PYTHONPATH="$PWD" OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
printf 'SOURCE=%s\\nTREE=%s\\n' {q(commit)} "$PWD"
{command}
'''
    subprocess.run(['ssh', '-o', 'BatchMode=yes', host, 'bash', '-s'], input=script, text=True, check=True)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--command', default='/home/tongshu/venv/bin/python -m unittest tests.test_search_teacher -v')
    parser.add_argument('--destination')
    args = parser.parse_args()
    ship(args.command, destination=args.destination)


if __name__ == '__main__':
    main()
