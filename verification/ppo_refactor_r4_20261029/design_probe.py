"""Exercise the declared distinct-scenario floors on planned schedules, without games.

Results here are synthetic wins so the comparator reaches its design branch; the
only quantities under test are the planned scenario identities and the floor
arithmetic. Nothing in this probe is a strength, corpus or convergence signal.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from learning.common import write_json
from learning.evaluate import comparisons, gate_design
from learning.formats import PLAYERS
from learning.schedule import evaluation_jobs, stock_teacher_jobs


def results_for(jobs, fmt):
    rows = []
    for job in jobs:
        sides = job['meta']['policy_sides']
        if PLAYERS[fmt] > 2:
            ranks = {side: (1.0 if side in sides else 0.0) for side in range(1, PLAYERS[fmt] + 1)}
            result = dict(bots=job['bots'], rank_points=ranks, faults={})
        else:
            result = dict(bots=job['bots'], winner=sides[0], faults={})
        rows.append(dict(id=job['id'], status='complete', result=result))
    return rows


def main(destination):
    out = Path(destination)
    out.mkdir(parents=True, exist_ok=True)
    report = dict(panels={}, bc={})
    for fmt in ('duel', 'ffa4', 'team2v2'):
        for label, blocks, floor in (('final', 30, 12), ('val000100', 12, 12)):
            jobs = evaluation_jobs(str(out), 'policy', 'baseline', ['baseline'], blocks, 19,
                                   1e18, 'unused', label=('final-test' if label == 'final' else label),
                                   formats=[fmt], min_distinct=floor)
            gate = gate_design([dict(scenario_family=job['scenario_family']) for job in jobs], floor)
            comparison = comparisons(jobs, results_for(jobs, fmt), min_blocks=blocks,
                                     team_contexts=('baseline_partner', 'self_team'), min_distinct=floor)[fmt]
            report['panels'][f'{label}-{fmt}'] = dict(
                jobs=len(jobs), blocks=blocks,
                distinct_scenarios=len({job['scenario_family'] for job in jobs}),
                gate=gate['status'], comparison=comparison['status'],
                reason=comparison['reason'])
    record = dict(kind='wesnoth_default_rca', version='1.18.8', query='none',
                  runtime_sha256='0' * 64)
    for fmt in ('duel', 'ffa4', 'team2v2'):
        jobs = stock_teacher_jobs(str(out), record, 'support', 0, 19, 1e18, 'unused',
                                  formats=[fmt], count=12, index_stride=12)
        rows = [dict(scenario_family=job['scenario_family']) for job in jobs]
        report['bc'][fmt] = dict(games=len(jobs),
                                 distinct_scenarios=len({job['scenario_family'] for job in jobs}),
                                 gate=gate_design(rows, 12)['status'])
    failed = [key for key, value in report['panels'].items()
              if value['distinct_scenarios'] < 12 or value['comparison'] == 'insufficient_design']
    failed += [fmt for fmt, value in report['bc'].items()
               if value['distinct_scenarios'] < 12 or value['gate'] != 'passed']
    report['status'] = 'passed' if not failed else 'failed'
    report['failed'] = failed
    write_json(out / 'design_probe.json', report)
    print(json.dumps(report, indent=2, sort_keys=True))
    if failed:
        raise SystemExit('design probe failed: ' + ', '.join(failed))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'tmp/r4_design')
