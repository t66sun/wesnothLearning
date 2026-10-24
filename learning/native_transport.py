"""Real Wesnoth 1.18.8 session, controlled through a file-backed Lua CA RPC.

The native process remains alive between actions. Each instance owns an isolated
userdata/add-on directory; it never installs into the user's game profile.
Snapshots are expensive restart-and-replay recipes, not native kernel snapshots.
No game is launched until NativeTransport is explicitly constructed/reset.
"""
from __future__ import annotations

from collections import deque
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import secrets
import shutil
import subprocess
import tempfile
import threading
import time

from .common import ROOT
from .features import schema
import native


class NativeTransportError(RuntimeError):
    pass


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def _stable(value):
    """Wall clocks are diagnostics, not deterministic game state."""
    if isinstance(value, dict):
        return {k: _stable(v) for k, v in value.items() if k not in ('timing', 'elapsed_ms', 'ms')}
    if isinstance(value, list):
        return [_stable(v) for v in value]
    return value


def _scenario(spec, options):
    width, height = int(spec['width']), int(spec['height'])
    terrain = spec['terrain']
    if width < 1 or height < 1 or len(terrain) != width * height or any(not isinstance(t, str) for t in terrain):
        raise ValueError('native reset needs a complete row-major terrain map')
    sides = spec['sides']
    if [s['id'] for s in sides] != list(range(1, len(sides) + 1)) or len(sides) not in (2, 4):
        raise ValueError('native transport supports sequential sides in duel/FFA4/2v2')
    # Data strings are WML quoted; map terrain itself cannot contain delimiters.
    import re
    if any(not re.fullmatch(r'[A-Za-z0-9_^+\-/]+', t) for t in terrain):
        raise ValueError('invalid native terrain token')
    board = dict(terrain=[terrain[y*width:(y+1)*width] for y in range(height)], starts=[])
    q = lambda text: '"'+str(text).replace('"','""')+'"'
    side_wml = []
    for side in sides:
        side_wml.append(f'''[side]
side={side['id']}
controller=ai
no_leader=yes
random_faction=no
''' + (f"faction={q(side['faction'])}\n" if side.get('faction') else '') + f'''team_name={q(side.get('team', side['id']))}
gold={int(side.get('gold', 100))}
# WML `income` is added to the engine's base income (2 in 1.18.8), unlike
# GameSpec `base_income`, which is the final base. Match the lite economy's
# fixed village gold and support too.
income={int(side.get('base_income', 2)) - 2}
village_gold=2
village_support=1
recruit={q(','.join(side.get('recruit', [])))}
fog={'yes' if side.get('fog', True) else 'no'}
shroud={'yes' if side.get('shroud', False) else 'no'}
share_view={'yes' if side.get('share_view', True) else 'no'}
share_maps={'yes' if side.get('share_maps', True) else 'no'}
[/side]''')
    return '''[multiplayer]
id=learning_native_rpc
name="Learning Native RPC"
victory_when_enemies_defeated=no
experience_modifier=''' + str(int(spec.get('experience_modifier',100))) + '''
turns=''' + str(int(spec.get('max_turns', 30))) + '\nmap_data=' + q(native.map_wml(board)) + '''
{DEFAULT_SCHEDULE}
''' + '\n'.join(side_wml) + '''
[event]
name=preload
first_time_only=no
[lua]
code=<<
wesnoth.require('~add-ons/arena_runtime/runtime.lua').setup(''' + native.lua(options) + ''')
>>
[/lua]
[/event]
[event]
name=prestart
[lua]
code=<< wesnoth.require('~add-ons/LearningNativeRPC/native_rpc.lua').initialize() >>
[/lua]
[/event]
[/multiplayer]
'''


class NativeTransport:
    engine_id = 'native-1.18.8'

    def __init__(self, game_spec=None, *, wesnoth=None, timeout=30, startup_timeout=120, work_dir=None):
        if not math.isfinite(timeout) or not 0 < timeout <= 3600 or not 0 < startup_timeout <= 3600:
            raise ValueError('invalid native transport timeouts')
        self.executable = native.find_wesnoth(wesnoth)
        self.timeout = timeout
        self.startup_timeout = startup_timeout
        self.work_dir = Path(work_dir or ROOT / 'tmp')
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.process = None
        self.directory = None
        self.messages = queue.Queue(maxsize=1024)
        self.log_tail = deque(maxlen=80)
        self.commands = []
        self.current = None
        self.result = None
        self.serial = 0
        self.reader = None
        self.spec = None
        if game_spec is not None:
            self.reset(game_spec)

    def reset(self, game_spec):
        with self.lock:
            self.close()
            self.spec = copy.deepcopy(game_spec)
            if not 0 <= int(self.spec.get('seed', 1)) <= 0xffffffff or int(self.spec.get('max_turns', 30)) < 1:
                raise ValueError('native seed must be uint32 and turn limit positive')
            self.commands = []
            self.serial = 0
            self.result = None
            self.current = None
            self.messages = queue.Queue(maxsize=1024)
            self.log_tail.clear()
            self.directory = tempfile.TemporaryDirectory(prefix='native-rpc-', dir=self.work_dir)
            user = Path(self.directory.name)
            addondir = user / 'data/add-ons'
            addon = addondir / 'LearningNativeRPC'
            (addon / 'lua').mkdir(parents=True)
            self.token = secrets.token_hex(16)
            self.prefix = 'NATIVE_RPC ' + self.token + ' '
            self.judge_prefix = 'ARENA2 ' + self.token + ' '
            shutil.copytree(ROOT / 'vendor/arena/runtime', addondir / 'arena_runtime')
            shutil.copyfile(Path(__file__).with_name('native_rpc.lua'), addon / 'native_rpc.lua')
            from .lite_host import host_modules
            astra_dir = addondir / 'gpt6astra/lua'
            astra_dir.mkdir(parents=True)
            for name, source in host_modules().items():
                if name.startswith('astra/'):
                    (astra_dir / name.split('/', 1)[1]).write_bytes(source.encode('utf-8'))
            if self.spec.get('differential_probe'):
                shutil.copyfile(ROOT / 'engine_lite/lua/differential_probe.lua', addon / 'differential_probe.lua')
            for source in (ROOT / 'lua').glob('*.lua'):
                (addon / 'lua' / source.name).write_text(source.read_text(encoding='utf-8').replace('@ADDON@', 'LearningNativeRPC'), encoding='utf-8')
            (addon / 'lua/features.lua').write_text('return ' + native.lua(schema()) + '\n', encoding='utf-8')
            (addon / 'lua/config.lua').write_text('return {candidate_budget_ms=200}\n', encoding='utf-8')
            (addon / 'session.lua').write_text('return ' + native.lua(dict(token=self.token, spec=self.spec, last_id=0, memories={})) + '\n', encoding='utf-8')
            self.command_path = addon / 'command.lua'
            self.command_path.write_text('return {id=0,kind="idle"}\n', encoding='utf-8')
            teams = [s.get('team', s['id']) for s in self.spec['sides']]
            options = dict(token=self.token, max_turns=self.spec.get('max_turns', 30), teams=teams,
                timeout=self.timeout, first_timeout=self.startup_timeout, max_actions=100000,
                fog=True, shroud=False, share_view=True, share_maps=True, lenient=False)
            (addon / '_main.cfg').write_text(_scenario(self.spec, options), encoding='utf-8')
            (user / 'preferences').write_text('save_replays=no\nauto_save_max=0\n', encoding='utf-8')
            command = [self.executable, '--userdata-dir', str(user), '--usercache-dir', str(user / 'cache'),
                '--multiplayer', '--scenario=learning_native_rpc', '--era=era_default', '--rng-seed', str(self.spec.get('seed', 1)),
                '--turns', str(self.spec.get('max_turns', 30)), '--no-log-to-file', '--nobanner', '--nosound', '--nogui', *native.console_options()]
            for side in self.spec['sides']:
                number = side['id']
                ai_path = addon / f'side{number}.cfg'
                # No default RCA stages can act while the RPC CA yields control.
                ai_path.write_text(f'''[ai]
id=learning_rpc_{number}
[stage]
id=main_loop
name=ai_default_rca::candidate_action_evaluation_loop
[candidate_action]
engine=lua
id=learning_rpc
name=learning_rpc
max_score=100000
location="~add-ons/LearningNativeRPC/native_rpc.lua"
[/candidate_action]
[/stage]
[/ai]
''', encoding='utf-8')
                command += ['--controller', f'{number}:ai', '--ai-config', f'{number}:~add-ons/LearningNativeRPC/side{number}.cfg']
            source_files = [Path(__file__), Path(__file__).with_name('native_rpc.lua'), ROOT / 'data/opponents/gpt6astra.zip', *sorted((ROOT / 'lua').glob('*.lua'))]
            if self.spec.get('differential_probe'):
                source_files.append(ROOT / 'engine_lite/lua/differential_probe.lua')
            self.source_hash = _hash({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in source_files})
            self.executable_hash = hashlib.sha256(Path(self.executable).read_bytes()).hexdigest()
            try:
                self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    creationflags=native.creationflags(), start_new_session=os.name != 'nt')
                self.reader = threading.Thread(target=self._read_output, daemon=True)
                self.reader.start()
                self._ready(0, self.startup_timeout)
            except BaseException:
                self.close()
                raise
            return copy.deepcopy(self.current)

    def _read_output(self):
        process=self.process;messages=self.messages;prefix=self.prefix;judge_prefix=self.judge_prefix
        try:
            while True:
                raw = process.stdout.readline(8 * 1024 * 1024 + 1)
                if not raw:
                    messages.put(None)
                    return
                if len(raw) > 8 * 1024 * 1024:
                    messages.put(dict(kind='ERROR', payload=dict(error='native RPC line exceeds 8 MiB')))
                    return
                line = raw.decode('utf-8', 'replace').strip()
                self.log_tail.append(line[:2000])
                if line.startswith(prefix):
                    messages.put(json.loads(line[len(prefix):]))
                elif line.startswith(judge_prefix + 'RESULT '):
                    messages.put(dict(kind='RESULT', payload=json.loads(line[len(judge_prefix + 'RESULT '):])))
                elif 'error scripting/lua:' in line or 'error config:' in line:
                    messages.put(dict(kind='ERROR', payload=dict(error=line)))
        except Exception as exc:
            messages.put(dict(kind='ERROR', payload=dict(error='native reader failed: ' + str(exc))))

    def _receive(self, deadline):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise NativeTransportError('native RPC timed out; tail: ' + '\n'.join(self.log_tail))
        try:
            message = self.messages.get(timeout=remaining)
        except queue.Empty:
            raise NativeTransportError('native RPC timed out; tail: ' + '\n'.join(self.log_tail)) from None
        if message is None:
            raise NativeTransportError(f'native process exited without the requested response ({self.process.poll()}); tail: ' + '\n'.join(self.log_tail))
        if message['kind'] == 'ERROR':
            raise NativeTransportError(message['payload'].get('error', 'native RPC error'))
        if message['kind'] == 'RESULT':
            self.result = message['payload']
        return message

    def _ready(self, serial, timeout=None):
        deadline = time.monotonic() + (timeout or self.timeout)
        while True:
            message = self._receive(deadline)
            if message['kind'] == 'RESULT':
                self.current = dict(self.current or {}, finished=True, truncated=self.result['reason'] == 'turn_limit', result=self.result)
                return
            if message.get('id') != serial:
                raise NativeTransportError('native RPC response sequence mismatch')
            if message['kind'] == 'READY':
                self.current = message['payload']
                return
            raise NativeTransportError('native RPC expected READY, got ' + message['kind'])

    def _request(self, kind, **payload):
        with self.lock:
            if self.process is None or self.spec is None:
                raise NativeTransportError('native session is not reset')
            if self.result is not None:
                raise NativeTransportError('native game has finished; reset before making another request')
            self.serial += 1
            command = dict(id=self.serial, token=self.token, kind=kind, **payload)
            temporary = self.command_path.with_suffix('.tmp')
            temporary.write_text('return ' + native.lua(command) + '\n', encoding='utf-8')
            temporary.replace(self.command_path)
            deadline = time.monotonic() + self.timeout
            try:
                response = self._receive(deadline)
                if response['kind'] == 'RESULT':
                    raise NativeTransportError('native game ended before the requested operation completed')
                if response.get('id') != self.serial or response['kind'] not in ('OBS', 'ACTIONS', 'DECISION', 'OUTCOME'):
                    raise NativeTransportError('native RPC unexpected response to ' + kind)
                result = response['payload']
                self._ready(self.serial)
                if kind in ('step', 'execute_candidate'):
                    result.update({k: v for k, v in self.current.items() if k in ('turn', 'current_side', 'finished', 'truncated', 'result')})
                self.commands.append(dict(kind=kind, payload=copy.deepcopy(payload), response_sha256=_hash(_stable(result))))
                return result
            except BaseException:
                self.close()
                raise

    def observe(self, side):
        return self._request('observe', side=int(side))

    def legal_actions(self, side):
        return self._request('legal_actions', side=int(side))['actions']

    def decision(self, side, *, teacher=False, budget_ms=500):
        if not isinstance(budget_ms, int) or not 1 <= budget_ms <= 60000:
            raise ValueError('candidate budget_ms must be an integer in [1,60000]')
        return self._request('decision', side=int(side), teacher=bool(teacher), budget_ms=budget_ms)

    def step(self, action):
        return self._request('step', action=action)

    def execute_candidate(self, action):
        return self._request('execute_candidate', action=action)

    def snapshot(self):
        with self.lock:
            if self.spec is None:
                raise NativeTransportError('native session is not reset')
            return dict(kind='native_restart_replay_v1', native_version='1.18.8',
                executable_sha256=self.executable_hash, source_sha256=self.source_hash,
                game_spec=copy.deepcopy(self.spec), rpc_log=copy.deepcopy(self.commands),
                state=copy.deepcopy(self.current), cost='full native restart plus replay of every prior RPC; no cheap kernel snapshot')

    def restore(self, snapshot):
        if snapshot.get('kind') != 'native_restart_replay_v1':
            raise ValueError('not a native restart/replay snapshot')
        expected = copy.deepcopy(snapshot)
        self.reset(expected['game_spec'])
        if self.executable_hash != expected['executable_sha256'] or self.source_hash != expected['source_sha256']:
            self.close()
            raise NativeTransportError('native replay source/executable changed')
        try:
            for item in expected['rpc_log']:
                response = self._request(item['kind'], **item['payload'])
                if _hash(_stable(response)) != item['response_sha256']:
                    raise NativeTransportError('native replay diverged; snapshot is not restored')
            if self.current != expected['state']:
                raise NativeTransportError('native replay final state differs from snapshot')
        except BaseException:
            self.close()
            raise

    def close(self):
        process = self.process
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
            if self.reader is not None:
                self.reader.join(timeout=2)
            if process.stdout is not None:
                process.stdout.close()
        self.process = None
        self.reader = None
        if self.directory is not None:
            self.directory.cleanup()
            self.directory = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
