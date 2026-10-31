"""Run one isolated official Wesnoth process and adjudicate native results."""
from contextlib import ExitStack
from pathlib import Path
import json
import gzip
import math
import os
import queue
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
import addons
import native
import params as P
import teams as team_rules


def rank_points(players, survivors, eliminated, faults):
    def key(side):
        if side in faults: return (0, 0)
        if side in survivors: return (2, 0)
        return (1, int(eliminated.get(side, 0)))
    return {side: sum(1 if key(other)<key(side) else .5 if key(other)==key(side) else 0
                      for other in range(1,players+1) if other!=side) for side in range(1,players+1)}


NATIVE_LOG_LIMIT = 80 * 1024 * 1024
ENTROPY_SHIM = Path(__file__).resolve().parents[2] / '.runtime' / 'entropy.so'


def log_exceeded(size):
    """A 60-turn 2v2 native game can emit more than the old 16 MiB cap."""
    return size > NATIVE_LOG_LIMIT


def _child_env(seed):
    env = os.environ.copy()
    if os.name == 'nt' or not ENTROPY_SHIM.is_file():
        return env
    preload = env.get('LD_PRELOAD')
    env['LD_PRELOAD'] = str(ENTROPY_SHIM) + (':' + preload if preload else '')
    env['ARENA_ENTROPY_SEED'] = format(seed, 'x')
    return env


def play_game(bots, seed=1, factions=None, timeout=P.ACTION_TIMEOUT, first_timeout=P.FIRST_TIMEOUT,
              max_turns=P.MAX_TURNS, lenient=False, replay_path=None, fog=True, wesnoth=None,
              visible=False, human_side=0, learning=None, experiment_deadline=None, map_override=None, teams=None,
              shroud=False,share_view=True,share_maps=True):
    n = len(bots)
    teams = team_rules.validate(teams, n)
    if (n not in P.PLAYERS and not (map_override and 2 <= n <= 9)) or not 0 <= seed <= 0xffffffff or max_turns < 1:
        raise ValueError('players must be 2/4/8; seed must be uint32; turns must be positive')
    if not all(math.isfinite(v) and 0 < v <= 3600 for v in (timeout, first_timeout)):
        raise ValueError('invalid time limits')
    if human_side and (not visible or not 1 <= human_side <= n):
        raise ValueError('human play needs a visible game and a valid side')
    exe = native.find_wesnoth(wesnoth)
    factions = list(factions or [P.FACTIONS[i%6] for i in range(n)])
    if len(factions)!=n or any(f not in P.FACTIONS for f in factions):
        raise ValueError('invalid factions')
    output = Path(replay_path or native.ROOT/'replays'/f'game_{time.time_ns()}.json').resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    log_path = output.with_suffix('.log')
    events_path = output.with_suffix('.events.jsonl')
    if learning: events_path=output.with_suffix('.events.jsonl.gz')
    started = time.monotonic()
    token = secrets.token_hex(12)
    prefix = 'ARENA2 ' + token + ' '
    payload = None
    faults = {}
    snapshots = []
    eliminated = {}
    last_survivors = list(range(1,n+1))
    side = 0
    turn = 0
    calls = 0
    active = None
    deadline = started + P.STARTUP_TIMEOUT
    result = None
    with ExitStack() as stack:
        user = Path(stack.enter_context(tempfile.TemporaryDirectory(prefix='wesnoth-native-')))
        addondir = user/'data/add-ons'
        runtime = addondir/'arena_runtime'
        shutil.copytree(native.ROOT/'runtime', runtime)
        (user/'preferences').write_text('save_replays=yes\ndelete_saves=no\nauto_save_max=0\n',encoding='utf-8')
        config = dict(token=token, seed=seed, max_turns=max_turns, timeout=timeout, first_timeout=first_timeout,
                      lenient=lenient, fog=fog,shroud=shroud,share_view=share_view,share_maps=share_maps,max_actions=P.MAX_ACTIONS)
        if teams: config['teams'] = teams
        if map_override:
            config['map_override'] = map_override
        preinstalled={}
        if learning:
            config['learning'] = learning['sides']
            shutil.copytree(learning['support'], addondir/'LearningSupport')
            shutil.copyfile(native.ROOT.parents[1]/'learning/collector.lua', runtime/'collector.lua')
            teacher=learning.get('dagger_teacher')
            if teacher:
                teacher_addon=stack.enter_context(addons.open_addon(teacher))
                teacher_id=addons.validate(teacher_addon)
                if teacher_id!='gpt6astra': raise ValueError('DAgger teacher must be frozen Astra')
                shutil.copytree(teacher_addon,addondir/teacher_id,dirs_exist_ok=True)
                preinstalled[str(Path(teacher).resolve())]=teacher_id
                for item in config['learning'].values():
                    if not item.get('teacher'): item['dagger_entry']='~add-ons/gpt6astra/lua/bot.lua'
        (runtime/'_main.cfg').write_text(native.scenario(config,factions,human_side), encoding='utf-8')
        command = [exe,'--userdata-dir',str(user),'--usercache-dir',str(user/'cache'),
            '--multiplayer','--scenario=arena_native','--era=era_default',
            '--rng-seed',str(seed),'--turns',str(max_turns),'--no-log-to-file',*native.console_options(),
            '--nobanner','--nosound']
        if not visible: command.append('--nogui')
        copied = dict(preinstalled)
        labels = []
        for s, bot in enumerate(bots,1):
            if s==human_side:
                labels.append('human')
                command += ['--controller',f'{s}:human']
            elif bot=='baseline':
                labels.append('baseline')
                command += ['--controller',f'{s}:ai']
            else:
                key = str(Path(bot).resolve())
                if key not in copied:
                    addon, name = stack.enter_context(addons.contestant(bot))
                    if name.casefold() in {v.casefold() for v in copied.values()}:
                        raise ValueError('different submissions have the same add-on ID')
                    shutil.copytree(addon,addondir/name)
                    copied[key] = name
                name = copied[key]
                labels.append(name)
                cfg = runtime/f'side{s}.cfg'
                cfg.write_text(native.contestant_ai(f'~add-ons/{name}/lua/bot.lua',s),encoding='utf-8')
                command += ['--controller',f'{s}:ai','--ai-config',f'{s}:~add-ons/arena_runtime/side{s}.cfg']
            command += ['--side',f'{s}:{factions[s-1]}','--parm',f'{s}:type:{P.LEADERS[P.FACTIONS.index(factions[s-1])]}']
        messages = queue.Queue(maxsize=4096)
        overflow = threading.Event()
        proc = subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=_child_env(seed),
                                creationflags=(native.creationflags()|(subprocess.BELOW_NORMAL_PRIORITY_CLASS if os.name=='nt' and experiment_deadline is not None else 0)) if not visible else 0,
                                start_new_session=os.name!='nt')
        def reader():
            try:
                while True:
                    line_limit = 2*1024*1024 if learning else 131072
                    raw = proc.stdout.readline(line_limit+1)
                    if not raw: break
                    if len(raw)>line_limit: overflow.set(); break
                    try: messages.put_nowait(raw.decode('utf-8','replace'))
                    except queue.Full: overflow.set(); break
            finally:
                try: messages.put_nowait(None)
                except queue.Full: overflow.set()
        thread = threading.Thread(target=reader,daemon=True)
        thread.start()
        log_bytes = 0
        infrastructure_error = None
        scripting_error = False
        try:
            event_stream=gzip.open(events_path,'wt',encoding='utf-8') if learning else events_path.open('w',encoding='utf-8')
            with log_path.open('w',encoding='utf-8') as log,event_stream as events:
                while True:
                    now = time.monotonic()
                    if experiment_deadline is not None and time.time() >= experiment_deadline:
                        raise TimeoutError('experiment_budget_interrupted')
                    if overflow.is_set():
                        raise RuntimeError('native output overflow')
                    if now > deadline:
                        if side and side!=human_side:
                            faults[side] = 'watchdog timeout: '+(active or 'native side turn')
                            payload = dict(reason='watchdog_timeout',survivors=[s for s in last_survivors if s not in faults],
                                           eliminated=eliminated,faults=faults,turns=turn)
                            break
                        if human_side and side==human_side:
                            deadline=now+86400
                        else: raise RuntimeError('native startup or shutdown timed out')
                    try: line = messages.get(timeout=min(.05,max(.001,deadline-now)))
                    except queue.Empty: continue
                    if line is None: break
                    is_learning = line.startswith(prefix+'LEARN ')
                    if not is_learning: log.write(line)
                    if 'error scripting/lua:' in line or 'error config:' in line:
                        scripting_error = True
                    log_bytes += 0 if is_learning else len(line)
                    if log_exceeded(log_bytes): raise RuntimeError(f'native log exceeds {NATIVE_LOG_LIMIT // (1024 * 1024)} MiB')
                    if not line.startswith(prefix): continue
                    kind, text = line[len(prefix):].split(' ',1)
                    event = json.loads(text)
                    events.write(json.dumps({'event':kind,'data':event},ensure_ascii=False)+'\n')
                    if kind=='START': deadline=now+P.OFFICIAL_TIMEOUT
                    elif kind=='TURN':
                        side=event['side'];turn=event['turn'];active=None
                        deadline=now+(86400 if side==human_side else P.OFFICIAL_TIMEOUT)
                    elif kind=='CALL':
                        side=event['side'];active='candidate evaluation/execution';calls+=1
                        deadline=now+float(event['budget'])
                    elif kind=='RETURN':
                        active=None;deadline=now+P.OFFICIAL_TIMEOUT
                    elif kind=='FAULT': faults[event['side']]=event['reason']
                    elif kind=='ELIMINATED':
                        eliminated[event['side']]=event['turn']
                        last_survivors=[s for s in last_survivors if s!=event['side']]
                    elif kind=='SNAPSHOT': snapshots.append(event)
                    elif kind=='RESULT':
                        payload=event;deadline=now+20
                if proc.poll() is None and payload is not None and payload['reason']!='watchdog_timeout':
                    try: proc.wait(timeout=10)
                    except subprocess.TimeoutExpired: raise RuntimeError('native game did not exit after RESULT') from None
                if payload is None:
                    raise RuntimeError(f'native process exited without a result (code {proc.poll()}); inspect {log_path}')
                if scripting_error:
                    raise RuntimeError(f'uncaught native scripting/configuration error; inspect {log_path}')
                if proc.poll() not in (None,0) and payload['reason']!='watchdog_timeout':
                    raise RuntimeError(f'native process failed (code {proc.returncode}); inspect {log_path}')
        except Exception as exc:
            infrastructure_error = str(exc)
        finally:
            if proc.poll() is None: proc.kill()
            proc.wait(timeout=10)
            thread.join(timeout=2)
            proc.stdout.close()
        replays = sorted((user/'saves').glob('*'),key=lambda p:p.stat().st_mtime) if (user/'saves').exists() else []
        native_replay = None
        for file in reversed(replays):
            if 'replay' in file.name.lower():
                suffix = ''.join(file.suffixes) or '.save'
                destination = output.with_suffix('.replay'+suffix)
                shutil.copyfile(file,destination)
                native_replay = str(destination)
                break
        if not infrastructure_error and payload['reason']!='watchdog_timeout' and not native_replay:
            infrastructure_error = 'native game completed but no official replay was saved; inspect '+str(log_path)
        if infrastructure_error:
            output.write_text(json.dumps({'error':infrastructure_error,'bots':labels,'seed':seed,'rules_version':P.RULES_VERSION},ensure_ascii=False,indent=2),encoding='utf-8')
            raise RuntimeError(infrastructure_error)
        faults.update({int(k):v for k,v in dict(payload['faults']).items()})
        eliminated.update({int(k):int(v) for k,v in dict(payload['eliminated']).items()})
        survivors = list(payload['survivors']) if isinstance(payload['survivors'],list) else []
        if not lenient: survivors=[s for s in survivors if s not in faults]
        result = dict(bots=labels,seed=seed,turns=payload['turns'],winner=survivors[0] if len(survivors)==1 else 0,
            survivors=survivors,reason=payload['reason'],faults=faults,
            rank_points=rank_points(n,survivors,eliminated,{} if lenient else faults),eliminated=eliminated,
            seconds=round(time.monotonic()-started,4),actions=calls,factions=factions,
            spawns=(map_override or native.load_map(n))['starts'],lenient=lenient,native_replay=native_replay,
            rules_version=P.RULES_VERSION)
        if teams:
            result.update(team_rules.adjudicate(teams, survivors, faults))
        artifact=dict(schema=2,rules_version=P.RULES_VERSION,result=result,map=map_override or native.load_map(n),frames=snapshots)
        output.write_text(json.dumps(artifact,ensure_ascii=False,indent=2),encoding='utf-8')
    return result
