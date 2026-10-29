"""Frozen-map identity for every archived replay, independent of filename.

Server archives pad ``map_data`` with a one-cell ring that clones the terrain
next to the board edge, and some mark the off-board area ``_off^_usr``. The
identity test therefore compares the terrain multiset of the board itself and
of the board with one ring removed, against the frozen 1.18.8 boards.
"""
from __future__ import annotations

import glob
import json
import re
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from learning.replay_curate import parse_wml, unpack  # noqa: E402

BASE = ROOT / 'data/replays/202412'
OFF_MAP = '_off^_usr'


def norm(cell):
    return re.sub(r'^\d+ ', '', cell.strip())


def key(cells):
    return tuple(sorted(Counter(cells).items()))


FROZEN = {}
for path in glob.glob(str(ROOT / 'data/rules/1.18.8/maps/*.json')):
    data = json.load(open(path, encoding='utf-8'))
    cells = [norm(c) for row in data['board']['terrain'] for c in row]
    FROZEN[key(c for c in cells if c != OFF_MAP)] = data['name']


def match(path_text):
    path = Path(path_text)
    try:
        _, raw, _ = unpack(path)
        root = parse_wml(raw.decode('utf-8-sig'))
        scenario = root.first('scenario')
        rows = [[norm(c) for c in row.split(',')]
                for row in (scenario.attrs.get('map_data', '').split('\n') if scenario else [])
                if row.strip()]
    except Exception:  # noqa: BLE001
        return dict(source=path.name, map=None, why='parse_error')
    if not rows:
        return dict(source=path.name, map=None, why='no_map')
    for why, cells in (('exact', [c for row in rows for c in row]),
                       ('ring_stripped', [c for row in rows[1:-1] for c in row[1:-1]])):
        name = FROZEN.get(key(c for c in cells if c != OFF_MAP))
        if name:
            return dict(source=path.name, map=name, why=why)
    return dict(source=path.name, map=None, why='other_map')


def main():
    files = sorted(str(p) for p in BASE.rglob('*.bz2'))
    out = ROOT / 'tmp/map_all.jsonl'
    with out.open('w', encoding='utf-8') as stream, ProcessPoolExecutor(max_workers=16) as pool:
        for row in pool.map(match, files, chunksize=16):
            stream.write(json.dumps(row) + '\n')
    rows = [json.loads(line) for line in out.open(encoding='utf-8')]
    print('files', len(rows))
    print('why', Counter(r['why'] for r in rows).most_common())
    print('maps', Counter(r['map'] for r in rows if r['map']).most_common())


if __name__ == '__main__':
    main()
