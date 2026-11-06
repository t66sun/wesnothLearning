"""Explicit-budget, paired BC/selected/latest evaluation on validation maps.

Planning exports frozen policies but starts no games. Execution is a separate
command. Neither operation changes the source run or its selected checkpoint.
"""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import shutil
from statistics import mean
import time

import torch

from .common import ROOT, read_json, sha256, write_json
from .evaluate import bootstrap, official_score, scenario_of
from .formats import FORMATS, PLAYERS

ROLES = ('bc', 'selected', 'latest')


def checkpoint_roles(directory):
    """Describe checkpoint bytes; an interrupted update is never latest-complete."""
    directory = Path(directory)

    def describe(name):
        path = directory / name
        if not path.exists():
            return None
        state = torch.load(path, map_location='cpu', weights_only=False)
        runner = state.get('runner', {})
        version = int(runner.get('version', -1))
        return dict(path=str(path.resolve()), checkpoint_sha256=sha256(path),
                    version=version, complete=version >= 0 and not bool(runner.get('pending_train')),
                    method=(runner.get('history') or [{}])[-1].get('method'))

    bc, ppo, current = (describe(name) for name in ('last_bc.pt', 'last_ppo.pt', 'latest.pt'))
    candidates = [row for row in (ppo, bc, current) if row and row['complete']]
    return dict(bc=bc, selected=describe('selected.pt'),
                latest=max(candidates, key=lambda row: row['version']) if candidates else None,
                pending=current if current and not current['complete'] else None)


def _cell(job):
    meta = job['meta']
    return meta['block'], meta['context'], meta['rotation']


def _matched_identity(job):
    meta = job['meta']
    return (scenario_of(job), job['seed'], tuple(meta['policy_sides']),
            tuple(meta['control_sides']), job.get('engine'), job.get('rules_dir'),
            tuple((side, bot) for side, bot in enumerate(job['bots'], 1)
                  if side not in meta['policy_sides']))


def paired_progress(jobs, results, fmt, blocks, *, min_distinct=12):
    """Cluster paired own-score changes; repeated seeds are not new scenarios."""
    if min_distinct < 12 or blocks < min_distinct:
        raise ValueError('progress needs at least 12 complete distinct scenarios')
    planned = {role: {} for role in ROLES}
    contexts = ('solo',) if fmt != 'team2v2' else tuple(sorted({j['meta']['context'] for j in jobs}))
    if fmt == 'team2v2' and set(contexts) not in (
            {'astra_partner', 'self_team'}, {'baseline_partner', 'self_team'}):
        raise ValueError('progress requires both teammate contexts')
    expected = {(b, c, r) for b in range(blocks) for c in contexts for r in range(PLAYERS[fmt])}
    for job in jobs:
        meta = job['meta']
        if meta['format'] != fmt or meta.get('map_partition') != 'validation' or not scenario_of(job):
            raise ValueError('progress requires identified validation scenarios')
        role = meta['progress_role']
        key = _cell(job)
        if key in planned[role]:
            raise ValueError('duplicate progress schedule cell')
        planned[role][key] = job
    if any(set(cells) != expected for cells in planned.values()):
        raise ValueError('progress plan must contain full matched rotation blocks')
    for key in expected:
        if len({_matched_identity(planned[role][key]) for role in ROLES}) != 1:
            raise ValueError('progress roles have unmatched scenarios, seeds or opponents')
    lookup = {row['id']: row for row in results}
    if len(lookup) != len(results):
        raise ValueError('ambiguous duplicate progress result')
    summaries = {}
    scale = 1. if fmt == 'ffa4' else 3.
    for role in ('selected', 'latest'):
        clusters = defaultdict(list)
        role_scores = {key: defaultdict(list) for key in ('bc', role)}
        context_clusters = {context: defaultdict(list) for context in contexts}
        complete, faults, infrastructure = 0, 0, 0
        for block in range(blocks):
            keys = sorted(key for key in expected if key[0] == block)
            records = [lookup.get(planned[r][key]['id'], {}) for r in ('bc', role) for key in keys]
            faults += sum(bool(row.get('result', {}).get('faults')) for row in records)
            infrastructure += sum(row.get('status') == 'infrastructure_error' for row in records)
            if not all(row.get('status') == 'complete' and not row['result'].get('faults') for row in records):
                continue
            family = tuple(sorted({scenario_of(planned['bc'][key]) for key in keys}))
            values = {r: {context: [] for context in contexts} for r in ('bc', role)}
            for r in ('bc', role):
                for key in keys:
                    job = planned[r][key]
                    result = lookup[job['id']]['result']
                    values[r][key[1]].append(mean(official_score(result, side)
                        for side in job['meta']['policy_sides']) / scale)
                role_scores[r][family].append(mean(mean(v) for v in values[r].values()))
            differences = []
            for context in contexts:
                difference = mean(values[role][context]) - mean(values['bc'][context])
                context_clusters[context][family].append(difference)
                differences.append(difference)
            clusters[family].append(mean(differences))
            complete += 1
        means = [mean(values) for values in clusters.values()]
        interval = bootstrap(means)
        enough = complete == blocks and not faults and not infrastructure
        if faults or infrastructure:
            status = 'infrastructure_error'
        elif not enough:
            status = 'inconclusive'
        elif len(clusters) < min_distinct:
            status = 'insufficient_design'
        elif interval[0] > 0:
            status = 'improved'
        elif interval[1] < 0:
            status = 'regressed'
        else:
            status = 'inconclusive'
        summaries[role] = dict(status=status, complete=enough, planned_blocks=blocks,
            blocks=complete, missing_blocks=blocks-complete, fault_games=faults,
            distinct_scenarios=len(clusters), min_distinct=min_distinct,
            difference=mean(means) if means else None, interval95=interval,
            scores={r: mean(mean(v) for v in grouped.values()) if grouped else None
                    for r, grouped in role_scores.items()},
            contexts={context: dict(difference=mean(mean(v) for v in grouped.values()) if grouped else None,
                        interval95=bootstrap([mean(v) for v in grouped.values()]))
                      for context, grouped in context_clusters.items()})
    return summaries


def plan(directory, output, *, fmt, blocks, seed, hours):
    """Freeze a new explicit evaluation budget without launching games."""
    from .export import export, load_model
    from .manifest import output_path, tree_hashes
    from .maps import SPLITS, bind_scenario
    from .rules_catalog import load, resolve_dir
    from .schedule import evaluation_jobs, freeze_schedule, starting_factions
    from .selection import validate_frozen_selection

    if blocks < 12 or len(starting_factions(PLAYERS[fmt], fmt))*len(SPLITS[fmt]['validation']) < 12:
        raise ValueError('progress needs at least 12 complete distinct scenarios')
    if not math.isfinite(hours) or hours <= 0:
        raise ValueError('progress hours must be finite and positive')
    directory = Path(directory).resolve()
    output = output_path(output)
    if output.is_relative_to(directory.parent):
        raise ValueError('progress output must be outside the frozen source run')
    manifest_path = directory.parent/'manifest.json'
    manifest = read_json(manifest_path)
    roles = checkpoint_roles(directory)
    if any(not roles[role] or not roles[role]['complete'] for role in ROLES):
        raise ValueError('progress requires complete BC, selected and latest checkpoints')
    validate_frozen_selection(directory/'selection.json', roles['selected']['checkpoint_sha256'])
    engine = manifest['config'].get('evaluation_engine', manifest['config']['engine'])
    rules = resolve_dir(manifest['rules']['directory'])
    if load(rules)['rules_file_sha256'] != manifest['rules']['rules_sha256']:
        raise ValueError('progress frozen rules identity changed')
    opponent = manifest['opponents'][0]
    if sha256(opponent['path']) != opponent['sha256']:
        raise ValueError('progress frozen opponent changed')
    output.mkdir(parents=True, exist_ok=False)
    control = output/'opponents'/Path(opponent['path']).name
    control.parent.mkdir()
    shutil.copyfile(opponent['path'], control)
    fixed = [str(control)] + (['baseline'] if engine == 'native' else [])
    contexts = ('baseline_partner', 'self_team') if engine == 'native' else ('astra_partner', 'self_team')
    deadline = time.time()+hours*3600
    identity = dict(roles=roles, seed=seed, blocks=blocks, engine=engine,
                    rules_sha256=manifest['rules']['rules_sha256'], control_sha256=opponent['sha256'])
    token = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:16]
    jobs = []
    for role in ROLES:
        # The exported weights are frozen even if the source run later advances.
        model, _ = load_model(roles[role]['path'], fmt)
        if sha256(roles[role]['path']) != roles[role]['checkpoint_sha256']:
            raise ValueError('checkpoint changed during progress planning')
        destination = output/'policies'/role
        name = 'Progress'+role.title()
        export({fmt: model}, destination, name=name, mode='greedy', package=False,
               version=str(roles[role]['version']))
        policy = str(destination/name)
        role_jobs = evaluation_jobs(output, policy, str(control), fixed, blocks, seed,
            deadline, manifest['baseline']['path'], label=f'progress-{token}-{role}',
            formats=[fmt], team_contexts=contexts, min_distinct=12)
        for job in role_jobs:
            job.update(engine=engine, rules_dir=str(rules), allow_approximate=manifest['config'].get('allow_approximate', False))
            job['meta'].update(progress_role=role, engine_id=engine, rules_sha256=identity['rules_sha256'])
            bind_scenario(job)
        jobs.extend(role_jobs)
    jobs.sort(key=lambda job: (*_cell(job), job['meta']['progress_role']))
    paired_progress(jobs, [], fmt, blocks)  # validate the matched design before freezing
    schedule = output/'jobs.json'
    freeze_schedule(schedule, jobs)
    record = dict(schema=1, format=fmt, checkpoint_roles=roles, input_manifest_sha256=sha256(manifest_path),
        engine=engine, rules_dir=str(rules), rules_sha256=identity['rules_sha256'],
        budget=dict(blocks_per_role=blocks, min_distinct=12, games=len(jobs), hours=hours, deadline=deadline),
        seed=seed, schedule_sha256=sha256(schedule),
        artifacts={folder: tree_hashes(output/folder) for folder in ('policies', 'opponents')},
        evaluator_source={folder: tree_hashes(ROOT/folder) for folder in ('learning', 'lua', 'engine_lite', 'vendor/arena')})
    write_json(output/'plan.json', record)
    return record


def load_plan(path):
    path = Path(path)
    record = read_json(path)
    schedule = path.parent/'jobs.json'
    if sha256(schedule) != record['schedule_sha256']:
        raise ValueError('progress schedule changed after freezing')
    return record, read_json(schedule)


def write_report(plan_path, results_path, output):
    record, jobs = load_plan(plan_path)
    results_path = Path(results_path)
    results = read_json(results_path) if results_path.suffix == '.json' else [
        json.loads(line) for line in results_path.read_text(encoding='utf-8').splitlines() if line.strip()]
    report = dict(format=record['format'], checkpoint_roles=record['checkpoint_roles'],
        budget=record['budget'], plan_sha256=sha256(plan_path), results_sha256=sha256(results_path),
        scope='paired normalized own score on validation maps; independent of final holdout and selection',
        progress=paired_progress(jobs, results, record['format'], record['budget']['blocks_per_role']))
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    write_json(output/'summary.json', report)
    lines = ['# BC to PPO progress', '', report['scope'], '',
             '| Role | Version | Checkpoint SHA-256 |', '|---|---:|---|']
    for role in ROLES:
        row = report['checkpoint_roles'][role]
        lines.append(f"| {role} | {row['version']} | {row['checkpoint_sha256']} |")
    lines += ['', '| Versus BC | Complete | Blocks | Scenarios | Score change | 95% interval | Status |',
              '|---|---|---:|---:|---:|---|---|']
    for role, row in report['progress'].items():
        lines.append(f"| {role} | {row['complete']} | {row['blocks']}/{row['planned_blocks']} | "
                     f"{row['distinct_scenarios']} | {row['difference']} | {row['interval95']} | {row['status']} |")
    (output/'REPORT.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return report


def run(plan_path, workers):
    from .manifest import tree_hashes
    from .rules_catalog import load
    from .sample import collect

    record, jobs = load_plan(plan_path)
    directory = Path(plan_path).parent
    if not 1 <= workers <= 16:
        raise ValueError('workers must be in [1,16]')
    for folder, expected in record['artifacts'].items():
        if tree_hashes(directory/folder) != expected:
            raise ValueError('progress export or opponent changed: '+folder)
    for folder, expected in record['evaluator_source'].items():
        if tree_hashes(ROOT/folder) != expected:
            raise ValueError('progress evaluator source changed: '+folder)
    if load(record['rules_dir'])['rules_file_sha256'] != record['rules_sha256']:
        raise ValueError('progress rules changed')
    if time.time() >= record['budget']['deadline']:
        raise ValueError('progress budget expired; prepare a fresh explicitly budgeted plan')
    output = directory/'execution'
    output.mkdir(exist_ok=False)
    results = collect(jobs, workers, output/'jobs.jsonl')
    write_json(output/'results.json', results)
    return write_report(plan_path, output/'results.json', directory/'report')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare = commands.add_parser('plan', help='export a frozen plan; starts no games')
    prepare.add_argument('--directory', required=True, help='existing run/<format> directory')
    prepare.add_argument('--format', choices=FORMATS, required=True)
    prepare.add_argument('--output', required=True)
    prepare.add_argument('--blocks', type=int, required=True)
    prepare.add_argument('--seed', type=int, required=True)
    prepare.add_argument('--hours', type=float, required=True)
    execute = commands.add_parser('run', help='execute the explicitly budgeted plan; starts games')
    execute.add_argument('--plan', required=True)
    execute.add_argument('--workers', type=int, default=8)
    report = commands.add_parser('report', help='recompute from recorded replies; starts no games')
    report.add_argument('--plan', required=True)
    report.add_argument('--results', required=True)
    report.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.command == 'plan':
        result = plan(args.directory, args.output, fmt=args.format, blocks=args.blocks, seed=args.seed, hours=args.hours)
    elif args.command == 'run':
        result = run(args.plan, args.workers)
    else:
        result = write_report(args.plan, args.results, args.output)
    print(json.dumps(result.get('budget', result), ensure_ascii=False))


if __name__ == '__main__':
    main()
