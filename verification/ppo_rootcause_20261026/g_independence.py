"""Scenario-split independence and validation trend over versions.

Part 1 groups every collected game by its physical scenario (map, factions,
opponents) and reports how many scenarios appear on both sides of the seed-based
split. Part 2 prints the validation/trend comparison series per version.
"""
import collections
import glob
import gzip
import json
import os
import sys

sys.path.insert(0, os.environ.get('WL_SOURCE', 'WesnothLearning'))
from learning.rowpack import row_meta          # noqa: E402

RUN = os.environ.get('WL_RUN', '.')


def shard_games(path, limit=400):
    seen = {}
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for index, line in enumerate(stream):
            if index >= limit:
                break
            try:
                meta = row_meta(line)
            except Exception:
                continue
            key = (meta.get('game_family'), meta.get('game_id'), meta.get('side'))
            if key in seen:
                continue
            seen[key] = dict(family=meta.get('game_family'), split=meta.get('split'),
                             map=meta.get('map'), map_sha256=meta.get('map_sha256'),
                             faction=meta.get('faction'), opponents=tuple(meta.get('opponents') or ()),
                             teacher=bool(meta.get('teacher')), engine=meta.get('engine_id'))
    return list(seen.values())


def independence(fmt):
    games = []
    patterns = ['%s/%s/data/teacher-*-%s-*.jsonl.gz' % (RUN, fmt, fmt)]
    if os.environ.get('WL_ROLLOUTS'):
        patterns.append('%s/%s/data/rollout-*-%s-*.jsonl.gz' % (RUN, fmt, fmt))
    for pattern in patterns:
        paths = sorted(glob.glob(pattern))
        cap = int(os.environ.get('WL_MAXFILES', '40'))
        picked = paths[:cap] + paths[-cap:] if len(paths) > cap else paths
        for path in picked:
            games.extend(shard_games(path))
    print('%s games %d families %d' % (fmt, len(games), len({g['family'] for g in games})))
    family_splits = collections.defaultdict(set)
    for game in games:
        family_splits[game['family']].add(game['split'])
    print('  families spanning both splits %d of %d' % (
        sum(1 for v in family_splits.values() if len(v) > 1), len(family_splits)))
    scenarios = collections.defaultdict(lambda: collections.defaultdict(set))
    for game in games:
        key = (game['map_sha256'], game['faction'], game['engine'])
        scenarios[key][game['split']].add(game['family'])
    both = {k: v for k, v in scenarios.items() if len(v) > 1}
    print('  physical scenarios %d, scenarios on both splits %d' % (len(scenarios), len(both)))
    multi = collections.Counter(len(v) for v in scenarios.values())
    print('  scenario split composition', dict(multi))
    counts = sorted((len(v) for v in scenarios.values()), reverse=True)[:5]
    print('  families per scenario (top 5)', counts)
    train_families = {g['family'] for g in games if g['split'] == 'train'}
    valid_families = {g['family'] for g in games if g['split'] == 'validation'}
    print('  families train %d validation %d' % (len(train_families), len(valid_families)))
    return games


def trend(fmt):
    series = []
    for path in sorted(glob.glob('%s/%s/validation/v*.json' % (RUN, fmt))):
        try:
            payload = json.load(open(path, encoding='utf-8'))
        except Exception:
            continue
        cells = payload.get('comparison') or payload.get('formats') or {}
        cell = cells.get(fmt) if isinstance(cells, dict) else None
        if not isinstance(cell, dict):
            cell = payload if 'difference' in payload else None
        if not cell:
            continue
        series.append((payload.get('version') or int(os.path.basename(path)[1:7]),
                       cell.get('difference'), cell.get('blocks'), cell.get('status')))
    series.sort()
    print('%s validation series (%d points)' % (fmt, len(series)))
    for version, difference, blocks, status in series:
        print('   v%-4s diff %-10s blocks %-3s %s' % (
            version, 'None' if difference is None else '%+.4f' % difference, blocks, status))


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'independence'
    for fmt in ('duel', 'ffa4', 'team2v2'):
        if mode == 'independence':
            independence(fmt)
        else:
            trend(fmt)
