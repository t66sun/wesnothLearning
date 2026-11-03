"""Freeze and run native Astra superiority or declared noninferiority acceptance.

Prepare once, inspect plan.json, then run once. Games use validation maps only;
there is no training, collection shard, retry, resume, or holdout evaluation.
"""
import argparse
from collections import Counter
from decimal import Decimal
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import zipfile


FORMATS = ('duel', 'ffa4', 'team2v2')
CONTEXTS = ('baseline_partner', 'self_team')
SEED = 20261103
BLOCKS = 12
WORKERS = 8
BUDGET_SECONDS = 6 * 3600


def panel_design(noninferiority=False, *, duel_only=False):
    if duel_only:
        return dict(mode='noninferiority', seed=20261105, margin=0.05, label='r3-duel-ni',
                    scales=dict(duel=3), min_distinct=15, required_blocks=dict(duel=960))
    if noninferiority:
        return dict(mode='noninferiority', seed=20261104, margin=0.05,
                    scales=dict(duel=3, ffa4=1, team2v2=3), min_distinct=15,
                    required_blocks=dict(duel=960, ffa4=300, team2v2=180))
    return dict(mode='superiority', seed=SEED, blocks=BLOCKS, min_distinct=BLOCKS)


def stage(source, name, output, *, compatible=False):
    import addons
    from learning.common import write_json

    with tempfile.TemporaryDirectory(prefix=name + '-') as temporary:
        target = Path(temporary) / name
        shutil.copytree(source, target)
        compatibility = None
        if compatible:
            from tests.teacher_control_compatibility import apply_ambush_compatibility
            compatibility = apply_ambush_compatibility(target)
        for filename, text in zip(('_main.cfg', 'ai.cfg'), addons.configuration(name)):
            (target / filename).write_text(text, encoding='utf-8')
        write_json(target / 'arena.json', dict(schema=2, id=name, entry='lua/bot.lua'))
        for path in (target / 'lua').glob('*.lua'):
            text = path.read_text(encoding='utf-8')
            path.write_text(text.replace('~add-ons/gpt6astra/', f'~add-ons/{name}/'),
                            encoding='utf-8')
        return addons.pack(target, output / (name + '.zip')), compatibility


def identities(root, executable, frozen, adapted, source_commit, compatibility=None, source_archive=None):
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
    if compatibility is not None:
        files.append(root / 'tests/teacher_control_compatibility.py')
    if source_archive is not None:
        files.append(source_archive)
    return dict(source_commit=source_commit, root=str(root), engine='native',
                native_rules='wesnoth-1.18.8-native-v2',
                teacher=teachers.lineage(),
                control_compatibility=compatibility,
                source_archive=str(source_archive) if source_archive is not None else None,
                artifacts={str(path): sha256(path) for path in files})


def panel_jobs(output, adapted, frozen, deadline, executable, design):
    from learning.maps import bind_scenario
    from learning.schedule import evaluation_jobs

    if design['mode'] == 'noninferiority':
        jobs = []
        for fmt, blocks in design['required_blocks'].items():
            jobs.extend(evaluation_jobs(
                output, str(adapted), str(frozen), ['baseline'], blocks,
                design['seed'] + FORMATS.index(fmt) * 100003, deadline, executable,
                label=design.get('label', 'r3-ni-panel'), formats=(fmt,), team_contexts=CONTEXTS,
                repeats=blocks // design['min_distinct'], min_distinct=design['min_distinct']))
        jobs.sort(key=lambda job: (job['meta']['block'], job['meta']['rotation'],
                                  FORMATS.index(job['meta']['format']), job['meta']['context']))
    else:
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
    return jobs


def multiplayer_reuse(reference, identity, adapted, control, jobs):
    """Transfer only the two accepted four-player results from the frozen November panel."""
    from learning.common import read_json, sha256
    from learning.maps import frozen_map

    summary_hash = sha256(reference / 'summary.json')
    if summary_hash != '8d56d7df50d9b53d83e824ddcb8b5d155351818d4f7c1966cd6be129f0e7d44d':
        raise ValueError('expected the completed 4560-game NI panel')
    previous = read_json(reference / 'identities.json')
    previous_root = Path(previous['root'])
    for path, expected in previous['artifacts'].items():
        old = Path(path)
        if path == previous['source_archive'] or old.name in (
                adapted.name, control.name, 'acceptance_teacher_strength.py'):
            continue
        current = (Path(identity['root']) / old.relative_to(previous_root)
                   if old.is_relative_to(previous_root) else old)
        if identity['artifacts'].get(str(current)) != expected:
            raise ValueError(f'four-player acceptance input changed: {old.name}')
    for package, permitted in ((adapted, {'astra_adapted/lua/duel.lua'}), (control, set())):
        baseline = reference / package.name
        prior_package = previous_root / 'panel' / package.name
        if sha256(baseline) != previous['artifacts'][str(prior_package)]:
            raise ValueError(f'previous staged package changed: {package.name}')
        with zipfile.ZipFile(baseline) as before, zipfile.ZipFile(package) as after:
            left, right = set(before.namelist()), set(after.namelist())
            changed = (left ^ right) | {p for p in left & right if before.read(p) != after.read(p)}
        if changed != permitted:
            raise ValueError(f'cannot isolate duel repair in {package.name}: {sorted(changed)}')
    prior_jobs = read_json(reference / 'schedule.json')
    if {job['seed'] for job in jobs}.intersection(job['seed'] for job in prior_jobs):
        raise ValueError('duel confirmation overlaps the previous NI panel seeds')
    four_maps = {(j['meta']['map'], j['meta']['map_sha256']) for j in prior_jobs
                 if j['meta']['format'] in ('ffa4', 'team2v2')}
    if four_maps != {('loris_river', frozen_map('loris_river')[1])}:
        raise ValueError('four-player validation map changed')
    return dict(formats=['ffa4', 'team2v2'], source_commit=previous['source_commit'],
                summary_sha256=summary_hash, changed_candidate_member='astra_adapted/lua/duel.lua')


def prepare(args):
    from learning.common import sha256, write_json
    import addons
    import native
    from learning import teachers

    root = Path(args.root).resolve()
    output = Path(args.output).resolve()
    ni = args.noninferiority or args.duel_noninferiority
    if args.duel_noninferiority != bool(args.reuse_panel):
        raise ValueError('--duel-noninferiority requires --reuse-panel, used only with that mode')
    if ni and not args.source_archive:
        raise ValueError('--source-archive is required for noninferiority')
    archive = Path(args.source_archive).resolve(strict=True) if args.source_archive else None
    executable = native.find_wesnoth(args.wesnoth)
    version = native.check_version(executable)
    design = panel_design(ni, duel_only=args.duel_noninferiority)
    output.mkdir(parents=True, exist_ok=False)
    with addons.open_addon(teachers.PARENT_PACKAGE) as source:
        name = 'astra_control_compatible' if ni else 'astra_frozen'
        frozen, compatibility = stage(source, name, output, compatible=ni)
    adapted, _ = stage(teachers.SOURCE, 'astra_adapted', output)
    identity = identities(root, executable, frozen, adapted, args.source_commit, compatibility, archive)
    created = time.time()
    deadline = created + BUDGET_SECONDS
    jobs = panel_jobs(output, adapted, frozen, deadline, executable, design)
    if args.duel_noninferiority:
        design['reused_evidence'] = multiplayer_reuse(Path(args.reuse_panel).resolve(),
                                                      identity, adapted, frozen, jobs)
    # This assertion protects the declared full panel, not game outcomes.
    counts = Counter(job['meta']['format'] for job in jobs)
    per_block = dict(duel=2, ffa4=4, team2v2=8)
    expected = ({fmt: per_block[fmt] * n for fmt, n in design['required_blocks'].items()}
                if ni else dict(duel=24, ffa4=48, team2v2=96))
    assert counts == expected, counts
    schedule = output / 'schedule.json'
    write_json(schedule, jobs)
    write_json(output / 'identities.json', identity)
    plan = dict(root=str(root), output=str(output), source_commit=args.source_commit,
                source_archive=identity['source_archive'],
                source_archive_sha256=identity['artifacts'][str(archive)] if archive is not None else None,
                wesnoth=executable, wesnoth_version=version, **design, workers=WORKERS,
                max_turns=30, timeout=1, first_timeout=10,
                team_contexts=list(CONTEXTS) if 'team2v2' in counts else [], games=dict(counts),
                created=created, deadline=deadline, budget_seconds=BUDGET_SECONDS,
                partition='validation', holdout_used=False,
                schedule_sha256=sha256(schedule),
                identities_sha256=sha256(output / 'identities.json'),
                pass_rule='Existing comparisons: 12 complete blocks, 12 families, CI low > 0',
                limit='Report turn_limit separately; candidate truncation is a different counter.')
    if ni:
        plan['pass_rule'] = ('All declared games/blocks and 15 families per format, zero faults; '
                             'each scheduled format normalized CI lower bound > -0.05')
    write_json(output / 'plan.json', plan)
    print(json.dumps(plan, indent=2), flush=True)


def noninferiority(plan, comparison, counts):
    formats = {}
    for fmt in plan['required_blocks']:
        row, count = comparison.get(fmt, {}), counts.get(fmt, {})
        required, scale = plan['required_blocks'][fmt], plan['scales'][fmt]
        interval = row.get('interval95')
        # Decimal preserves the strict -5% boundary when normalizing e.g. -0.15 / 3.
        normalized = [Decimal(str(value)) / scale for value in interval] if interval else None
        complete = (count.get('planned') == count.get('observed') == plan['games'][fmt]
                    and count.get('statuses', {}).get('complete') == plan['games'][fmt]
                    and count.get('fault_games') == 0 and row.get('fault_games') == 0
                    and row.get('blocks') == row.get('planned_blocks') == required
                    and row.get('missing_blocks') == 0
                    and row.get('distinct_scenarios', 0) >= plan['min_distinct']
                    and row.get('status') not in ('insufficient_design', 'infrastructure_error')
                    and normalized is not None)
        passed = complete and normalized[0] > -Decimal(str(plan['margin']))
        formats[fmt] = dict(status='passed' if passed else 'not_passed' if complete else 'inconclusive',
                            complete=complete, scale=scale, required_blocks=required,
                            difference=(float(Decimal(str(row['difference'])) / scale)
                                        if row.get('difference') is not None else None),
                            interval95=[float(value) for value in normalized] if normalized else None)
    status = ('inconclusive' if any(row['status'] == 'inconclusive' for row in formats.values()) else
              'passed' if all(row['status'] == 'passed' for row in formats.values()) else 'not_passed')
    return dict(margin=plan['margin'], formats=formats, status=status)


def report(output):
    from learning.common import read_json
    from learning.evaluate import comparisons

    jobs = read_json(output / 'schedule.json')
    results = [json.loads(line) for line in (output / 'jobs.jsonl').read_text(
        encoding='utf-8').splitlines() if line]
    lookup = {row['id']: row for row in results}
    plan = read_json(output / 'plan.json')
    counts = {}
    for fmt in plan['games']:
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
    if plan.get('mode') == 'noninferiority':
        summary['noninferiority'] = noninferiority(plan, summary['comparison'], counts)
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
    prepare_parser.add_argument('--source-archive')
    ni_modes = prepare_parser.add_mutually_exclusive_group()
    ni_modes.add_argument('--noninferiority', action='store_true')
    ni_modes.add_argument('--duel-noninferiority', action='store_true')
    prepare_parser.add_argument('--reuse-panel', type=Path)
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
