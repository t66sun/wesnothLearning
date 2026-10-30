#!/usr/bin/env python3
"""Run one prepared curated-replay capture under the native 1.18.8 engine."""
import gzip
import json
import os
import pathlib
import signal
import subprocess
import sys
import time

cap = pathlib.Path(sys.argv[1]).resolve()
timeout = float(sys.argv[2]) if len(sys.argv) > 2 else 420.0
meta = json.loads((cap / 'capture.json').read_text(encoding='utf-8'))
command = list(meta['command'])
game = meta['options']['game_id']

saves = cap / 'userdata' / 'saves'
saves.mkdir(parents=True, exist_ok=True)
with (cap / (game + '.cfg')).open('rb') as source, gzip.open(saves / (game + '.gz'), 'wb') as target:
    target.write(source.read())
command[command.index('--load') + 1] = game + '.gz'
for flag in ('--no-log-to-file', '--log-info=scripting/lua','--log-debug=replay', '--nodelay'):
    if flag not in command:
        command.append(flag)

config = cap / 'config'
config.mkdir(parents=True, exist_ok=True)
(config / 'preferences').write_text('[hotkey]\n    command="playreplay"\n    key="p"\n[/hotkey]\n', encoding='utf-8')

log = cap / (game + '.log')
env = dict(os.environ)
env.setdefault('DISPLAY', ':99')
env.pop('XAUTHORITY', None)
with log.open('w', encoding='utf-8') as handle:
    process = subprocess.Popen(command, stdout=handle, stderr=subprocess.STDOUT, env=env, cwd=str(cap))
    keyer = subprocess.Popen([sys.executable, str(pathlib.Path(__file__).with_name('keyplay.py')), 'p', '2', '1200'],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    deadline = time.time() + timeout
    status = 'timeout'
    while time.time() < deadline:
        if process.poll() is not None:
            status = 'exited'
            break
        if '"complete"' in log.read_text(encoding='utf-8', errors='replace'):
            try:
                process.wait(timeout=60)
                status = 'complete-and-exited'
            except subprocess.TimeoutExpired:
                status = 'complete-but-running'
            break
        time.sleep(2.0)
    keyer.terminate()
    if process.poll() is None:
        process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    text = log.read_text(encoding='utf-8', errors='replace')
    print(json.dumps(dict(game=game, status=status, returncode=process.returncode,
                          complete=text.count('"complete"'), samples=text.count('"sample"'),
                          lines=len(text.splitlines()), log=str(log))))
