import argparse
import json
from pathlib import Path
import time
from learning.common import ROOT
from learning.formats import FORMATS
from .packages import digest, read, stage, write_new
from .panels import HORIZONS, execute, jobs_for
from .report import candidate_cells, compare, load_panels, provisional, rank_key, report_panel
import match
import native


def clock(directory):
    return read(directory / 'clock.json')


def candidate(directory, name):
    result = read(directory / 'candidates' / name / 'candidate.json')
    if digest(result['package']) != result['package_sha256']:
        raise ValueError('frozen candidate package changed')
    return result


def init(args):
    directory = args.directory
    directory.mkdir(parents=True, exist_ok=False)
    executable = native.find_wesnoth(args.wesnoth)
    native.check_version(executable)
    if not match.ENTROPY_SHIM.is_file():
        raise ValueError('native paired comparisons require the entropy shim')
    baseline = stage(ROOT / 'learning/teachers/gpt6astra', 'fixed_astra', directory / 'fixed_astra.zip')
    baseline.update(timeout=1, first_timeout=10, source_commit=args.source_commit)
    manifest = dict(schema=1, source_commit=args.source_commit, evaluator_root=str(ROOT),
                    executable=executable, executable_sha256=digest(executable),
                    entropy_sha256=digest(match.ENTROPY_SHIM), baseline=baseline, workers=8,
                    rules_sha256=digest(ROOT / 'data/rules/1.18.8-combat-filtered/rules.json'),
                    formats=list(FORMATS), horizons=list(HORIZONS), created=time.time(),
                    exploration_seconds=18000, post_seconds=14400, selection_seconds=3600,
                    improvement=.10, confidence=.95, min_distinct=12)
    write_new(directory / 'manifest.json', manifest)
    print(json.dumps(manifest, indent=2), flush=True)


def register(args):
    manifest = read(args.directory / 'manifest.json')
    timer = clock(args.directory) if (args.directory / 'clock.json').exists() else None
    if timer and time.time()>=timer['exploration_end']:
        raise ValueError('exploration has ended; candidates are frozen')
    directory = args.directory / 'candidates' / args.name
    directory.mkdir(parents=True, exist_ok=False)
    config = json.loads(args.parameters)
    result = stage(args.source or ROOT / 'learning/teachers/search_teacher', args.name,
                   directory / (args.name + '.zip'), config)
    result.update(source_commit=args.source_commit, registered=time.time(), description=args.description,
                  timeout=2, first_timeout=20)
    if timer and result['registered']>=timer['exploration_end']:
        raise ValueError('candidate packaging crossed the exploration deadline')
    write_new(directory / 'candidate.json', result)
    print(json.dumps(result, indent=2), flush=True)


def start(args):
    manifest = read(args.directory / 'manifest.json')
    qualified = False
    for panel in (args.directory / 'panels').glob('*'):
        if not (panel / 'summary.json').exists():
            continue
        plan = read(panel / 'plan.json')
        if plan['metadata'].get('preflight'):
            rows = list(read(panel / 'summary.json').values())
            if len(rows)==6 and all(r['complete'] and r['fault_games']==0 for r in rows):
                qualified = True
    if not qualified:
        raise ValueError('a complete fault-free six-cell preflight is required')
    now = time.time()
    timer = dict(started=now, exploration_end=now+manifest['exploration_seconds'],
                 selection_end=now+manifest['exploration_seconds']+manifest['selection_seconds'],
                 final_end=now+manifest['exploration_seconds']+manifest['post_seconds'])
    write_new(args.directory / 'clock.json', timer)
    print(json.dumps(timer, indent=2), flush=True)


def panel(args):
    manifest = read(args.directory / 'manifest.json')
    chosen = candidate(args.directory, args.candidate)
    control = manifest['baseline'] if args.opponent=='baseline' else candidate(args.directory, args.opponent)
    if digest(control['package']) != control['package_sha256']:
        raise ValueError('frozen opponent package changed')
    if args.preflight:
        if (args.directory / 'clock.json').exists():
            raise ValueError('preflight cannot bypass an active exploration clock')
        deadline = time.time()+1800
    else:
        deadline = clock(args.directory)['exploration_end']
        if time.time()>=deadline:
            raise ValueError('exploration deadline expired')
        if args.opponent!='baseline':
            prior_jobs, prior_results = load_panels(args.directory, opponent=manifest['baseline']['name'])
            previous = compare(prior_jobs, prior_results)
            if not any(provisional(candidate_cells(previous, c, manifest['baseline']['name']))
                       for c in {r['candidate'] for r in previous.values()}):
                raise ValueError('version league starts only after a provisional baseline win')
    directory = args.directory / 'panels' / args.name
    jobs = [job for fmt in args.formats for horizon in args.horizons
            for job in jobs_for(directory, chosen, control, fmt, horizon, args.blocks, 'train', deadline,
                                manifest['executable'], seed=args.seed, offset=args.offset)]
    results = execute(directory, jobs, workers=manifest['workers'],
                      metadata=dict(preflight=args.preflight, partition='train', source_commit=manifest['source_commit'],
                                    candidate_sha256=chosen['package_sha256'], control_sha256=control['package_sha256']))
    summary = report_panel(directory, jobs, results)
    print(json.dumps(summary, indent=2), flush=True)


def status(args):
    manifest = read(args.directory / 'manifest.json')
    jobs, results = load_panels(args.directory, opponent=manifest['baseline']['name'])
    summary = compare(jobs, results)
    rankings = {}
    for fmt in FORMATS:
        entries = []
        for path in (args.directory / 'candidates').glob('*/candidate.json'):
            row = read(path);cells=candidate_cells(summary, row['name'], manifest['baseline']['name'])
            entries.append(dict(name=row['name'], key=rank_key(cells, fmt), provisional=provisional(cells)))
        rankings[fmt] = sorted(entries, key=lambda r: (r['key'] is not None, r['key'] or []), reverse=True)
    active = []
    for path in (args.directory / 'panels').glob('*/plan.json'):
        if not (path.parent / 'results.json').exists():
            log = path.parent / 'jobs.jsonl'
            active.append(dict(name=path.parent.name, planned=read(path)['games'],
                               finished=len(log.read_text().splitlines()) if log.exists() else 0))
    print(json.dumps(dict(clock=clock(args.directory) if (args.directory/'clock.json').exists() else None,
                          rankings=rankings, active=active, comparison=summary), indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description='Independent native teacher experiment')
    parser.add_argument('--directory', required=True, type=Path)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('init');p.add_argument('--source-commit', required=True);p.add_argument('--wesnoth')
    p = commands.add_parser('register');p.add_argument('--name', required=True)
    p.add_argument('--source', type=Path);p.add_argument('--source-commit', required=True)
    p.add_argument('--parameters', default='{}');p.add_argument('--description', required=True)
    commands.add_parser('start');commands.add_parser('status')
    p = commands.add_parser('panel');p.add_argument('--name', required=True);p.add_argument('--candidate', required=True)
    p.add_argument('--opponent', default='baseline');p.add_argument('--blocks', type=int, default=1)
    p.add_argument('--offset', type=int, default=0);p.add_argument('--seed', type=int, default=20261107)
    p.add_argument('--formats', nargs='+', choices=FORMATS, default=FORMATS)
    p.add_argument('--horizons', nargs='+', type=int, choices=HORIZONS, default=HORIZONS)
    p.add_argument('--preflight', action='store_true')
    commands.add_parser('select')
    args = parser.parse_args();args.directory=args.directory.resolve()
    if args.command=='select':
        from .selection import select
        select(args.directory)
    else:
        globals()[args.command](args)


if __name__ == '__main__':
    main()
