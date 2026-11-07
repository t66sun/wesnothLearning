"""Read finished evidence and write one portable metadata export; never run games."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import shutil
from statistics import mean
import time

from learning.teacher_lab.packages import read, write_new
from learning.teacher_lab.report import compare, load_panels, score, valid

ROOT = Path('/home/tongshu/myDev/wesnothLearning/verification/teacher_search_20261107')
LAB = ROOT / 'experiment_v2'
final = read(LAB / 'final.json')
assert read(ROOT / 'selected_package_audit.json')['passed']
assert all((p.parent / 'results.json').exists() for p in (LAB / 'panels').glob('*/plan.json'))
out = ROOT / 'export'
out.mkdir(exist_ok=False)
metadata = out / 'metadata'
metadata.mkdir()


def copy(path):
    target = metadata / path.relative_to(ROOT)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, target)


for name in ('export_evidence_20261107.py', 'archive_evidence_20261107.sh',
             'selected_package_audit_20261107.sh'):
    copy(ROOT / name)
for path in sorted(ROOT.glob('*.json')):
    copy(path)
for directory in sorted(ROOT.iterdir()):
    if directory.is_dir() and ('checks' in directory.name or directory.name.startswith('query_audit')):
        for path in sorted(directory.iterdir()):
            if path.is_file() and path.suffix in ('.json', '.txt', '.md'):
                copy(path)
for name in ('experiment', 'experiment_v1', 'experiment_v2'):
    base = ROOT / name
    if not base.exists():
        continue
    for path in sorted(base.iterdir()):
        if path.is_file() and path.suffix in ('.json', '.zip', '.md'):
            copy(path)
    for path in sorted((base / 'candidates').glob('*/*')):
        if path.is_file() and path.suffix in ('.json', '.zip'):
            copy(path)
    panels = list((base / 'panels').glob('*'))
    panels += [base / 'selection', base / 'selection/validation', base / 'selection/holdout']
    for panel in panels:
        if panel.is_dir():
            for path in sorted(panel.iterdir()):
                if path.is_file() and path.suffix in ('.json', '.jsonl', '.zip', '.md'):
                    copy(path)

jobs, results = load_panels(LAB)
comparison = compare(jobs, results)
write_new(metadata / 'exploration_comparison.json', comparison)
panels = []
for path in sorted((LAB / 'panels').glob('*/plan.json')):
    plan = read(path)
    rows = read(path.parent / 'results.json')
    panels.append(dict(name=path.parent.name, plan=plan,
                       statuses=dict(Counter(row['status'] for row in rows)),
                       started_jobs=sum('started' in row for row in rows),
                       unstarted_budget_jobs=sum(row['status']=='budget_interrupted' and 'started' not in row for row in rows),
                       valid_games=sum(valid(row) for row in rows),
                       fault_games=sum(bool(row.get('result', {}).get('faults')) or
                                       bool(row.get('timing', {}).get('overruns')) for row in rows),
                       finished=max((row.get('finished', 0) for row in rows), default=None)))
write_new(metadata / 'panel_inventory.json', panels)
registry = [read(path) for path in sorted((LAB / 'candidates').glob('*/candidate.json'))]
excluded = read(LAB / 'selection_source.json')['exclusions']
for row in registry:
    row['correctness_exclusion'] = excluded.get(row['name'])
    related = [cell for cell in comparison.values() if cell['candidate'] == row['name']]
    row['exploration_jobs_observed'] = sum(cell['observed'] for cell in related)
    row['exploration_complete_games'] = sum(cell['statuses'].get('complete', 0) for cell in related)
    row['exploration_baseline_cells'] = [cell for cell in related if cell['opponent'] == 'fixed_astra']
write_new(metadata / 'candidate_inventory.json', registry)

holdout = LAB / 'selection/holdout'
jobs = read(holdout / 'schedule.json')
results = read(holdout / 'results.json')
assert compare(jobs, results, min_distinct=12) == final['comparison']
lookup = {row['id']: row for row in results}
cells = defaultdict(list)
for job in jobs:
    cells[(job['meta']['format'], job['meta']['horizon'])].append(job)


def timing_summary(values):
    values = sorted(values)
    return dict(decisions=len(values), mean_ms=mean(values) if values else None,
                p95_ms=values[int(.95 * (len(values)-1))] if values else None,
                max_ms=max(values) if values else None)


details = {}
for (fmt, horizon), planned in sorted(cells.items()):
    blocks = defaultdict(list)
    for job in planned:
        blocks[job['meta']['block']].append(job)
    clusters = defaultdict(lambda: {'candidate': [], 'baseline': []})
    complete_scenes = []
    for block, members in blocks.items():
        if len(members) != {'duel': 2, 'ffa4': 4, 'team2v2': 8}[fmt] or not all(valid(lookup.get(j['id'])) for j in members):
            continue
        family = tuple(sorted({j['scenario_family'] for j in members}))
        complete_scenes.append(dict(block=block, families=family, map=members[0]['meta']['map'],
                                    factions=members[0]['meta']['design_scenario']['factions']))
        for role, side_key in (('candidate', 'policy_sides'), ('baseline', 'control_sides')):
            clusters[family][role].append(mean(mean(score(lookup[j['id']]['result'], side, horizon)
                                                    for side in j['meta'][side_key]) for j in members))
    values = {role: mean(mean(c[role]) for c in clusters.values()) if clusters else None
              for role in ('candidate', 'baseline')}
    timings = defaultdict(list)
    exposure = defaultdict(Counter)
    for job in planned:
        if not valid(lookup.get(job['id'])):
            continue
        for role, side_key in (('candidate', 'policy_sides'), ('baseline', 'control_sides')):
            exposure[role].update(job['factions'][side-1] for side in job['meta'][side_key])
        for line in Path(job['output']).with_suffix('.events.jsonl').read_text().splitlines():
            event = json.loads(line)
            if event['event'] != 'RETURN':
                continue
            data = event['data']
            for role, side_key in (('candidate', 'policy_sides'), ('baseline', 'control_sides')):
                if data['side'] in job['meta'][side_key]:
                    timings[role + '/all'].append(data['elapsed_ms'])
                    timings[role + ('/first' if data['first'] else '/ordinary')].append(data['elapsed_ms'])
    details[f'{fmt}/{horizon}'] = dict(scores=values, complete_scenes=complete_scenes,
        planned_maps=sorted({j['meta']['map'] for j in planned}),
        completed_maps=sorted({j['meta']['map'] for j in planned if valid(lookup.get(j['id']))}),
        faction_seat_exposures=dict(exposure), timings={k: timing_summary(v) for k, v in timings.items()})
write_new(metadata / 'holdout_detail.json', details)
write_new(metadata / 'export_identity.json', dict(created=time.time(), source_root=str(ROOT),
    source_host='cpuServer', evaluator_source=Path('SOURCE_COMMIT').read_text().strip(),
    selected_package_sha256=final['selected']['package_sha256'],
    raw_archive='raw_evidence.tar.gz', raw_archive_scope='Evidence root excluding sources and export',
    passed=final['passed'], note='Copied evidence retains its original absolute source paths.'))
hashes = {p.relative_to(metadata).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
          for p in sorted(metadata.rglob('*')) if p.is_file()}
write_new(metadata / 'SHA256SUMS.json', hashes)
print(json.dumps(dict(metadata=str(metadata), files=len(hashes), final_passed=final['passed'])))
