"""Summarize frozen #306 preparation traces and model bounded family reuse."""
from collections import OrderedDict
import json
from pathlib import Path
import sys

SEEDS = (202611081, 202611082, 202611083)
SEGMENTS = ('early', 'middle', 'late')
FAMILY_BUDGET = 256 << 20


def adjusted(batch, name):
    time = batch['timings'][name]['wall_seconds']
    if name == 'rehearsal_read':
        time -= batch['instrumentation']['estimate']['wall_seconds']
    return time


def segment_cost(batches, seen, resident):
    result = dict(batches=[batch['batch'] for batch in batches], recorded_wall=0.0,
                  prepare=0.0, rehearsal_read=0.0, family_decode=0.0, rehearsal_identity=0.0,
                  observed_repeated_decode=0.0, bounded_repeated_decode=0.0,
                  decoded=0, repeat_decodes=0, bounded_hits=0, target_count=0, repeat_targets=0,
                  prefix_slots=0, repeat_prefix_slots=0)
    prior_targets = set()
    prior_prefixes = {}
    used = sum(resident.values())
    for batch in batches:
        result['recorded_wall'] += batch['recorded_wall_seconds']
        result['prepare'] += sum(adjusted(batch, name) for name in batch['timings'])
        result['rehearsal_read'] += adjusted(batch, 'rehearsal_read')
        result['rehearsal_identity'] += adjusted(batch, 'rehearsal_identity')
        for family in batch['families']:
            key = tuple(family['paths'])
            cost, size = family['seconds'], family['payload_bytes']
            result['family_decode'] += cost
            result['decoded'] += 1
            if key in seen:
                result['repeat_decodes'] += 1
                result['observed_repeated_decode'] += cost
            seen.add(key)
            if key in resident:
                assert resident[key] == size
                result['bounded_hits'] += 1
                result['bounded_repeated_decode'] += cost
                resident.move_to_end(key)
            elif size <= FAMILY_BUDGET:
                while used + size > FAMILY_BUDGET:
                    _, evicted = resident.popitem(last=False)
                    used -= evicted
                resident[key] = size
                used += size
        targets = {tuple(target) for target in batch['targets']}
        result['target_count'] += len(targets)
        result['repeat_targets'] += len(targets & prior_targets)
        prior_targets.update(targets)
        for sequence, length in batch['prefixes']:
            key = tuple(sequence)
            prior = prior_prefixes.get(key, 0)
            result['prefix_slots'] += length
            result['repeat_prefix_slots'] += min(length, prior)
            prior_prefixes[key] = max(length, prior)
    result['first_prepare'] = sum(adjusted(batches[0], name) for name in batches[0]['timings'])
    result['peak_rss_kib'] = max(batch['peak_rss_kib'] for batch in batches)
    return result


def summarize(path):
    blocks = {}
    for seed in SEEDS:
        source = path / f'{seed}.jsonl'
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        assert len(rows) == 24 and {row['seed'] for row in rows} == {seed}
        for segment in SEGMENTS:
            batches = [row for row in rows if row['segment'] == segment]
            assert len(batches) == 8
            start = batches[0]['batch']
            assert [row['batch'] for row in batches] == list(range(start, start + 8))
            blocks[f'{seed}/{segment}'] = segment_cost(batches, set(), OrderedDict())

    totals = {}
    columns = ('recorded_wall', 'prepare', 'rehearsal_read', 'family_decode', 'rehearsal_identity',
               'observed_repeated_decode', 'bounded_repeated_decode', 'decoded', 'repeat_decodes',
               'bounded_hits', 'target_count', 'repeat_targets', 'prefix_slots', 'repeat_prefix_slots')
    for segment in (*SEGMENTS, 'all'):
        chosen = [block for name, block in blocks.items() if segment == 'all' or name.endswith(segment)]
        total = {column: sum(block[column] for block in chosen) for column in columns}
        total['all_read_and_identity_share'] = (
            (total['rehearsal_read'] + total['rehearsal_identity']) / total['recorded_wall'])
        for name in ('observed', 'bounded'):
            total[f'{name}_decode_plus_all_identity_share'] = (
                (total[f'{name}_repeated_decode'] + total['rehearsal_identity']) / total['recorded_wall'])
        totals[segment] = total
    return dict(family_budget_bytes=FAMILY_BUDGET, segments=totals, blocks=blocks)


def main():
    result = summarize(Path(sys.argv[1]))
    with Path(sys.argv[2]).open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    for segment, row in result['segments'].items():
        print(segment, round(row['recorded_wall'], 2), round(row['prepare'], 2),
              round(row['observed_decode_plus_all_identity_share'] * 100, 2),
              round(row['bounded_decode_plus_all_identity_share'] * 100, 2))


if __name__ == '__main__':
    main()
