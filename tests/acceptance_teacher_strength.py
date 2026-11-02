"""Freeze and run the existing 12-block native Astra comparison for TEST.md R3.

Prepare once, inspect plan.json, then run once. Games use validation maps only;
there is no training, collection shard, retry, resume, or holdout evaluation.
"""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time


FORMATS = ('duel', 'ffa4', 'team2v2')
CONTEXTS = ('baseline_partner', 'self_team')
SEED = 20261103
BLOCKS = 12
WORKERS = 8
BUDGET_SECONDS = 6 * 3600


def stage(source, name, output):
    import addons
    from learning.common import write_json

    with tempfile.TemporaryDirectory(prefix=name + '-') as temporary:
        target = Path(temporary) / name
        shutil.copytree(source, target)
        for filename, text in zip(('_main.cfg', 'ai.cfg'), addons.configuration(name)):
            (target / filename).write_text(text, encoding='utf-8')
        write_json(target / 'arena.json', dict(schema=2, id=name, entry='lua/bot.lua'))
        for path in (target / 'lua').glob('*.lua'):
            text = path.read_text(encoding='utf-8')
            path.write_text(text.replace('~add-ons/gpt6astra/', f'~add-ons/{name}/'),
                            encoding='utf-8')
        return addons.pack(target, output / (name + '.zip'))


def identities(root, executable, frozen, adapted, source_commit):
    from learning.common import sha256
    from learning import teachers
    import match

    rules = root / 'data/rules/1.18.8-combat-filtered'
    files = [Path(executable), match.ENTROPY_SHIM,
             rules / 'rules.json', rules / 'catalog-summary.json',
             teachers.PARENT_PACKAGE, frozen, adapted]
    files.extend(root / name for name in (
        'tests/acceptance_teacher_strength.py', 'learning/schedule.py',
        'learning/evaluate.py', 'learning/maps.py', 'learning/sample.py',
        'vendor/arena/match.py', 'vendor/arena/native.py',
        'vendor/arena/addons.py', 'vendor/arena/params.py',
        'vendor/arena/runtime/runtime.lua'))
    return dict(source_commit=source_commit, root=str(root), engine='native',
                native_rules='wesnoth-1.18.8-native-v2',
                teacher=teachers.lineage(),
                artifacts={str(path): sha256(path) for path in files})


def prepare(args):
    from learning.common import sha256, write_json
    import addons
    import native
    from learning.maps import bind_scenario
    from learning.schedule import evaluation_jobs
    from learning import teachers

    root = Path(args.root).resolve()
    output = Path(args.output).resolve()
    executable = native.find_wesnoth(args.wesnoth)
    version = native.check_version(executable)
    output.mkdir(parents=True, exist_ok=False)
    with addons.open_addon(teachers.PARENT_PACKAGE) as source:
        frozen = stage(source, 'astra_frozen', output)
    adapted = stage(teachers.SOURCE, 'astra_adapted', output)
    identity = identities(root, executable, frozen, adapted, args.source_commit)
    created = time.time()
    deadline = created + BUDGET_SECONDS
    jobs = evaluation_jobs(output, str(adapted), str(frozen), ['baseline'],
                           BLOCKS, SEED, deadline, executable,
                           label='r3-panel', formats=FORMATS,
                           team_contexts=CONTEXTS, min_distinct=BLOCKS)
    for job in jobs:
        job.update(engine='native', timeout=1, first_timeout=10)
        job['meta'].update(engine_version='native-1.18.8',
                           combat_version='native-1.18.8',
                           rules_version='wesnoth-1.18.8-native-v2')
        bind_scenario(job)
    # This assertion protects the declared full panel, not game outcomes.
    counts = Counter(job['meta']['format'] for job in jobs)
    assert counts == dict(duel=24, ffa4=48, team2v2=96), counts
    schedule = output / 'schedule.json'
    write_json(schedule, jobs)
    write_json(output / 'identities.json', identity)
    plan = dict(root=str(root), output=str(output), source_commit=args.source_commit,
                wesnoth=executable, wesnoth_version=version, seed=SEED,
                blocks=BLOCKS, min_distinct=BLOCKS, workers=WORKERS,
                max_turns=30, timeout=1, first_timeout=10,
                team_contexts=list(CONTEXTS), games=dict(counts),
                created=created, deadline=deadline, budget_seconds=BUDGET_SECONDS,
                partition='validation', holdout_used=False,
                schedule_sha256=sha256(schedule),
                identities_sha256=sha256(output / 'identities.json'),
                pass_rule='Existing comparisons: 12 complete blocks, 12 families, CI low > 0',
                limit='Report turn_limit separately; candidate truncation is a different counter.')
    write_json(output / 'plan.json', plan)
    print(json.dumps(plan, indent=2), flush=True)


def report(output):
    from learning.common import read_json
    from learning.evaluate import comparisons

    jobs = read_json(output / 'schedule.json')
    results = [json.loads(line) for line in (output / 'jobs.jsonl').read_text(
        encoding='utf-8').splitlines() if line]
    lookup = {row['id']: row for row in results}
    counts = {}
    for fmt in FORMATS:
        planned = [job for job in jobs if job['meta']['format'] == fmt]
        rows = [lookup[job['id']] for job in planned if job['id'] in lookup]
        counts[fmt] = dict(planned=len(planned), observed=len(rows),
                          statuses=dict(Counter(row['status'] for row in rows)),
                          completion_reasons=dict(Counter(
                              row.get('result', {}).get('reason', 'missing')
                              for row in rows if row['status'] == 'complete')),
                          fault_games=sum(bool(row.get('result', {}).get('faults')) for row in rows),
                          candidate_truncations=sum(row.get('truncated', 0) for row in rows))
    summary = dict(comparison=comparisons(jobs, results, min_blocks=BLOCKS,
                                          min_distinct=BLOCKS, team_contexts=CONTEXTS),
                   counts=counts, recorded_at=time.time())
    with (output / 'summary.json').open('x', encoding='utf-8') as stream:
        json.dump(summary, stream, indent=2)
        stream.write('\n')
    print(json.dumps(summary, indent=2), flush=True)


def run(output):
    from learning.common import read_json, sha256, write_json
    from learning.sample import collect

    plan = read_json(output / 'plan.json')
    for filename, expected in (('schedule.json', plan['schedule_sha256']),
                               ('identities.json', plan['identities_sha256'])):
        if sha256(output / filename) != expected:
            raise ValueError(f'frozen {filename} changed')
    identity = read_json(output / 'identities.json')
    for path, expected in identity['artifacts'].items():
        if sha256(path) != expected:
            raise ValueError(f'frozen input changed: {path}')
    if time.time() >= plan['deadline']:
        raise ValueError('frozen six-hour deadline has expired')
    # Exclusive creation prevents accidentally rerunning a frozen panel.
    with (output / 'execution.json').open('x', encoding='utf-8') as stream:
        json.dump(dict(started=time.time(), pid=os.getpid()), stream)
    print(f"Running {sum(plan['games'].values())} games; progress: {output / 'jobs.jsonl'}", flush=True)
    results = collect(read_json(output / 'schedule.json'), plan['workers'], output / 'jobs.jsonl')
    write_json(output / 'results.json', results)
    report(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare_parser = commands.add_parser('prepare')
    prepare_parser.add_argument('--root', required=True)
    prepare_parser.add_argument('--output', required=True)
    prepare_parser.add_argument('--wesnoth', required=True)
    prepare_parser.add_argument('--source-commit', required=True)
    for command in ('run', 'report'):
        commands.add_parser(command).add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    root = (Path(args.root).resolve() if args.command == 'prepare' else
            Path(json.loads((output / 'plan.json').read_text(encoding='utf-8'))['root']))
    sys.path.insert(0, str(root))
    os.chdir(root)
    if args.command == 'prepare':
        prepare(args)
    elif args.command == 'run':
        run(output)
    else:
        report(output)


if __name__ == '__main__':
    main()
