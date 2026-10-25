"""One fresh authorized run; detached startup and read-only status snapshots."""
from pathlib import Path
import datetime
import json
import os
import platform
import subprocess
import sys

ROOT = Path.cwd()
WORK = ROOT.parent
LOGS = WORK / 'logs'
RUN = ROOT / 'runs/v5_lite30h_20261025'
PROVISION = Path('/home/tongshu/myDev/wesnothLearning/acceptance_refactor_20261025/master')


def load(path):
    return json.loads(path.read_text()) if path.exists() else {}


def emit(value):
    print(json.dumps(value, indent=2, ensure_ascii=False), flush=True)


def command():
    return [sys.executable, '-u', '-B', '-m', 'learning', 'run',
            '--run-dir', str(RUN), '--engine', 'lite', '--evaluation-engine', 'lite',
            '--bc-games', '300', '600', '400', '--native-bc-games', '0', '0', '0',
            '--device', 'cpu', '--workers', '8', '--trainer-threads', '1',
            '--hours', '30', '--phase', 'auto', '--formats', 'duel', 'ffa4', 'team2v2',
            '--seed', '20261017', '--validation-interval', '10', '--final-blocks', '30',
            '--final-holdout-hours', '4', '--wesnoth', str(PROVISION / '.runtime/install/bin/wesnoth'),
            '--rules-dir', str(ROOT / 'data/rules/1.18.8-training'),
            '--opponents', str(ROOT / 'data/opponents'), '--human-data', str(ROOT / 'data/datasets/human')]


def preflight():
    import torch
    import _engine_lite
    from learning.features import schema
    from learning.teachers import identity
    from learning.__main__ import parser, run_config
    from learning.experiment import validate_config
    from learning.manifest import tree_hashes
    core = {key: getattr(_engine_lite, key) for key in ('ENGINE_VERSION', 'RNG_VERSION', 'COMBAT_VERSION')}
    assert core == dict(ENGINE_VERSION='lite-0.2', RNG_VERSION='deterministic-expected_damage_v1', COMBAT_VERSION='expected_damage_v1'), core
    assert schema()['rules_sha256'] == 'd6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca'
    teacher = identity()
    assert teacher['teacher_source_sha256'] == 'a5d4b3a69d5af0378fa22119f315c1300fb6ad965c79b08071eb4a37c0addbef', teacher
    assert torch.__version__.startswith('2.9.1'), torch.__version__
    assert not RUN.exists(), RUN
    assert not list((ROOT / 'data/datasets/human').rglob('*.gz'))
    config = run_config(parser().parse_args(command()[5:]))
    validate_config(config)
    baseline = subprocess.check_output([str(PROVISION / '.runtime/install/bin/wesnoth'), '--version'], text=True, stderr=subprocess.STDOUT)
    assert '1.18.8' in baseline, baseline
    record = dict(source_revision=os.environ['TRAINING_SOURCE_REVISION'], archive_sha256=os.environ['TRAINING_ARCHIVE_SHA256'],
                  platform=platform.platform(), python=sys.version, torch=torch.__version__, extension=_engine_lite.__file__,
                  engine=core, rules=schema()['rules_sha256'], teacher=teacher, baseline=baseline,
                  config=config, command=command(), source={folder:tree_hashes(ROOT / folder) for folder in ('learning','lua','vendor/arena','engine_lite','benchmarks')},
                  meminfo=Path('/proc/meminfo').read_text())
    (LOGS / 'predeclared.json').write_text(json.dumps(record, indent=2))
    emit(record)


def start():
    assert not RUN.exists(), RUN
    assert not (LOGS / 'launch.json').exists()
    with (LOGS / 'training.log').open('xb') as output:
        process = subprocess.Popen(command(), cwd=ROOT, env=os.environ.copy(), stdin=subprocess.DEVNULL,
                                   stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
    record = dict(pid=process.pid, session=process.pid, command=command(), run=str(RUN),
                  launched_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  source_revision=os.environ['TRAINING_SOURCE_REVISION'], archive_sha256=os.environ['TRAINING_ARCHIVE_SHA256'])
    (LOGS / 'launch.json').write_text(json.dumps(record, indent=2))
    emit(record)


def status():
    launch = load(LOGS / 'launch.json')
    pid = launch.get('pid')
    proc = Path('/proc') / str(pid)
    cmdline = (proc / 'cmdline').read_bytes().replace(b'\0', b' ').decode() if (proc / 'cmdline').exists() else ''
    alive = bool(cmdline and str(RUN) in cmdline)
    manifest = load(RUN / 'manifest.json')
    formats = {}
    for fmt in ('duel', 'ffa4', 'team2v2'):
        folder = RUN / fmt
        state = load(folder / 'state.json')
        rows = {}
        path = folder / 'jobs.jsonl'
        if path.exists():
            for line in path.read_text().splitlines():
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                rows[row['id']] = row
        valid = [r for r in rows.values() if r.get('meta', {}).get('phase') == 'teacher' and r.get('status') == 'complete'
                 and not r.get('result', {}).get('faults') and r.get('training_eligible', True) and r.get('coverage', {}).get('matched', 0) > 0]
        checkpoint = folder / 'latest.pt'
        errors = {name:(folder / name).read_text()[-6000:] for name in ('trainer_error.log', 'errors.log') if (folder / name).exists()}
        formats[fmt] = dict(stage=state.get('stage'), version=state.get('version'), batch=state.get('batch'),
                            counters=state.get('counters'), effective=state.get('effective'), valid_teacher_games=len(valid),
                            job_statuses={s:sum(r.get('status') == s for r in rows.values()) for s in sorted({r.get('status','unknown') for r in rows.values()})},
                            checkpoint_bytes=checkpoint.stat().st_size if checkpoint.exists() else 0,
                            checkpoint_mtime=checkpoint.stat().st_mtime if checkpoint.exists() else None,
                            error=state.get('error'), errors=errors)
    ready = alive and all(v['valid_teacher_games'] > 0 and (v.get('counters') or {}).get('optimizer_steps', 0) > 0
                          and v['checkpoint_bytes'] > 0 and not v['error'] and not v['errors'] for v in formats.values())
    record = dict(observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), alive=alive, pid=pid,
                  startup_ready=ready, config=manifest.get('config'), clock=load(RUN / 'clock.json'), formats=formats,
                  training_log_tail=(LOGS / 'training.log').read_text(errors='replace')[-6000:])
    emit(record)


if __name__ == '__main__':
    {'preflight':preflight, 'start':start, 'status':status}[sys.argv[1]]()
