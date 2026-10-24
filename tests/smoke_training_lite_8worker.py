"""T4: minimal real training chain under the global 8-worker pool.

Restricted acceptance harness, separate from the three-worker
``tests/smoke_training_revision_lite.py``. It keeps the real lite collection ->
BC -> DAgger/truncated-bootstrap -> PPO -> checkpoint path and adds the shared
scheduler with three concurrently running trainers:

* one fresh isolated run directory with a frozen manifest,
* three spawned trainer processes plus one parent-side broker(max_workers=8),
* three real Astra teacher games per format (nine games, <=10 turns each, at
  least one native training map per format, both train and validation families),
* one real BC update batch plus ``last_bc.pt`` reload per format,
* one lite student rollout per format with DAgger queries and truncation
  bootstraps, one finite PPO update plus ``last_ppo.pt`` reload,
* 8-worker peak, sampling/update overlap, exit codes, peak PSS, available
  memory, swap growth and residual processes recorded in ``summary.json``.

The formal 300/600/400 configuration is never read or written, ``state.effective``
is never set and no gate result is claimed. ``--plan-only`` runs every game-free
check (config validation, output-dir creation, seed/map/partition selection,
memory sampler) and writes ``t4_plan.json`` next to the other acceptance
evidence; it never spawns a trainer or a game.

Run:  python tests/smoke_training_lite_8worker.py --plan-only
      python tests/smoke_training_lite_8worker.py [--wesnoth EXE] [--output NAME]
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import os
import platform
import shutil
import sys
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FORMATS = ('duel', 'ffa4', 'team2v2')
PLAYERS = dict(duel=2, ffa4=4, team2v2=4)
TEAM2V2 = [1, 2, 1, 2]
WORKERS = 8
TEACHER_GAMES = 3
TEACHER_TURNS = 10
ROLLOUT_TURNS = 2
SEED_LIMIT = 50
TEACHER_SECONDS = 900.
ROLLOUT_SECONDS = 600.
EVIDENCE = ROOT / 'verification/pretrain_acceptance_20261022'
GIB = 1024 ** 3
MIB = 1024 ** 2
PEAK_PSS_LIMIT = 12 * GIB
AVAILABLE_FLOOR = 1 * GIB
SWAP_GROWTH_LIMIT = 256 * MIB
NATIVE_MAPS = frozenset({
    'the_freelands', 'weldyn_channel', 'sablestone_delta', 'hamlets',
    'caves_of_the_basilisk', 'ruined_passage', 'clash', 'isars_cross',
    'loris_river', 'morituri'})


def append_jsonl(path, record):
    """Append one complete line; O_APPEND keeps three trainer writers atomic."""
    line = (json.dumps(record, sort_keys=True, default=str) + '\n').encode('utf-8')
    handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(handle, line)
    finally:
        os.close(handle)


def read_jsonl(path):
    if not Path(path).is_file():
        return []
    rows = []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def wait_for_directory(source, names, timeout, label):
    """Wait for one marker file per name; a timeout names what never arrived."""
    deadline = time.time() + timeout
    while True:
        present = {name for name in names if (Path(source) / name).is_file()}
        if present == set(names):
            return
        if time.time() > deadline:
            missing = sorted(set(names) - present)
            raise TimeoutError(f'{label}: missing {missing} after {timeout:.0f}s')
        time.sleep(.05)


def lite_config():
    """Validation config for the restricted run; formal corpus stays untouched."""
    from learning.experiment import default_config, validate_config
    formal = default_config('cpu')
    config = dict(formal)
    config.update(workers=WORKERS,
                  bc_games={fmt: TEACHER_GAMES for fmt in FORMATS},
                  native_bc_games={fmt: 0 for fmt in FORMATS},
                  bc_batch_games=TEACHER_GAMES, bc_records=256,
                  bc_validation_records=128, epochs=1, minibatch=8,
                  validation_interval=1000)
    validate_config(config)
    if config['engine'] != 'lite' or config['evaluation_engine'] != 'lite':
        raise ValueError('the restricted harness requires the lite engine')
    if config['workers'] != WORKERS:
        raise ValueError('the restricted harness requires the 8-worker pool')
    return dict(config=config, formal=formal)


def config_negative_cases(config):
    """Rejections that prove the bound configuration is still validated."""
    cases = [
        ('workers above pool limit', dict(workers=17)),
        ('zero workers', dict(workers=0)),
        ('rollout games not a full rotation', dict(rollout_games=6)),
        ('formal evaluation below thirty blocks', dict(final_blocks=29)),
        ('bc batch of zero games', dict(bc_batch_games=0)),
        ('native anchor beyond bc corpus', dict(native_bc_games={fmt: 99 for fmt in FORMATS})),
        ('zero epochs', dict(epochs=0)),
        ('unknown reward mode', dict(reward_mode='learned')),
    ]
    from learning.experiment import validate_config
    results = []
    for name, patch in cases:
        try:
            validate_config({**config, **patch})
        except ValueError:
            results.append(dict(name=name, rejected=True, error=None))
        except Exception as error:  # wrong failure type is still a failure
            results.append(dict(name=name, rejected=False, error=f'{type(error).__name__}: {error}'))
        else:
            results.append(dict(name=name, rejected=False, error='validate_config accepted the patch'))
    return results


def teacher_stage_jobs(directory, fmt, teachers, seed, support, wesnoth, deadline):
    """Three teacher games for one format on a frozen shared schedule."""
    from learning.schedule import teacher_jobs
    jobs = teacher_jobs(directory, teachers, list(teachers), support, batch_index=0,
                        seed=seed, deadline=deadline, wesnoth=wesnoth,
                        formats=[fmt], count=TEACHER_GAMES,
                        index_stride=TEACHER_GAMES)
    for job in jobs:
        job.setdefault('format', fmt)
        # decorate() forces 60 turns on train jobs; the restricted run is capped.
        job['max_turns'] = TEACHER_TURNS
    return jobs


def rollout_stage_jobs(directory, fmt, policy, current, teachers, support, version,
                       seed, wesnoth, deadline):
    """One lite student rollout with DAgger queries and truncation bootstraps."""
    from learning.schedule import rollout_jobs
    jobs = rollout_jobs(directory, policy, [current], list(teachers), support, version,
                        batch_index=0, seed=seed, deadline=deadline, wesnoth=wesnoth,
                        games_per_format=1, current=current, formats=[fmt])
    for job in jobs:
        job.setdefault('format', fmt)
        job['max_turns'] = ROLLOUT_TURNS
        job.setdefault('learning', {})['dagger_teacher'] = teachers[0]
    return jobs


def describe_jobs(jobs):
    from learning.data import split
    return [dict(id=job['id'], map=job['meta']['map'],
                 map_partition=job['meta'].get('map_partition'),
                 partition=split(job['game_family']), turns=job['max_turns'],
                 native=job['meta']['map'] in NATIVE_MAPS) for job in jobs]


def resolve_plan(directory, teachers, support='support', wesnoth=None,
                 seed_limit=SEED_LIMIT):
    """Search seeds so each format covers train+validation and train-only PPO."""
    deadline = time.time() + 3600
    plan = dict(teacher={}, rollout={}, seed_limit=seed_limit)
    for fmt in FORMATS:
        chosen = None
        for seed in range(seed_limit):
            jobs = teacher_stage_jobs(directory / fmt, fmt, teachers, seed, support,
                                      wesnoth, deadline)
            described = describe_jobs(jobs)
            partitions = {entry['partition'] for entry in described}
            native = [entry for entry in described
                      if entry['native'] and entry['map_partition'] == 'train']
            if partitions == {'train', 'validation'} and native:
                chosen = dict(seed=seed, seeds_examined=seed + 1, jobs=described,
                              native_maps=[entry['map'] for entry in native])
                break
        if chosen is None:
            raise RuntimeError(f'{fmt}: no seed within {seed_limit} covers train and'
                               ' validation with a native training map')
        plan['teacher'][fmt] = chosen
        chosen = None
        for seed in range(seed_limit):
            jobs = rollout_stage_jobs(directory / fmt, fmt,
                                      'policy/LitePolicy', 'policy/LitePolicy',
                                      teachers, support, 'v0', seed, wesnoth, deadline)
            described = describe_jobs(jobs)
            if [entry['partition'] for entry in described] == ['train']:
                chosen = dict(seed=seed, seeds_examined=seed + 1, jobs=described,
                              version='v0')
                break
        if chosen is None:
            raise RuntimeError(f'{fmt}: no seed within {seed_limit} gives a train'
                               ' rollout family')
        plan['rollout'][fmt] = chosen
    plan['job_ids'] = [entry['id'] for fmt in FORMATS
                       for entry in plan['teacher'][fmt]['jobs']]
    plan['rollout_ids'] = [entry['id'] for fmt in FORMATS
                           for entry in plan['rollout'][fmt]['jobs']]
    return plan


def plan_lines(plan):
    """One readable line per seed decision plus the nine teacher job IDs."""
    lines = []
    for fmt in FORMATS:
        teacher = plan['teacher'][fmt]
        lines.append(
            f"teacher {fmt}: seed={teacher['seed']}"
            f" (searched {teacher['seeds_examined']})"
            f" maps={','.join(entry['map'] for entry in teacher['jobs'])}"
            f" partitions={','.join(entry['partition'] for entry in teacher['jobs'])}"
            f" turns={teacher['jobs'][0]['turns']}"
            f" native={','.join(teacher['native_maps'])}")
        rollout = plan['rollout'][fmt]
        lines.append(
            f"rollout {fmt}: seed={rollout['seed']}"
            f" (searched {rollout['seeds_examined']})"
            f" maps={','.join(entry['map'] for entry in rollout['jobs'])}"
            f" partitions={','.join(entry['partition'] for entry in rollout['jobs'])}"
            f" turns={rollout['jobs'][0]['turns']}")
    lines.append('teacher ids: ' + ','.join(plan['job_ids']))
    lines.append('rollout ids: ' + ','.join(plan['rollout_ids']))
    return lines


class MemorySampler:
    """Sample the validated process tree; degrade to inconclusive off Linux."""

    def __init__(self, interval=.2, pid=None):
        self.interval = max(.05, interval)
        self.pid = int(pid or os.getpid())
        self.samples = []
        self.supported = (os.name == 'posix'
                          and Path('/proc/meminfo').is_file()
                          and Path(f'/proc/{self.pid}/smaps_rollup').exists())
        self._stop = threading.Event()
        self._thread = None

    def snapshot(self):
        if not self.supported:
            return None
        from learning.benchmark_runner import tree_memory
        rss, pss = tree_memory(self.pid)
        values = {}
        for line in Path('/proc/meminfo').read_text(encoding='utf-8').splitlines():
            key, _, value = line.partition(':')
            if key in ('MemAvailable', 'SwapTotal', 'SwapFree'):
                values[key] = int(value.split()[0]) * 1024
        return dict(time=time.time(), rss=rss, pss=pss,
                    mem_available=values.get('MemAvailable'),
                    swap_total=values.get('SwapTotal'),
                    swap_free=values.get('SwapFree'))

    def _loop(self):
        while not self._stop.wait(self.interval):
            sample = self.snapshot()
            if sample is not None:
                self.samples.append(sample)

    def start(self):
        if self.supported:
            self._thread = threading.Thread(target=self._loop, name='memory-sampler',
                                            daemon=True)
            self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        sample = self.snapshot()
        if sample is not None:
            self.samples.append(sample)
        return self.report()

    def report(self):
        if not self.supported:
            return dict(status='inconclusive', samples=0, platform=sys.platform,
                        reason='POSIX /proc tree accounting unavailable on this platform')
        pss = [sample['pss'] for sample in self.samples if sample['pss'] is not None]
        available = [sample['mem_available'] for sample in self.samples
                     if sample['mem_available'] is not None]
        swap_used = [sample['swap_total'] - sample['swap_free']
                     for sample in self.samples
                     if sample['swap_total'] is not None and sample['swap_free'] is not None]
        if not self.samples:
            return dict(status='inconclusive', samples=0, platform=sys.platform,
                        reason='no memory samples were collected')
        report = dict(platform=sys.platform, samples=len(self.samples),
                      peak_rss=max(sample['rss'] for sample in self.samples),
                      peak_pss=max(pss) if pss else None,
                      min_available=min(available) if available else None,
                      swap_used_start=swap_used[0] if swap_used else None,
                      swap_used_end=swap_used[-1] if swap_used else None,
                      limits=dict(peak_pss=PEAK_PSS_LIMIT, min_available=AVAILABLE_FLOOR,
                                  swap_growth=SWAP_GROWTH_LIMIT))
        if report['peak_pss'] is None or report['min_available'] is None or not swap_used:
            report.update(status='inconclusive', checks={},
                          reason='process PSS, MemAvailable or swap counters were unreadable')
            return report
        growth = max(0, report['swap_used_end'] - report['swap_used_start'])
        report['swap_growth'] = growth
        report['checks'] = dict(peak_pss_within_limit=report['peak_pss'] <= PEAK_PSS_LIMIT,
                                available_above_floor=report['min_available'] > AVAILABLE_FLOOR,
                                swap_growth_bounded=growth <= SWAP_GROWTH_LIMIT)
        report['status'] = 'measured' if all(report['checks'].values()) else 'failed'
        return report


def memory_self_test():
    sampler = MemorySampler(interval=.05).start()
    time.sleep(.3)
    report = sampler.stop()
    keys = {'status', 'samples', 'platform'}
    if not keys <= set(report):
        raise RuntimeError(f'memory sampler report is incomplete: {sorted(report)}')
    if sampler.supported:
        if report['samples'] < 2:
            raise RuntimeError(f'memory sampler collected {report["samples"]} samples')
        if not report.get('peak_rss'):
            raise RuntimeError('memory sampler reported no resident bytes')
    return report


def residual_processes(marker):
    """Live processes still holding the run directory in their command line."""
    if os.name != 'posix' or not Path('/proc').is_dir():
        return None
    found = []
    for entry in Path('/proc').iterdir():
        if not entry.name.isdigit() or int(entry.name) == os.getpid():
            continue
        try:
            command = (entry / 'cmdline').read_bytes().decode('utf-8', 'replace')
        except (FileNotFoundError, ProcessLookupError, PermissionError):
            continue
        if marker in command:
            found.append(dict(pid=int(entry.name),
                              command=' '.join(command.split('\x00')).strip()[:400]))
    return found


def resolve_wesnoth(value=None):
    from learning.common import ROOT as repository
    import native
    candidates = [value, os.environ.get('WESNOTH_EXE'),
                  str(repository / '.runtime/install/bin/wesnoth')]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return native.find_wesnoth(str(candidate))
    return native.find_wesnoth(None)


def lite_trainer(directory, fmt, manifest, clock, requests, replies, plan, ready,
                 pending, go):
    """One real format trainer: teacher batch, BC update, rollout, PPO update."""
    from learning.coordinator import limit_memory
    from learning.data import read_shards, split
    from learning.experiment import FormatExperiment
    from learning.export import load_model

    directory = Path(directory)
    timeline = directory.parent / 'timeline.jsonl'

    def event(name, **payload):
        append_jsonl(timeline, dict(time=time.time(), format=fmt, event=name, **payload))

    def collect(jobs, log):
        # The marker proves the batch is queued before the parent starts draining.
        stage = len(list(Path(pending).glob(f'{fmt}-*.json'))) + 1
        append_jsonl(Path(pending) / f'{fmt}-{stage}.json',
                     dict(format=fmt, stage=stage, queued=time.time(),
                          ids=[job['id'] for job in jobs], log=str(log)))
        requests.put((fmt, jobs, str(log)))
        reply = replies.get()
        if isinstance(reply, dict) and reply.get('error'):
            raise RuntimeError(f'broker rejected the {fmt} batch: {reply["error"]}')
        return reply['results'] if isinstance(reply, dict) else reply

    def finished(results, jobs, stage):
        by_id = {result['id']: result for result in results}
        missing = [job['id'] for job in jobs if job['id'] not in by_id]
        if missing:
            raise RuntimeError(f'{fmt}: {stage} returned no result for {missing}')
        broken = []
        for job in jobs:
            result = by_id[job['id']]
            faults = (result.get('result') or {}).get('faults') or []
            eligible = result.get('training_eligible')
            if result.get('status') != 'complete' or faults or eligible is False:
                broken.append(dict(id=job['id'], status=result.get('status'),
                                   faults=faults, eligible=eligible,
                                   error=result.get('error')))
        if broken:
            raise RuntimeError(f'{fmt}: {stage} jobs are not clean: {broken}')
        return by_id

    def describe(results, jobs):
        entries = []
        for job in jobs:
            result = results[job['id']]
            outcome = result.get('result') or {}
            entries.append(dict(id=job['id'], map=job['meta']['map'],
                                map_partition=job['meta'].get('map_partition'),
                                native=job['meta']['map'] in NATIVE_MAPS,
                                partition=split(job['game_family']),
                                turn_cap=job['max_turns'],
                                turns=outcome.get('turns'),
                                reason=outcome.get('reason'),
                                truncated=outcome.get('truncated'),
                                winner=outcome.get('winner'),
                                coverage=(result.get('coverage') or {}).get('matched')))
        return entries

    record = dict(format=fmt, pid=os.getpid(), status='running', checks={},
                  teacher={}, bc={}, ppo={}, update_windows=[], timeline=str(timeline),
                  engine=None, effective=None, errors=[])
    try:
        limit_memory(manifest['config']['trainer_memory_gb'])
        event('trainer_start')
        experiment = FormatExperiment(directory, fmt, manifest, clock, collect)
        record['engine'] = experiment.config['engine']
        record['hardware'] = json.loads((directory / 'hardware.json').read_text(encoding='utf-8'))
        Path(ready).mkdir(parents=True, exist_ok=True)
        with open(Path(ready) / f'{fmt}.json', 'w', encoding='utf-8') as handle:
            json.dump(dict(format=fmt, pid=os.getpid()), handle)
        wait_for_directory(Path(go).parent, [Path(go).name], TEACHER_SECONDS,
                           f'{fmt}: parent go signal')
        event('barrier_released')

        teachers = [entry['path'] for entry in manifest['opponents']]
        support = experiment.support
        seed = plan['teacher'][fmt]['seed']
        jobs = teacher_stage_jobs(experiment.directory, fmt, teachers, seed, support,
                                  experiment.exe,
                                  min(clock['update_deadline'],
                                      time.time() + TEACHER_SECONDS))
        if [split(job['game_family']) for job in jobs] != \
                [entry['partition'] for entry in plan['teacher'][fmt]['jobs']]:
            raise RuntimeError(f'{fmt}: teacher families differ from the frozen plan')
        if not any(job['meta']['map'] in NATIVE_MAPS
                   and job['meta']['map_partition'] == 'train' for job in jobs):
            raise RuntimeError(f'{fmt}: no native training map in the teacher batch')
        if len(jobs) != TEACHER_GAMES or any(job['max_turns'] != TEACHER_TURNS
                                             for job in jobs):
            raise RuntimeError(f'{fmt}: teacher batch is not {TEACHER_GAMES} x <='
                               f' {TEACHER_TURNS} turns')
        event('schedule_frozen', stage='teacher', ids=[job['id'] for job in jobs])
        jobs, results = experiment.execute(jobs, 'teacher-batch-000000')
        teacher_results = finished(results, jobs, 'teacher')
        record['teacher'] = dict(seed=seed, games=describe(teacher_results, jobs),
                                 ids=[job['id'] for job in jobs])
        shards = sorted({job['shard'] for job in jobs
                         if teacher_results[job['id']].get('status') == 'complete'})
        if len(shards) != TEACHER_GAMES:
            raise RuntimeError(f'{fmt}: expected {TEACHER_GAMES} teacher shards,'
                               f' found {len(shards)}')
        experiment.state['teacher_shards'] = shards
        experiment.state['stage'] = 'training'
        experiment.state['counters']['collection_batches'] += 1
        experiment.save()

        # Read the same partitions finish_train() consumes and record provenance.
        train_rows = read_shards(shards, partition='train', limit=256, seed=experiment.config['seed'],
                                 format_name=fmt)
        validation_rows = read_shards(shards, partition='validation', limit=128,
                                      seed=experiment.config['seed'], format_name=fmt)
        if not train_rows:
            raise RuntimeError(f'{fmt}: training partition is empty')
        if not validation_rows:
            raise RuntimeError(f'{fmt}: validation partition is empty')
        faulty = [row.get('faults') for row in train_rows + validation_rows
                  if row.get('faults')]
        if faulty:
            raise RuntimeError(f'{fmt}: BC corpus holds {len(faulty)} faulty samples')
        provenance = sorted({(str(row.get('source')), str(row.get('engine_id')))
                             for row in train_rows + validation_rows})
        if [source for source, _ in provenance] != ['astra']:
            raise RuntimeError(f'{fmt}: unexpected teacher provenance {provenance}')
        if any(not engine.startswith('lite') for _, engine in provenance):
            raise RuntimeError(f'{fmt}: teacher rows are not lite-engine {provenance}')
        rewards = {json.dumps(row.get('reward_config'), sort_keys=True)
                   for row in train_rows + validation_rows}
        if len(rewards) != 1:
            raise RuntimeError(f'{fmt}: teacher rows mix {len(rewards)} reward configs')
        missing = [key for key in ('reward_version', 'reward_formula_id', 'rules_version',
                                   'rng_version', 'combat_version', 'candidate_version')
                   if any(row.get(key) is None
                          for row in (train_rows[0], validation_rows[0]))]
        if missing:
            raise RuntimeError(f'{fmt}: teacher rows lack provenance {missing}')
        record['bc'].update(train_rows=len(train_rows),
                            validation_rows=len(validation_rows),
                            train_families=len({row['game_family'] for row in train_rows}),
                            validation_families=len({row['game_family'] for row in validation_rows}),
                            provenance=[list(item) for item in provenance],
                            reward_configs=len(rewards),
                            corpus={fmt: len(train_rows) + len(validation_rows)})

        # One real BC update batch and its checkpoint.
        experiment.state['pending_train'] = dict(paths=[], method='bc',
                                                 cursor=dict(epoch=0, step=0),
                                                 reward_config=jobs[0]['reward_config'])
        experiment.save()
        started = time.time()
        event('update_start', method='bc')
        ok = experiment.finish_train()
        event('update_end', method='bc', ok=bool(ok),
              updates=(experiment.state['history'][-1] or {}).get('updates'))
        record['update_windows'].append(dict(method='bc', start=started, end=time.time()))
        if not ok:
            raise RuntimeError(f'{fmt}: BC update was interrupted')
        metrics = dict(experiment.state['history'][-1])
        if not metrics.get('updates'):
            raise RuntimeError(f'{fmt}: BC update counted no optimizer steps')
        if metrics.get('interrupted'):
            raise RuntimeError(f'{fmt}: BC update reported an interruption')
        bc_path = experiment.directory / 'last_bc.pt'
        if not bc_path.is_file():
            raise RuntimeError(f'{fmt}: BC checkpoint missing')
        _, bc_state = load_model(bc_path, fmt)
        if int(bc_state.get('runner', {}).get('version', 0)) != 1:
            raise RuntimeError(f'{fmt}: BC checkpoint does not carry version 1')
        record['bc'].update(updates=metrics.get('updates'), loss=metrics.get('loss'),
                            interrupted=metrics.get('interrupted'),
                            version=experiment.state['version'],
                            checkpoint=str(bc_path), reloaded=True,
                            checkpoint_sha256=hashlib.sha256(
                                bc_path.read_bytes()).hexdigest())

        # One lite student rollout with DAgger and truncated-bootstrap data.
        version = experiment.state['version']
        sample = experiment.ensure_export(experiment.model, f'v{version:06}-sample',
                                          f'Rollout{version:06}', mode='sample',
                                          version=f'v{version}')
        current = experiment.ensure_export(experiment.model, f'v{version:06}-greedy',
                                           f'Greedy{version:06}', mode='greedy',
                                           version=f'v{version}')
        rollout_seed = plan['rollout'][fmt]['seed']
        jobs = rollout_stage_jobs(experiment.directory, fmt, sample, current, teachers,
                                  support, f'v{version}', rollout_seed, experiment.exe,
                                  min(clock['update_deadline'],
                                      time.time() + ROLLOUT_SECONDS))
        if [split(job['game_family']) for job in jobs] != \
                [entry['partition'] for entry in plan['rollout'][fmt]['jobs']]:
            raise RuntimeError(f'{fmt}: rollout family differs from the frozen plan')
        event('schedule_frozen', stage='ppo', ids=[job['id'] for job in jobs])
        jobs, results = experiment.execute(jobs, 'ppo-batch-000000')
        rollout_results = finished(results, jobs, 'rollout')
        record['ppo'].update(seed=rollout_seed, games=describe(rollout_results, jobs),
                             ids=[job['id'] for job in jobs])
        paths = [job['shard'] for job in jobs]
        rows = read_shards(paths, format_name=fmt)
        if not rows:
            raise RuntimeError(f'{fmt}: rollout produced no policy samples')
        policy_rows = [row for row in rows if row.get('source') == 'policy']
        if len(policy_rows) != len(rows):
            raise RuntimeError(f'{fmt}: rollout rows are not all on-policy')
        faults = [row.get('faults') for row in rows if row.get('faults')]
        if faults:
            raise RuntimeError(f'{fmt}: rollout corpus holds {len(faults)} faulty samples')
        bootstraps = [row for row in rows if row.get('bootstrap_value') is not None]
        if not bootstraps:
            raise RuntimeError(f'{fmt}: rollout produced no truncation bootstraps')
        dagger = []
        for path in paths:
            dagger_path = Path(str(path).replace('.jsonl.gz', '.dagger.jsonl.gz'))
            if dagger_path.is_file():
                dagger.append(str(dagger_path))
        if not dagger:
            raise RuntimeError(f'{fmt}: rollout produced no DAgger shards')
        dagger_rows = read_shards(dagger, format_name=fmt)
        from learning.rowpack import unpack_line
        queries = 0
        for path in dagger:
            with gzip.open(path, 'rt', encoding='utf-8') as stream:
                queries += sum(bool(unpack_line(line.rstrip(), plain=True)[0].get('query_only'))
                               for line in stream if line.strip())
        if not queries:
            raise RuntimeError(f'{fmt}: DAgger shards carry no teacher queries')
        if not dagger_rows:
            raise RuntimeError(f'{fmt}: DAgger shards carry no training rows')
        versions = {row.get('version') for row in rows}
        if len(versions) != 1:
            raise RuntimeError(f'{fmt}: rollout rows mix policy versions {versions}')
        record['ppo'].update(policy_rows=len(policy_rows), bootstrap_rows=len(bootstraps),
                             dagger_rows=len(dagger_rows), dagger_queries=queries,
                             version=versions.pop(), dagger_shards=dagger)

        experiment.state['dagger_shards'] = sorted(
            set(experiment.state.get('dagger_shards', [])) | set(dagger))
        experiment.state['pending_train'] = dict(paths=paths, method='ppo',
                                                 cursor=dict(epoch=0, step=0),
                                                 reward_config=jobs[0]['reward_config'])
        experiment.save()
        started = time.time()
        event('update_start', method='ppo')
        ok = experiment.finish_train()
        event('update_end', method='ppo', ok=bool(ok),
              updates=(experiment.state['history'][-1] or {}).get('updates'))
        record['update_windows'].append(dict(method='ppo', start=started, end=time.time()))
        if not ok:
            raise RuntimeError(f'{fmt}: PPO update was interrupted')
        metrics = dict(experiment.state['history'][-1])
        if not metrics.get('updates'):
            raise RuntimeError(f'{fmt}: PPO update counted no optimizer steps')
        if metrics.get('interrupted'):
            raise RuntimeError(f'{fmt}: PPO update reported an interruption')
        ppo_path = experiment.directory / 'last_ppo.pt'
        if not ppo_path.is_file():
            raise RuntimeError(f'{fmt}: PPO checkpoint missing')
        _, ppo_state = load_model(ppo_path, fmt)
        if int(ppo_state.get('runner', {}).get('version', 0)) != version + 1:
            raise RuntimeError(f'{fmt}: PPO checkpoint does not carry version {version + 1}')
        record['ppo'].update(updates=metrics.get('updates'), loss=metrics.get('loss'),
                             interrupted=metrics.get('interrupted'),
                             version=experiment.state['version'],
                             checkpoint=str(ppo_path), reloaded=True,
                             checkpoint_sha256=hashlib.sha256(
                                 ppo_path.read_bytes()).hexdigest())

        record['state'] = dict(version=experiment.state['version'],
                               batch=experiment.state['batch'],
                               stage=experiment.state['stage'],
                               teacher_shards=len(experiment.state['teacher_shards']),
                               dagger_shards=len(experiment.state['dagger_shards']),
                               effective=experiment.state['effective'],
                               counters=dict(experiment.state['counters']))
        if experiment.state['effective'] is not False:
            raise RuntimeError(f'{fmt}: the restricted harness must not set effective')
        if experiment.state['version'] != 2:
            raise RuntimeError(f'{fmt}: expected version 2 after BC and PPO')
        record['checks'] = dict(teacher_games=len(record['teacher']['ids']) == TEACHER_GAMES,
                                bc_version=record['bc']['version'] == 1,
                                ppo_updates=bool(record['ppo']['updates']),
                                bootstraps=bool(record['ppo']['bootstrap_rows']),
                                dagger=bool(record['ppo']['dagger_queries']),
                                reloads=bool(record['bc']['reloaded'] and record['ppo']['reloaded']),
                                effective=experiment.state['effective'] is False,
                                version=experiment.state['version'] == 2)
        record['status'] = 'complete'
        event('trainer_done', version=experiment.state['version'])
    except BaseException as error:
        record['status'] = 'failed'
        record['errors'].append(f'{type(error).__name__}: {error}')
        record['traceback'] = traceback.format_exc()
        try:
            (directory / 'lite_trainer_error.log').write_text(record['traceback'],
                                                              encoding='utf-8')
        except OSError:
            pass
        try:
            append_jsonl(timeline, dict(time=time.time(), format=fmt,
                                        event='trainer_failed', error=str(error)))
        except OSError:
            pass
        raise
    finally:
        with open(directory / 'trainer_result.json', 'w', encoding='utf-8') as handle:
            json.dump(record, handle, indent=2, default=str)
    return record


def scheduler_intervals(rows):
    """Start/finish intervals per scheduled game plus the observed active peak."""
    starts = {}
    intervals = []
    unfinished = []
    for row in rows:
        key = (row.get('format'), row.get('id'))
        if row.get('event') == 'start':
            starts[key] = row.get('time')
        elif row.get('event') == 'finish':
            if key in starts:
                intervals.append(dict(format=row.get('format'), id=row.get('id'),
                                      start=starts.pop(key), end=row.get('time'),
                                      active=row.get('active')))
            else:
                unfinished.append(row)
    pending = [dict(format=fmt, id=ident) for fmt, ident in starts]
    return intervals, pending, unfinished


def update_overlap(intervals, windows):
    """Sampling intervals that ran while another format's trainer was updating."""
    hits = []
    for interval in intervals:
        for window in windows:
            if interval['format'] == window['format']:
                continue
            if interval['start'] < window['end'] and window['start'] < interval['end']:
                hits.append(dict(game=f"{interval['format']}/{interval['id']}",
                                 update=f"{window['format']}/{window['method']}"))
    return hits


def cross_format_overlap(intervals):
    hits = []
    for outer in intervals:
        for inner in intervals:
            if outer['format'] == inner['format']:
                continue
            if outer['start'] < inner['end'] and inner['start'] < outer['end']:
                hits.append(sorted({outer['format'], inner['format']}))
    return hits


def plan_only(args):
    """Every game-free check; never spawns a trainer, pool or rollout."""
    from learning.common import write_json
    started = time.time()
    checks = []

    def check(name, function):
        try:
            detail = function()
        except Exception as error:
            checks.append(dict(name=name, passed=False,
                               error=f'{type(error).__name__}: {error}',
                               traceback=traceback.format_exc()))
            return None
        checks.append(dict(name=name, passed=True, detail=detail))
        return detail

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    probe = EVIDENCE / f't4-plan-probe-{os.getpid()}-{int(started)}'

    def config_check():
        built = lite_config()
        formal = built['formal']
        config = built['config']
        if formal['bc_games'] != dict(duel=300, ffa4=600, team2v2=400):
            raise RuntimeError(f'formal corpus of the shared defaults changed: {formal["bc_games"]}')
        if config['bc_games'] == formal['bc_games']:
            raise RuntimeError('the restricted config reuses the formal corpus')
        return dict(workers=config['workers'], engine=config['engine'],
                    bc_games=config['bc_games'], native_bc_games=config['native_bc_games'],
                    bc_batch_games=config['bc_batch_games'], bc_records=config['bc_records'],
                    bc_validation_records=config['bc_validation_records'],
                    epochs=config['epochs'], minibatch=config['minibatch'],
                    validation_interval=config['validation_interval'],
                    final_blocks=config['final_blocks'], hours=config['hours'])

    def negative_check():
        outcomes = config_negative_cases(lite_config()['config'])
        rejected = [entry for entry in outcomes if entry['rejected']]
        if len(rejected) != len(outcomes):
            raise RuntimeError(f'config validation accepted: '
                               f'{[entry for entry in outcomes if not entry["rejected"]]}')
        return outcomes

    def output_dir_check():
        probe.mkdir(exist_ok=False)
        (probe / 'probe.json').write_text('{"ok": true}', encoding='utf-8')
        reopened = probe / 'probe.json'
        if json.loads(reopened.read_text(encoding='utf-8')) != {'ok': True}:
            raise RuntimeError('probe file did not round-trip')
        shutil.rmtree(probe)
        if probe.exists():
            raise RuntimeError('probe directory survived removal')
        return dict(created=str(probe), exclusive=True, removed=True)

    def plan_check():
        teachers = [str(ROOT / 'data/opponents/gpt6astra.zip')]
        if not Path(teachers[0]).is_file():
            raise RuntimeError(f'missing frozen teacher {teachers[0]}')
        plan = resolve_plan(ROOT / 'tmp/t4_plan_probe', teachers)
        for fmt in FORMATS:
            teacher = plan['teacher'][fmt]
            rollout = plan['rollout'][fmt]
            partitions = {entry['partition'] for entry in teacher['jobs']}
            if partitions != {'train', 'validation'}:
                raise RuntimeError(f'{fmt}: teacher partitions {sorted(partitions)}')
            if not teacher['native_maps']:
                raise RuntimeError(f'{fmt}: no native training map')
            if len(teacher['jobs']) != TEACHER_GAMES:
                raise RuntimeError(f'{fmt}: {len(teacher["jobs"])} teacher games')
            if any(entry['turns'] != TEACHER_TURNS for entry in teacher['jobs']):
                raise RuntimeError(f'{fmt}: teacher turns are not capped')
            if [entry['partition'] for entry in rollout['jobs']] != ['train']:
                raise RuntimeError(f'{fmt}: rollout family is not a train family')
            if rollout['jobs'][0]['turns'] != ROLLOUT_TURNS:
                raise RuntimeError(f'{fmt}: rollout turns are not capped')
            if len({entry['id'] for entry in teacher['jobs']}) != TEACHER_GAMES:
                raise RuntimeError(f'{fmt}: duplicate teacher ids')
        ids = plan['job_ids'] + plan['rollout_ids']
        if len(ids) != len(set(ids)):
            raise RuntimeError('duplicate job ids across formats')
        if len(plan['job_ids']) != TEACHER_GAMES * len(FORMATS):
            raise RuntimeError(f'{len(plan["job_ids"])} teacher jobs scheduled, expected 9')
        expected = {f'teacher-{index:05}-{fmt}-t0'
                    for fmt in FORMATS for index in range(TEACHER_GAMES)}
        if set(plan['job_ids']) != expected:
            raise RuntimeError(f'teacher ids differ: {sorted(set(plan["job_ids"]) ^ expected)}')
        return plan

    def memory_check():
        return memory_self_test()

    config = check('config_validation', config_check)
    check('config_rejects_invalid', negative_check)
    check('output_directory', output_dir_check)
    plan = check('seed_and_map_plan', plan_check)
    check('memory_sampler', memory_check)

    if plan is not None:
        from learning.common import write_json as write
        write(EVIDENCE / 't4_plan.json',
              dict(mode='plan-only', generated=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                   host=platform.node(), platform=sys.platform, python=sys.version,
                   command=sys.argv, target_platform='requirement: Linux 8-worker run; '
                   'this file only records game-free planning evidence',
                   config=(config or {}), plan=plan, plan_lines=plan_lines(plan),
                   checks=checks, passed=all(entry['passed'] for entry in checks),
                   duration_s=time.time() - started))
    passed = all(entry['passed'] for entry in checks)
    for line in (plan_lines(plan) if plan else []):
        print(line)
    for entry in checks:
        status = 'ok' if entry['passed'] else 'FAILED'
        print(f'plan-only {status}: {entry["name"]}'
              + ('' if entry['passed'] else f' -> {entry["error"]}'))
    if not passed:
        for entry in checks:
            if not entry['passed']:
                print(entry.get('traceback', ''), file=sys.stderr)
        return 1
    print(f'plan-only evidence: {EVIDENCE / "t4_plan.json"}')
    return 0


def run(args):
    """One restricted real run: three trainers, one 8-worker pool, no run()/learn()."""
    import multiprocessing
    from learning.common import write_json
    from learning.coordinator import broker
    from learning.manifest import freeze

    checks = []

    def check(name, passed, **detail):
        checks.append(dict(name=name, passed=bool(passed), **detail))
        return bool(passed)

    started = time.time()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime('%Y%m%d_%H%M%S', time.gmtime())
    run_dir = EVIDENCE / (args.output or f't4_lite8_{stamp}')
    run_dir.mkdir(exist_ok=False)
    (run_dir / 'ready').mkdir()
    (run_dir / 'pending').mkdir()

    built = lite_config()
    config = built['config']
    check('config_validation', True, workers=config['workers'],
          bc_games=config['bc_games'], bc_batch_games=config['bc_batch_games'])

    wesnoth = resolve_wesnoth(args.wesnoth)
    manifest, teachers = freeze(run_dir, str(ROOT / 'data/opponents'), wesnoth, config)
    plan = resolve_plan(run_dir / 'plan', teachers, support='support',
                        wesnoth=manifest['baseline']['path'])
    write_json(run_dir / 'plan.json', plan)

    clock = dict(started=started,
                 deadline=started + config['hours'] * 3600.,
                 update_deadline=started + config['hours'] * 3600.)
    context = multiprocessing.get_context('spawn')
    requests = context.Queue()
    replies = {fmt: context.Queue() for fmt in FORMATS}
    processes = {}
    for fmt in FORMATS:
        processes[fmt] = context.Process(
            target=lite_trainer, name=f'trainer-{fmt}',
            args=(str(run_dir / fmt), fmt, manifest, clock, requests, replies[fmt],
                  plan, str(run_dir / 'ready'), str(run_dir / 'pending'),
                  str(run_dir / 'go')))
    for process in processes.values():
        process.start()
    sampler = MemorySampler()
    broker_error = None
    broker_result = {}
    try:
        wait_for_directory(run_dir / 'ready', [f'{fmt}.json' for fmt in FORMATS], 900,
                           'trainers ready')
        (run_dir / 'go').write_text('go\n', encoding='utf-8')
        wait_for_directory(run_dir / 'pending', [f'{fmt}-1.json' for fmt in FORMATS], 600,
                           'teacher batches queued')
        sampler.start()
        broker_result = broker(processes, requests, replies, config['workers'], run_dir)
    except BaseException as error:
        broker_error = f'{type(error).__name__}: {error}'
    finally:
        memory = sampler.stop()
        for process in processes.values():
            process.join(timeout=120)
        hung = [fmt for fmt, process in processes.items() if process.is_alive()]
        for fmt in hung:
            processes[fmt].terminate()
            processes[fmt].join(timeout=30)
        if hung:
            broker_error = (broker_error or '') + f' trainers had to be terminated: {hung}'

    exit_codes = {fmt: processes[fmt].exitcode for fmt in FORMATS}
    results = {}
    for fmt in FORMATS:
        path = run_dir / fmt / 'trainer_result.json'
        results[fmt] = (json.loads(path.read_text(encoding='utf-8'))
                        if path.is_file() else None)
    log_path = run_dir / 'trainer_exit.log'
    exit_log = log_path.read_text(encoding='utf-8') if log_path.is_file() else ''
    scheduler_rows = read_jsonl(run_dir / 'scheduler.jsonl')
    intervals, pending, unfinished = scheduler_intervals(scheduler_rows)
    windows = [dict(format=fmt, **window) for fmt, result in results.items()
               if result for window in result.get('update_windows', [])]
    overlaps = update_overlap(intervals, windows) if intervals and windows else []
    concurrent = cross_format_overlap(intervals)
    active_peak = max((int(row.get('active') or 0) for row in scheduler_rows), default=0)
    max_active = max((entry.get('active') or 0) for entry in intervals) if intervals else 0
    residual = residual_processes(str(run_dir))
    done = {fmt: bool(results[fmt]) and results[fmt].get('status') == 'complete'
            and not results[fmt].get('errors') for fmt in FORMATS}
    job_ids = {fmt: ((results[fmt] or {}).get('teacher', {}).get('ids', [])
                     + (results[fmt] or {}).get('ppo', {}).get('ids', [])) for fmt in FORMATS}
    scheduled = {row.get('id') for row in scheduler_rows if row.get('event') == 'start'}
    expected_jobs = set(plan['job_ids']) | set(plan['rollout_ids'])

    checks.extend([
        dict(name='broker_drained_queue', passed=broker_error is None,
             detail=dict(error=broker_error, result=broker_result)),
        dict(name='trainer_exit_codes', passed=all(code == 0 for code in exit_codes.values()),
             detail=exit_codes, log=exit_log[-2000:]),
        dict(name='trainer_results', passed=all(done.values()),
             detail={fmt: dict(status=(results[fmt] or {}).get('status'),
                               errors=(results[fmt] or {}).get('errors')) for fmt in FORMATS}),
        dict(name='nine_teacher_and_three_rollout_jobs',
             passed=scheduled == expected_jobs and len(scheduled) == 9 + 3,
             detail=dict(scheduled=len(scheduled), expected=sorted(expected_jobs),
                         missing=sorted(expected_jobs - scheduled),
                         unknown=sorted(scheduled - expected_jobs))),
        dict(name='pool_peak_games', passed=int(broker_result.get('peak_native_games', 0)) == WORKERS,
             detail=broker_result.get('peak_native_games')),
        dict(name='scheduler_active_peak',
             passed=active_peak == WORKERS and max_active <= WORKERS,
             detail=dict(active_peak=active_peak, max_interval_active=max_active)),
        dict(name='cross_format_concurrency', passed=bool(concurrent),
             detail=dict(pairs=len(concurrent), example=concurrent[:3])),
        dict(name='sampling_update_overlap_recorded', passed=True,
             detail=dict(gated=False, observed=bool(overlaps), hits=len(overlaps),
                         example=overlaps[:5])),
        dict(name='scheduler_closed', passed=not pending and not unfinished,
             detail=dict(pending=pending, unfinished=unfinished[:5])),
        dict(name='memory_accounting',
             passed=(memory.get('status') == 'measured'
                     or (memory.get('status') == 'inconclusive'
                         and os.name != 'posix')),
             detail=memory),
        dict(name='residual_processes',
             passed=(residual is None or not residual),
             detail=dict(inconclusive=residual is None, found=residual)),
    ])
    for fmt in FORMATS:
        result = results[fmt] or {}
        teacher = result.get('teacher') or {}
        bc = result.get('bc') or {}
        ppo = result.get('ppo') or {}
        state = result.get('state') or {}
        passed = (done[fmt] and teacher.get('games')
                  and len(teacher.get('games', [])) == TEACHER_GAMES
                  and any(game.get('native') and game.get('map_partition') == 'train'
                          for game in teacher.get('games', []))
                  and all(game.get('turn_cap') == TEACHER_TURNS
                          for game in teacher.get('games', []))
                  and bc.get('updates') and not bc.get('interrupted')
                  and bc.get('validation_rows') and bc.get('reloaded')
                  and ppo.get('updates') and not ppo.get('interrupted')
                  and ppo.get('bootstrap_rows') and ppo.get('dagger_queries')
                  and ppo.get('reloaded') and state.get('version') == 2
                  and state.get('effective') is False
                  and result.get('engine') == 'lite'
                  and (result.get('hardware') or {}).get('trainer_threads') == 1)
        checks.append(dict(name=f'{fmt}_stage_evidence', passed=bool(passed),
                           detail=dict(teacher=teacher, bc=bc, ppo=ppo, state=state,
                                       checks=result.get('checks'))))

    passed = all(entry['passed'] for entry in checks)
    summary = dict(mode='restricted-8-worker', passed=passed, run_dir=str(run_dir),
                   started=started, duration_s=time.time() - started,
                   platform=sys.platform, host=platform.node(),
                   command=sys.argv, wesnoth=wesnoth,
                   config={key: config[key] for key in
                           ('workers', 'engine', 'bc_games', 'native_bc_games',
                            'bc_batch_games', 'bc_records', 'bc_validation_records',
                            'epochs', 'minibatch', 'validation_interval', 'hours',
                            'trainer_memory_gb', 'trainer_threads')},
                   plan=plan, checks=checks, memory=memory,
                   brokers=broker_result, exit_codes=exit_codes,
                   scheduler=dict(rows=len(scheduler_rows), active_peak=active_peak,
                                  max_interval_active=max_active,
                                  intervals=len(intervals), pending=pending),
                   concurrency=dict(pool_peak=int(broker_result.get('peak_native_games', 0)),
                                    cross_format_pairs=len(concurrent),
                                    sampling_update_overlaps=len(overlaps)),
                   job_ids=job_ids,
                   trainer_results={fmt: results[fmt] for fmt in FORMATS})
    write_json(run_dir / 'summary.json', summary)
    print(json.dumps(dict(passed=passed, run_dir=str(run_dir),
                          failed=[entry['name'] for entry in checks if not entry['passed']],
                          checks=[dict(name=entry['name'], passed=entry['passed'])
                                  for entry in checks]), indent=2))
    return 0 if passed else 1


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Restricted T4 real training chain under the global 8-worker pool')
    parser.add_argument('--plan-only', action='store_true',
                        help='run only game-free planning checks and write t4_plan.json')
    parser.add_argument('--wesnoth', default=None,
                        help='Wesnoth 1.18.8 executable for the frozen manifest')
    parser.add_argument('--output', default=None,
                        help='run directory name under verification/pretrain_acceptance_20261022')
    args = parser.parse_args(argv)
    if args.plan_only:
        return plan_only(args)
    return run(args)


if __name__ == '__main__':
    raise SystemExit(main())
