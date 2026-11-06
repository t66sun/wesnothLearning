"""Account for the frozen run; never execute jobs or load a trainer."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import statistics


def summary(values):
    values = sorted(values)
    return dict(n=len(values), total=sum(values), minimum=min(values),
                median=statistics.median(values), mean=statistics.mean(values),
                maximum=max(values)) if values else dict(n=0, total=0)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def intervals(events):
    """Return completed worker intervals; duplicate/open events remain visible."""
    starts = {}
    result = []
    unmatched = Counter()
    for row in events:
        key = (row['format'], row['id'])
        if row['event'] == 'start':
            if key in starts:
                unmatched['replaced_start'] += 1
            starts[key] = row['time']
        elif key in starts:
            start = starts.pop(key)
            result.append(dict(format=key[0], id=key[1], start=start,
                               end=row['time'], event=row['event']))
        else:
            unmatched['end_without_start'] += 1
    unmatched['open_at_end'] = len(starts)
    return result, dict(unmatched)


def union_seconds(spans):
    """Concurrent worker intervals overlap in elapsed time."""
    total = 0.
    end = float('-inf')
    for start, stop in sorted(spans):
        total += max(0., stop - max(start, end))
        end = max(end, stop)
    return total


def ledger(history):
    rows = []
    for entry in history:
        if entry['method'] != 'ppo':
            continue
        planned = entry['planned_steps']
        committed = entry['committed_steps']
        rejected = int(entry['kl_stopped'])
        inspected = entry['inspected_decisions']
        applied = entry['committed_decisions']
        # A stopped batch actually evaluated one rejected logical step. The
        # remaining planned steps did not run, so they incurred no backward cost.
        assert planned >= committed + rejected
        assert inspected >= applied
        assert rejected or inspected == applied
        rows.append(dict(batch=entry['batch'], eligible_decisions=entry['eligible_decisions'],
            unique_game_families=entry['unique_families_seen'], windows=entry['sequence_windows'],
            committed_steps=committed, rejected_steps=rejected,
            never_attempted_steps=planned - committed - rejected, planned_steps=planned,
            inspected_decisions=inspected, committed_decisions=applied,
            rejected_decisions=inspected - applied, approx_kl=entry['approx_kl'],
            committed_passes=applied / entry['eligible_decisions'],
            elapsed_hours=entry['elapsed_hours'], cursor=entry['cursor']))
    return rows


def inspect(root):
    events = [json.loads(line) for line in (root / 'scheduler.jsonl').open()]
    spans, unmatched = intervals(events)
    duration = max(row['time'] for row in events) - min(row['time'] for row in events)
    output = dict(run=str(root), scheduler=dict(event_elapsed_seconds=duration,
        completed_worker_seconds=sum(s['end'] - s['start'] for s in spans),
        any_worker_seconds=union_seconds((s['start'], s['end']) for s in spans),
        unmatched=unmatched, note='Worker wall occupancy is not CPU utilization.'),
        inputs={str(root / 'scheduler.jsonl'): sha256(root / 'scheduler.jsonl')}, formats={})
    for fmt in ('duel', 'ffa4', 'team2v2'):
        directory = root / fmt
        state = json.loads((directory / 'state.json').read_text())
        jobs = [json.loads(line) for line in (directory / 'jobs.jsonl').open()]
        for name in ('state.json', 'jobs.jsonl'):
            output['inputs'][str(directory / name)] = sha256(directory / name)
        by_id = {row['id']: row for row in jobs}
        phases = defaultdict(list)
        for span in spans:
            if span['format'] == fmt:
                job = by_id.get(span['id'], {})
                phase = job.get('meta', {}).get('phase', span['id'].split('-')[0])
                phases[phase].append(span)
        phase_output = {}
        for phase, entries in sorted(phases.items()):
            phase_output[phase] = dict(jobs=len(entries),
                worker_wall_seconds=sum(s['end'] - s['start'] for s in entries),
                union_wall_seconds=union_seconds((s['start'], s['end']) for s in entries),
                job_wall_seconds=summary([s['end'] - s['start'] for s in entries]))
        ppo = ledger(state['history'])
        scenarios = Counter()
        batches = []
        span_index = {row['id']: row for row in spans if row['format'] == fmt}
        for row in ppo:
            path = directory / 'schedules' / f"ppo-batch-{row['batch']:06}.json"
            schedule = json.loads(path.read_text())
            output['inputs'][str(path)] = sha256(path)
            scenarios.update(j['scenario_family'] for j in schedule)
            completed = [span_index[j['id']] for j in schedule if j['id'] in span_index]
            row.update(new_games=len(schedule), independent_scenarios=len({j['scenario_family'] for j in schedule}),
                       worker_wall_seconds=sum(s['end'] - s['start'] for s in completed),
                       collection_span_seconds=(max(s['end'] for s in completed) - min(s['start'] for s in completed))
                       if completed else None)
            batches.append(row)
        totals = {key: sum(row[key] for row in ppo) for key in (
            'new_games', 'eligible_decisions', 'committed_steps', 'rejected_steps',
            'never_attempted_steps', 'planned_steps', 'inspected_decisions',
            'committed_decisions', 'rejected_decisions')}
        reads = [h['reads']['bc'] for h in state['history'] if h['method'] == 'ppo']
        shards = {}
        for key in ('teacher_shards', 'policy_shards', 'dagger_shards'):
            paths = [Path(p) for p in state.get(key, [])]
            shards[key] = dict(files=len(paths), compressed_bytes=sum(p.stat().st_size for p in paths))
        output['formats'][fmt] = dict(phases=phase_output, batches=batches, totals=totals,
            scenario_count=len(scenarios), scenario_game_counts=dict(scenarios),
            committed_passes=summary([r['committed_passes'] for r in ppo]),
            stop_kl=summary([r['approx_kl'] for r in ppo if r['rejected_steps']]),
            rehearsal_read=dict(gz_bytes=sum(r['gz_bytes'] for r in reads),
                decoded_families=sum(r['families_decoded'] for r in reads),
                returned_rows=sum(r['rows'] for r in reads),
                source_rows=dict(sum((Counter(r['sources']) for r in reads), Counter())),
                excluded_rows=sum(h['rehearsal_rows_excluded'] for h in state['history'] if h['method'] == 'ppo')),
            shards=shards)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(inspect(args.run), indent=2) + '\n')
