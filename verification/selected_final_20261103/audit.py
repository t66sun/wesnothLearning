"""Audit completed native results against the original schedule and referee events."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys


out = Path(sys.argv[1])
original = Path(sys.argv[2])
read = lambda path: json.loads(path.read_text())
old = read(original / 'schedules/final.json')
new = read(out / 'schedule.json')
rows = [json.loads(line) for line in (out / 'jobs.jsonl').read_text().splitlines()]
assert len(rows) == len(old) == len(new) == len({r['id'] for r in rows}) == 120
by_id = {r['id']: r for r in rows}
counts = Counter()
timing = {'first': [], 'regular': [], 'turn10plus_regular': []}
for before, job in zip(old, new):
    side, = before['meta']['policy_sides']
    before['bots'][side - 1] = before['meta']['policy'] = job['meta']['policy']
    before.update(output=job['output'], deadline=job['deadline'])
    assert before == job
    row = by_id[job['id']]
    result = row['result']
    assert row['status'] == 'complete' and not result['faults']
    assert result['seed'] == job['seed'] and result['factions'] == job['factions']
    assert result['bots'][side - 1] == 'FinalSelected'
    assert Path(result['native_replay']).is_file()
    label = job['meta']['label']
    counts[label, result['reason']] += 1
    counts[label, 'loss' if result['winner'] not in (0, None, side) else
           'win' if result['winner'] == side else 'draw'] += 1
    turn = 0
    with Path(job['output']).with_suffix('.events.jsonl').open() as stream:
        for line in stream:
            event = json.loads(line)
            data = event['data']
            if event['event'] == 'TURN':
                turn = data['turn']
            if event['event'] == 'RETURN' and data['side'] == side:
                key = 'first' if data['first'] else 'regular'
                timing[key].append(data['elapsed_ms'])
                if turn >= 10 and not data['first']:
                    timing['turn10plus_regular'].append(data['elapsed_ms'])
print(json.dumps(dict(
    original_checkpoint_sha256=hashlib.sha256((original / 'selected.pt').read_bytes()).hexdigest(),
    counts={label: {k: v for (l, k), v in counts.items() if l == label}
            for label in ('final-gpt6astra', 'final-baseline')},
    policy_returns={k: dict(count=len(v), max_ms=max(v), p95_ms=sorted(v)[(len(v)*95-1)//100])
                    for k, v in timing.items()}), indent=2))
