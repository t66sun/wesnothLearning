"""Replay the frozen L1 native holdout with its selected trained duel weights."""
import argparse
from collections import Counter
import json
from pathlib import Path
import time

import torch

from learning.common import read_json, sha256, write_json
from learning.evaluate import comparisons
from learning.export import export
from learning.features import schema
from learning.model import ARCHITECTURE, Policy
from learning.sample import collect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('duel', type=Path, help='Original L1 duel run directory')
    parser.add_argument('output', type=Path, help='Fresh acceptance output directory')
    parser.add_argument('source_commit')
    args = parser.parse_args()
    original, output = args.duel.resolve(), args.output.resolve()
    output.mkdir()
    checkpoint = original / 'selected.pt'
    schedule = original / 'schedules/final.json'
    selection = read_json(original / 'selection.json')
    assert sha256(checkpoint) == selection['selected_sha256'] == '603e3c83d6658b96d65da62bdf5cb277e979fbb19b080d4269ee4ac6e65fff08'
    assert sha256(schedule) == '31049d275eef253d72f3ed3a8f000b0c3e0c3d7dbf9c6ce2271720eeb1dc67fc'
    state = torch.load(checkpoint, map_location='cpu', weights_only=False)
    # This deployment predates the candidate quota descriptor. All ordered
    # tensor inputs, their vocabulary, and the trained parameters must match.
    current = schema()
    selection_contract = current.pop('candidate_selection')
    assert state['features'] == current and state['architecture'] == ARCHITECTURE
    assert state['format'] == 'duel' and state['runner']['version'] == selection['selected_version'] == 12
    model = Policy('duel')
    model.load_state_dict(state['model'])
    identity = read_json(original / 'policies/final-selected/export.json')['identity']
    policy = export(model, output / 'export', name='FinalSelected', version='duel-v12',
                    identity=identity, package=False)

    jobs = read_json(schedule)
    deadline = time.time() + 4 * 3600
    for job in jobs:
        side, = job['meta']['policy_sides']
        job['bots'][side - 1] = job['meta']['policy'] = str(policy)
        job['output'] = str(output / 'replays' / (job['id'] + '.json'))
        job['deadline'] = deadline
    groups = {label: [j for j in jobs if j['meta']['label'] == label]
              for label in ('final-gpt6astra', 'final-baseline')}
    astra = groups['final-gpt6astra'][0]['meta']['control']
    assert sha256(astra) == '2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933'
    (output / 'replays').mkdir()
    write_json(output / 'schedule.json', jobs)
    write_json(output / 'plan.json', dict(source_commit=args.source_commit, workers=4,
               original_schedule_sha256=sha256(schedule), schedule_sha256=sha256(output / 'schedule.json'),
               selection=selection, checkpoint_sha256=sha256(checkpoint), control_sha256=sha256(astra),
               native_sha256=sha256(jobs[0]['wesnoth']), candidate_selection=selection_contract,
               deadline=deadline, games=len(jobs), blocks_per_control=30, min_distinct=12))
    rows = collect(jobs, 4, output / 'jobs.jsonl')
    reports = {label: comparisons(panel, rows)['duel'] for label, panel in groups.items()}
    counts = Counter(r['status'] for r in rows)
    reasons = Counter(r.get('result', {}).get('reason') for r in rows)
    faults = sum(bool(r.get('result', {}).get('faults')) for r in rows)
    passed = (len({r['id'] for r in rows}) == len(rows) == 120 and counts == {'complete': 120}
              and not faults and all(v['blocks'] == 30 and v['distinct_scenarios'] >= 12
                                     for v in reports.values()))
    write_json(output / 'summary.json', dict(passed=passed, statuses=counts, reasons=reasons,
               fault_games=faults, controls=reports))
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
