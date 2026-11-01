#!/usr/bin/env python3
"""Replay the frozen bounded-loop teacher schedules and report coverage by reason.

Teacher seats execute the recorded plan verbatim whatever ``choice`` is, so a
replay reproduces every teacher intent and the whole trajectory; only candidate
retention and the matching outcome are recomputed.  That makes the committed
``bc_gate.json`` denominators an identity oracle for the replay.

This is evidence tooling, not a production module.  It reads the schedules from
the acceptance directory it is given and writes its own results beside them, so
it never depends on files inside the shipped tree.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from learning.experiment import coverage_gate
from learning.sample import collect

FORMATS = ('duel', 'ffa4', 'team2v2')
# Committed per-kind action totals of the frozen run; a replay must reproduce them.
DENOMINATORS = {
    'duel': dict(all=2602, recruit=398, move=1187, attack=687),
    'ffa4': dict(all=2423, recruit=255, move=1074, attack=778),
    'team2v2': dict(all=3203, recruit=168, move=2248, attack=397),
}
DEADLINE = 7200


def recorded(root, fmt):
    """The committed per-job coverage records of one format, in id order."""
    lines = (root / fmt / 'jobs.jsonl').read_text(encoding='utf-8').splitlines()
    return sorted((json.loads(line) for line in lines if line.strip()), key=lambda row: row['id'])


def totals(rows):
    """Per-kind action totals of a set of committed per-job coverage records."""
    out = dict(all=sum(r['coverage']['total'] for r in rows))
    for kind in ('recruit', 'move', 'attack'):
        out[kind] = sum(r['coverage']['kinds'][kind]['total'] for r in rows)
    return out


def committed(root, fmt):
    """The jobs whose committed records reproduce the gate, so both runs share one set.

    The frozen run stopped its ffa4/team2v2 blocks after the first batch, so the
    gate covers fewer games than ``jobs.jsonl`` records.  The smallest id prefix
    that reproduces the committed totals is that block; when nothing matches, the
    whole record is replayed and the determinism check reports the difference.
    """
    rows = recorded(root, fmt)
    for n in range(1, len(rows) + 1):
        if totals(rows[:n]) == DENOMINATORS[fmt]:
            return {row['id'] for row in rows[:n]}
    return {row['id'] for row in rows}


def scheduled(root, fmt, out, ids):
    """The selected jobs of one format, rebuilt from its frozen BC schedules."""
    jobs = {}
    for path in sorted((root / fmt / 'schedules').glob('bc-batch-*.json')):
        for job in json.loads(path.read_text(encoding='utf-8')):
            if job['id'] not in ids:
                continue
            job = dict(job, engine='lite', output=str(out / f"{job['id']}.json"),
                       deadline=time.time() + DEADLINE)
            job.pop('shard', None)
            jobs[job['id']] = job
    missing = ids - set(jobs)
    if missing:
        raise SystemExit(f'{fmt}: no schedule holds recorded jobs {sorted(missing)[:5]}')
    return [jobs[i] for i in sorted(jobs)]


def determinism(fmt, gate):
    """Compare the replayed totals against the committed denominators."""
    for kind, expected in DENOMINATORS[fmt].items():
        actual = gate['actions'][kind]['total']
        if actual != expected:
            return f'mismatch {kind} {expected} {actual}'
    return 'ok'


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--schedules', required=True, help='bounded-loop run directory holding duel/ffa4/team2v2')
    parser.add_argument('--out', required=True, help='fresh directory for replays and per-format results')
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--formats', default=','.join(FORMATS))
    args = parser.parse_args()
    root, out = Path(args.schedules), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for fmt in args.formats.split(','):
        jobs = scheduled(root, fmt, out, committed(root, fmt))
        results = collect(jobs, args.workers, out / f'{fmt}.jsonl')
        failed = [r['id'] for r in results if r.get('status') != 'complete']
        if failed:
            raise SystemExit(f'{fmt}: {len(failed)} jobs did not complete: {failed[:5]}')
        gate = coverage_gate(results)
        print(json.dumps(dict(format=fmt, jobs=len(jobs), coverage=gate,
                              truncated=sum(r.get('truncated', 0) for r in results),
                              determinism=determinism(fmt, gate)), sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
