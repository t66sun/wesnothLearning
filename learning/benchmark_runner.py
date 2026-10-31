"""Linux, single-worker native/lite resource benchmark with real Astra workloads.

Run explicitly: python -m learning.benchmark_runner --help. No training is run.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import tempfile
import time

from .benchmark import COMPONENTS, _digest, _interval, _summary, benchmark_report, freeze_artifacts
from .common import ROOT, write_json
from .formats import PLAYERS


def process_tree(pid):
    """Read Linux process ancestry, including a child that has already exited."""
    records = {}
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
            records[int(entry.name)] = (int(fields[1]), int(fields[11]) + int(fields[12]))
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
    selected = {pid}
    while True:
        children = {p for p, (parent, _) in records.items() if parent in selected}
        if children <= selected:
            break
        selected.update(children)
    return {p: records[p][1] for p in selected if p in records}


def tree_memory(pid):
    """Return simultaneous tree RSS/PSS; an unreadable PSS stays missing."""
    rss = pss = 0
    available = True
    for process in set(process_tree(pid)) | {os.getpid()}:
        try:
            values = {}
            for line in Path(f'/proc/{process}/smaps_rollup').read_text().splitlines():
                key, _, value = line.partition(':')
                if key in ('Rss', 'Pss'):
                    values[key] = int(value.split()[0]) * 1024
            rss += values['Rss']
            pss += values['Pss']
        except (FileNotFoundError, ProcessLookupError):
            continue
        except (PermissionError, KeyError):
            available = False
    return rss, pss if available else None


def _cpu():
    import resource
    own = resource.getrusage(resource.RUSAGE_SELF)
    waited = resource.getrusage(resource.RUSAGE_CHILDREN)
    # RUSAGE_CHILDREN includes reaped descendants; /proc adds live/unreaped ones.
    live = sum(ticks for pid, ticks in process_tree(os.getpid()).items() if pid != os.getpid()) / os.sysconf('SC_CLK_TCK')
    return own.ru_utime + own.ru_stime + waited.ru_utime + waited.ru_stime + live


def make_spec(work, rules):
    from .lite_policy import game_spec
    import params
    count = PLAYERS[work['format']]
    rotation = work['factions_rotation'] + work['seat'] - 1
    factions = [params.FACTIONS[(rotation + i) % len(params.FACTIONS)] for i in range(count)]
    job = dict(bots=['astra'] * count, factions=factions, seed=work['seed'],
               teams=[1, 2, 1, 2] if work['format'] == 'team2v2' else list(range(1, count + 1)),
               max_turns=work['turn_limit'], allow_approximate=True, fog=True)
    spec = game_spec(job, rules)
    if work['density'] == 'dense':
        occupied = {u['pos'] for u in spec['units']}
        for leader in list(spec['units']):
            origin = leader['pos']
            candidates = sorted(range(spec['width'] * spec['height']), key=lambda p:
                (abs(p % spec['width'] - origin % spec['width']) + abs(p // spec['width'] - origin // spec['width']), p))
            for pos in [p for p in candidates if p not in occupied and spec['terrain'][p] == 'Gg'][:8]:
                occupied.add(pos)
                definition = rules['units']['Elvish Fighter']
                spec['units'].append(dict(id=f'dense_{leader["side"]}_{pos}', unit_type='Elvish Fighter',
                    side=leader['side'], pos=pos, hp=definition['hp'], moves=definition['moves'],
                    attacks_left=1, xp=0, leader=False, status=[], traits=[]))
    return spec


def _emit(kind, value):
    print('BENCH ' + json.dumps(dict(kind=kind, payload=value), allow_nan=False), flush=True)


def worker(config):
    """One isolated process, with a resident native child or Rust/Lua host."""
    work = config['work']
    engine = config['engine']
    cold = work['cache'] == 'cold'
    started = time.perf_counter()
    if cold:
        _emit('BEGIN', {})
    from .adapters import NativeAdapter
    from .lite_host import LiteHost, teacher_candidate
    rules_dir = Path(config['rules_dir'])
    rules = json.loads((rules_dir / 'rules.json').read_text())
    spec = make_spec(work, rules)
    if engine == 'native':
        adapter = NativeAdapter(spec, wesnoth=config['executable'], timeout=config['timeout'])
    elif work['mode'] == 'equal_work':
        # Fixed scripted actions do not need candidate generation, Astra or the
        # teacher. Paying for the Lua host here measured setup that equal work
        # never uses; end-to-end mode still constructs the full host.
        from .adapters import LiteAdapter
        adapter = LiteAdapter(spec, rules_dir, require_accepted=False)
    else:
        adapter = LiteHost(spec, rules_dir, require_accepted=False).adapter
    startup = time.perf_counter() - started
    try:
        if not cold:
            # Warm both hosts without changing state; same public API calls.
            adapter.observe(1)
            adapter.legal_actions(1)
            if work['mode'] == 'end_to_end':
                adapter.decision(1, teacher=True)
            _emit('BEGIN', {})
        cpu_started = _cpu()
        operations = defaultdict(float)
        counts = defaultdict(int)
        serialized = 0
        def call(name, fn, *args, **kwargs):
            nonlocal serialized
            before = time.perf_counter()
            value = fn(*args, **kwargs)
            operations[name] += time.perf_counter() - before
            counts[name] += 1
            before = time.perf_counter()
            serialized += len(json.dumps(value, separators=(',', ':')).encode())
            operations['serialization'] += time.perf_counter() - before
            return value
        actions = 0
        turns = set()
        current = 1
        reason = 'script_complete' if work['mode'] == 'equal_work' else 'decision_limit'
        script = []
        for _ in range(config['max_decisions']):
            view = call('observe', adapter.observe, current)
            if view.get('finished'):
                reason = 'turn_limit' if view.get('truncated') else 'finished'
                break
            current = view['current_side']
            turns.add(view['turn'])
            if work['mode'] == 'equal_work':
                call('legal_actions', adapter.legal_actions, current)
                action = dict(kind='end_turn')
            else:
                row = call('decision', adapter.decision, current, teacher=True)
                action = teacher_candidate(row['teacher_action'])
            if work['mode'] == 'equal_work':
                # A fixed script needs no candidate Lua. Use the core step path
                # directly so equal-work timing measures rules, not a host that
                # this mode never queries.
                outcome = dict(call('execute', adapter.step, action), committed=True)
            else:
                outcome = call('execute', adapter.execute_candidate, action)
            if not outcome.get('committed', outcome.get('execution', {}).get('changed', False)):
                raise RuntimeError('Astra/script action did not commit: ' + json.dumps(action))
            actions += 1
            script.append(dict(side=current, turn=view['turn'], action=action))
            after = outcome.get('view', outcome)
            current = after.get('current_side', outcome.get('current_side', current))
            if after.get('finished') or outcome.get('finished'):
                reason = 'turn_limit' if after.get('truncated', outcome.get('truncated')) else 'finished'
                break
            if work['mode'] == 'equal_work' and actions >= PLAYERS[work['format']] * config['script_turns']:
                break
        measured_cpu = _cpu() - cpu_started
        result = dict(startup_seconds=startup, actions=actions, turns=len(turns), terminal_reason=reason,
            work_signature=_digest(dict(spec=spec, script=script, injected_hits=[])) if work['mode'] == 'equal_work' else None,
            operation_seconds=dict(operations), operation_counts=dict(counts), serialized_bytes=serialized,
            components_seconds={name: (operations.get('serialization', 0.) if name == 'serialization' else
                                      0. if name == 'inference' else None) for name in COMPONENTS},
            worker_cpu_seconds=measured_cpu, faults=[], initial_state_sha256=_digest(spec),
            cache_aligned=True, cache_description='fresh process, OS page cache unchanged' if cold else
                'resident host after one observe/legal warmup (plus one decision for end-to-end); OS page cache unchanged')
        if cold:
            adapter.close()
        _emit('RESULT', result)
    finally:
        adapter.close()


def measure(engine, work, *, executable, rules_dir, timeout, max_decisions, script_turns):
    import resource
    config = dict(engine=engine, work=work, executable=str(executable), rules_dir=str(rules_dir),
                  timeout=timeout, max_decisions=max_decisions, script_turns=script_turns)
    with tempfile.TemporaryDirectory(prefix='wesnoth-bench-') as temporary:
        path = Path(temporary) / 'work.json'
        path.write_text(json.dumps(config))
        env = dict(os.environ, OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
                   CUDA_VISIBLE_DEVICES='', PYTHONUNBUFFERED='1')
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu_started = time.process_time()
        started = time.perf_counter()
        process = subprocess.Popen([sys.executable, '-m', 'learning.benchmark_runner', '--worker', str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1, env=env)
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        active = work['cache'] == 'cold'
        result = None
        peak_rss = peak_pss = 0
        pss_available = True
        try:
            while True:
                if active:
                    rss, pss = tree_memory(process.pid)
                    peak_rss = max(peak_rss, rss)
                    if pss is None:
                        pss_available = False
                    else:
                        peak_pss = max(peak_pss, pss)
                events = selector.select(.02)
                if events:
                    line = process.stdout.readline()
                    if not line:
                        break
                    if line.startswith('BENCH '):
                        message = json.loads(line[6:])
                        if message['kind'] == 'BEGIN' and not active:
                            active = True
                            started = time.perf_counter()
                            cpu_started = time.process_time()
                        elif message['kind'] == 'RESULT':
                            result = message['payload']
                            elapsed = time.perf_counter() - started
                            coordinator_cpu = time.process_time() - cpu_started
                            break
                if time.perf_counter() - started > timeout * max_decisions + 120:
                    raise TimeoutError('benchmark worker exceeded explicit work budget')
            process.wait(timeout=timeout)
            stderr = process.stderr.read()
            if process.returncode or result is None:
                raise RuntimeError(f'{engine} worker failed ({process.returncode}): {stderr[-12000:]}')
            after = resource.getrusage(resource.RUSAGE_CHILDREN)
            if work['cache'] == 'cold':
                cpu = after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime + time.process_time() - cpu_started
                elapsed = time.perf_counter() - started
            else:
                cpu = result['worker_cpu_seconds'] + coordinator_cpu
            result.update(wall_seconds=elapsed, cpu_core_seconds=cpu, peak_rss_bytes=peak_rss,
                peak_pss_bytes=peak_pss if pss_available else None,
                disk_bytes=sum(p.stat().st_size for p in Path(temporary).rglob('*') if p.is_file()),
                cpu_scope='process_tree_including_coordinator', host_id=os.uname().nodename,
                cpu_quota=dict(affinity=sorted(os.sched_getaffinity(0)), cpu_max=_cpu_max()),
                workers=1, threads=1, inference='cpu', memory_sampling_seconds=.02,
                disk_scope='retained benchmark files; transient native files not retained')
            return result
        finally:
            selector.close()
            if process.poll() is None:
                # A worker timeout must also stop its resident native process.
                for child in process_tree(process.pid):
                    if child != process.pid:
                        try:
                            os.kill(child, 9)
                        except ProcessLookupError:
                            pass
                process.kill()
                process.wait()


def _cpu_max():
    path = Path('/sys/fs/cgroup/cpu.max')
    return path.read_text().strip() if path.exists() else None


def observed_report(raw, manifest):
    """Show measured resource ratios even when a deliberately small run is used."""
    by_id = defaultdict(dict)
    for row in raw:
        by_id[row['workload_id']][row['engine']] = row
    groups = defaultdict(list)
    for work in manifest['workloads']:
        pair = by_id[work['id']]
        if set(pair) != {'native', 'lite'}:
            continue
        a, b = pair['native'], pair['lite']
        equal = work['mode'] != 'equal_work' or (a['work_signature'] == b['work_signature'] and
                    a['actions'] == b['actions'] and a['turns'] == b['turns'])
        groups[tuple(work[k] for k in ('format', 'cache', 'mode', 'density'))].append((work, a, b, equal))
    output = []
    for key, rows in groups.items():
        good = [(w, a, b) for w, a, b, equal in rows if equal and not a['faults'] and not b['faults']]
        blocks = defaultdict(list)
        for w, a, b in good:
            blocks[w['block']].append((a, b))
        complete = [pairs for pairs in blocks.values() if len(pairs) == PLAYERS[key[0]]]
        ratios = {}
        for metric in ('wall_seconds', 'cpu_core_seconds', 'peak_pss_bytes'):
            pairs = [(sum(a[metric] for a, _ in block), sum(b[metric] for _, b in block))
                     for block in complete if all(a[metric] is not None and b[metric] is not None for a, b in block)]
            ratios[metric] = dict(ratio=sum(a for a, _ in pairs) / sum(b for _, b in pairs) if pairs else None,
                                 ci95=_interval(pairs) if len(pairs) >= 2 else None)
        output.append(dict(zip(('format', 'cache', 'mode', 'density'), key), samples=len(rows),
            complete_rotation_blocks=len(complete), unequal_work_samples=sum(not row[3] for row in rows),
            resources=ratios, engines={engine: {metric: _summary([r[1 if engine == 'native' else 2][metric]
                for r in good if r[1 if engine == 'native' else 2][metric] is not None]) for metric in
                ('wall_seconds', 'cpu_core_seconds', 'peak_pss_bytes')} for engine in ('native', 'lite')}))
    return dict(status='measured', acceptance='See acceptance.json; these are observed ratios, not full acceptance.', groups=output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', help=argparse.SUPPRESS)
    parser.add_argument('--executable', default=os.environ.get('WESNOTH_EXE'))
    parser.add_argument('--rules-dir', default=str(ROOT / 'data/rules/1.18.8'))
    parser.add_argument('--output')
    parser.add_argument('--formats', nargs='+', choices=tuple(PLAYERS), default=list(PLAYERS))
    parser.add_argument('--modes', nargs='+', choices=('equal_work', 'end_to_end'), default=['equal_work', 'end_to_end'])
    parser.add_argument('--caches', nargs='+', choices=('cold', 'hot'), default=['cold', 'hot'])
    parser.add_argument('--densities', nargs='+', choices=('regular', 'dense'), default=['regular', 'dense'])
    parser.add_argument('--blocks', type=int, default=1)
    parser.add_argument('--seats', type=int, nargs='+', help='Default: every seat in a complete rotation')
    parser.add_argument('--turn-limit', type=int, default=3)
    parser.add_argument('--script-turns', type=int, default=1)
    parser.add_argument('--max-decisions', type=int, default=1000)
    parser.add_argument('--timeout', type=float, default=60)
    args = parser.parse_args()
    if args.worker:
        worker(json.loads(Path(args.worker).read_text()))
        return
    if sys.platform != 'linux':
        parser.error('resource measurement requires Linux /proc; run on the Ubuntu acceptance host')
    if not args.executable or not args.output:
        parser.error('--executable and --output are required')
    if args.blocks < 1 or args.script_turns < 1 or args.max_decisions < 1:
        parser.error('blocks, script-turns and max-decisions must be positive')
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    artifacts = freeze_artifacts(dict(native_executable=args.executable,
        lite_rules=Path(args.rules_dir) / 'rules.json', astra=ROOT / 'data/opponents/gpt6astra.zip'))
    workloads = []
    for fmt in args.formats:
        for cache in args.caches:
            for mode in args.modes:
                for density in args.densities:
                    for block in range(args.blocks):
                        for seat in args.seats or range(1, PLAYERS[fmt] + 1):
                            if not 1 <= seat <= PLAYERS[fmt]:
                                parser.error('seat outside format player range')
                            work = dict(format=fmt, cache=cache, mode=mode, density=density,
                                block=block, seat=seat, seed=190000 + block, map=f'arena{PLAYERS[fmt]}',
                                workers=1, inference='cpu', threads=1, turn_limit=args.turn_limit,
                                factions_rotation=block % 6)
                            work['id'] = _digest(work)
                            workloads.append(work)
    manifest = dict(version=1, artifacts=artifacts, workloads=workloads,
        required_artifacts=['native_executable', 'lite_rules', 'astra'],
        minimum_complete_rotation_blocks=30, required_speedup=5, required_cpu_ratio=5,
        resource_memory_ratio_target=1.3,
        cache_contract='process cold / resident hot; OS page cache unchanged',
        measurement='Linux /proc smaps_rollup + getrusage; one game worker; coordinator included',
        max_decisions=args.max_decisions, script_turns=args.script_turns)
    manifest['manifest_id'] = _digest(manifest)
    write_json(output / 'manifest.json', manifest)
    raw = []
    with (output / 'raw.jsonl').open('x') as stream:
        for index, work in enumerate(workloads):
            for engine in (('native', 'lite') if index % 2 == 0 else ('lite', 'native')):
                print(f'{len(raw)+1}/{len(workloads)*2} {engine} {work["format"]} {work["cache"]} {work["mode"]} {work["density"]} block={work["block"]} seat={work["seat"]}', flush=True)
                row = measure(engine, work, executable=args.executable, rules_dir=args.rules_dir,
                    timeout=args.timeout, max_decisions=args.max_decisions, script_turns=args.script_turns)
                row.update(engine=engine, workload_id=work['id'], manifest_id=manifest['manifest_id'])
                stream.write(json.dumps(row, allow_nan=False) + '\n')
                stream.flush()
                raw.append(row)
    write_json(output / 'observed.json', observed_report(raw, manifest))
    write_json(output / 'acceptance.json', benchmark_report(raw, manifest))


if __name__ == '__main__':
    main()
