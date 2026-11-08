"""Recount B3 support from the frozen Ubuntu gates, schedules and job logs."""

from collections import Counter
import json
from pathlib import Path
import sys


def read(path):
    return json.loads(path.read_text())


def eligible_jobs(path, phase):
    results = {}
    for line in path.read_text().splitlines():
        row = json.loads(line)
        if (row.get('meta', {}).get('phase') == phase and row['status'] == 'complete'
                and row['training_eligible'] and not row['result']['faults']):
            assert row['id'] not in results
            results[row['id']] = row
    return results


def bc(duel):
    gate = read(duel / 'bc_gate.json')
    jobs = eligible_jobs(duel / 'jobs.jsonl', 'teacher')
    assert len(jobs) == gate['corpus']['games']
    support = Counter()
    matches, totals = Counter(), Counter()
    for job in jobs.values():
        coverage = job['coverage']
        support.update(coverage.get('teacher_support', {}))
        for kind, counts in coverage['kinds'].items():
            matches[kind] += counts['matched']
            totals[kind] += counts['total']
    assert support == gate['coverage'].get('teacher_support', {})
    matches['attack'] -= matches['move_attack']
    totals['attack'] -= totals['move_attack']
    exact_kinds = {kind: dict(matched=matches[kind], total=total) for kind, total in totals.items()}
    return dict(games=len(jobs), gate=gate, exact_kinds=exact_kinds)


def ppo(cell):
    ledger = cell['ledger']
    duel = Path(cell['run']) / 'duel'
    results = eligible_jobs(duel / 'jobs.jsonl', 'ppo')
    jobs = [job for row in ledger['history'] for job in read(
        duel / 'schedules' / f"ppo-batch-{row['batch']:06}.json")]
    families = {job['game_family'] for job in jobs}
    assert len(families) == len(jobs) == ledger['policy_games']
    assert {job['id'] for job in jobs} == results.keys()
    assert sum(row['training_shard']['written'] for row in results.values()) == ledger['fresh_targets']
    counts = Counter(games=len(jobs), fresh=ledger['fresh_targets'])
    teacher_support = Counter()
    for row in results.values():
        assert row['result']['task_terminal']
        coverage = row['coverage']
        if cell['route'] == 'base':
            assert 'candidate_use' not in coverage and 'teacher_support' not in coverage
            continue
        teacher_support.update(coverage['teacher_support'])
        use = coverage['candidate_use']
        assert use['decisions'] == row['training_shard']['raw_records']
        counts['decisions'] += use['decisions']
        counts['games_with_any_selection'] += bool(use['selected'])
        for stage in ('offered', 'selected'):
            for kind, count in use[stage].items():
                counts[f'{kind}:{stage}'] += count
                counts[f'{kind}:{stage}_games'] += bool(count)
    return dict(counts=counts, teacher_support=teacher_support), families


def main(root):
    manifest = read(root / 'launch-manifest.json')
    b_source = Path(manifest['contracts']['b']['source'])
    report = dict(base_bc=bc(Path(manifest['base_bc_parent']) / 'duel'),
                  b_bc=bc(b_source / 'runs/experiment/bc/duel'))
    for arm in ('base', 'b'):
        totals, stages, cells, game_families = Counter(), Counter(), {}, set()
        for seed in (202611071, 202611072, 202611073):
            data, families = ppo(read(root / 'experiment' / f'{arm}-{seed}-ledger.json'))
            cells[seed] = data
            game_families.update(families)
            totals.update(data['counts'])
            stages.update(data['teacher_support'])
        assert totals['games'] == len(game_families)
        report[arm] = dict(cells=cells, counts=totals, teacher_support=stages)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == '__main__':
    main(Path(sys.argv[1]))
