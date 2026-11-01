"""Compare native inference event streams, excluding only wall-clock durations."""
import argparse
import gzip
import hashlib
from itertools import groupby, zip_longest
import json
from pathlib import Path


def timed_events(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            event = json.loads(line)
            if event['event'] == 'RETURN':
                event['data'].pop('elapsed_ms', None)
            if event['event'] == 'LEARN':
                timing = event['data']['timing']
                for name in ('ms', 'generate_ms', 'score_ms', 'inference_ms'):
                    timing.pop(name, None)
            yield event


def events(path):
    # runtime.lua emits independent per-side reports through pairs(config.learning).
    # Canonicalize only contiguous report batches; all gameplay order is retained.
    for name, group in groupby(timed_events(path), key=lambda event: event['event']):
        if name in ('METRIC', 'BOOTSTRAP'):
            yield from sorted(group, key=lambda event: (event['data']['side'],
                event['data'].get('turn', 0), event['data'].get('metric_event', '')))
        else:
            yield from group


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--before', type=Path, required=True)
    parser.add_argument('--after', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    names = sorted(p.name for p in args.before.glob('*.events.jsonl.gz'))
    if not names or names != sorted(p.name for p in args.after.glob('*.events.jsonl.gz')):
        raise ValueError('native game sets differ or are empty')
    results = []
    for name in names:
        before, after = args.before / name, args.after / name
        hashes = [hashlib.sha256(), hashlib.sha256()]
        counts = [0, 0]
        difference = None
        for index, pair in enumerate(zip_longest(events(before), events(after))):
            for side, event in enumerate(pair):
                if event is not None:
                    counts[side] += 1
                    hashes[side].update(json.dumps(event, sort_keys=True, separators=(',', ':')).encode())
                    hashes[side].update(b'\n')
            if pair[0] != pair[1] and difference is None:
                difference = dict(index=index, events=[e['event'] if e else None for e in pair])
        results.append(dict(game=name, event_counts=counts, first_difference=difference,
                            normalized_sha256=[h.hexdigest() for h in hashes],
                            raw_sha256=[hashlib.sha256(p.read_bytes()).hexdigest() for p in (before, after)]))
    result = dict(passed=all(r['first_difference'] is None for r in results), games=results,
                  canonical_batches=['METRIC', 'BOOTSTRAP'],
                  excluded_fields=['RETURN.data.elapsed_ms', 'LEARN.data.timing.{ms,generate_ms,score_ms,inference_ms}'])
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, sort_keys=True))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
