"""Inventory the 2026 archive months without running Wesnoth: one pass, map identity included.

Reads serialized WML as data only; no Lua is executed. Writes one JSON line per
file so later steps can re-analyse without decompressing again.
"""
from __future__ import annotations

import bz2
import hashlib
import glob
import json
import os
import re
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from learning.replay_curate import (COSMETIC, DECISIONS, Node, controller_changes, parse_wml,
                                   unpack)  # noqa: E402

BASE = ROOT / 'data/replays'
MONTHS = ('202607', '202608', '202609')
PREFIX_DEPTH = 256
SKIP = {'sent', 'undo'}


def dig(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()[:16]


def canonical(node):
    return [node.tag, sorted(node.attrs.items()), [canonical(c) for c in node.children]]



OFF_MAP = '_off^_usr'
FROZEN = {}
for _path in sorted(glob.glob(str(ROOT / 'data/rules/1.18.8/maps/*.json'))):
    _data = json.load(open(_path, encoding='utf-8'))
    _cells = [re.sub(r'^\d+ ', '', c.strip()) for row in _data['board']['terrain'] for c in row]
    FROZEN[tuple(sorted(Counter(c for c in _cells if c != OFF_MAP).items()))] = _data['name']


def map_identity(scenario):
    if scenario is None:
        return None, 'no_map'
    rows = [[re.sub(r'^\d+ ', '', c.strip()) for c in line.split(',')]
            for line in scenario.attrs.get('map_data', '').split('\n') if line.strip()]
    if not rows:
        return None, 'no_map'
    for why, cells in (('exact', [c for row in rows for c in row]),
                       ('ring_stripped', [c for row in rows[1:-1] for c in row[1:-1]])):
        name = FROZEN.get(tuple(sorted(Counter(c for c in cells if c != OFF_MAP).items())))
        if name:
            return name, why
    return None, 'other_map'


def scan(path_text):
    path = Path(path_text)
    row = dict(source=str(path.relative_to(BASE)).replace('\\', '/'))
    t0 = time.perf_counter()
    try:
        packed, raw, compression = unpack(path)
        text = raw.decode('utf-8-sig')
        root = parse_wml(text)
    except Exception as exc:  # noqa: BLE001 - record, never crash the sweep
        row.update(status='parse_error', error=f'{type(exc).__name__}: {exc}')
        return row
    row.update(bytes=len(packed), raw_bytes=len(raw), compression=compression,
               source_sha256=hashlib.sha256(packed).hexdigest()[:16])
    row.update({k: root.attrs.get(k, '') for k in
                ('version', 'campaign_type', 'campaign', 'era_id', 'active_mods',
                 'mod_defines', 'label', 'core', 'abbrev')})
    start = root.first('replay_start')
    # Server archives split the history over a leading [replay] holding only
    # [upload_log] and a later [replay] with the commands; merge all of them.
    replays = root.all('replay')
    snapshot = root.first('snapshot')
    scenario = root.first('scenario')
    carry = root.first('carryover_sides_start')
    mp = root.first('multiplayer') or Node('multiplayer')
    row['replay_blocks'] = len(replays)
    row.update(has_start=start is not None, has_replay=bool(replays),
               has_scenario=scenario is not None, has_snapshot=snapshot is not None,
               has_carryover=carry is not None,
               initial_seed=(carry.attrs.get('random_seed') if carry is not None else None)
               or (start.attrs.get('random_seed') if start is not None else '') or '')
    row.update(mp_scenario=mp.attrs.get('mp_scenario', ''),
               mp_era=mp.attrs.get('mp_era', ''), mp_fog=mp.attrs.get('mp_fog', ''),
               mp_shroud=mp.attrs.get('mp_shroud', ''), mp_turns=mp.attrs.get('mp_num_turns', ''),
               mp_countdown=mp.attrs.get('mp_countdown', ''),
               observer=mp.attrs.get('observer', ''),
               mp_addons=[a.attrs.get('id', '') for a in mp.all('addon')
                          if a.attrs.get('required') in {'yes', 'true', '1'} and a.attrs.get('id') != 'mainline'],
               mp_addons_any=[a.attrs.get('id', '') for a in mp.all('addon') if a.attrs.get('id')])
    if scenario is not None:
        row.update(scenario_id=scenario.attrs.get('id', ''),
                   scenario_addon=scenario.attrs.get('addon_id', ''),
                   scenario_turns=scenario.attrs.get('turns', ''),
                   xp_mod=scenario.attrs.get('experience_modifier', ''),
                   map_sha=hashlib.sha256(scenario.attrs.get('map_data', '').encode()).hexdigest()[:16],
                   has_mod_events=scenario.attrs.get('has_mod_events', ''))
    sides = []
    source_sides = (start or scenario or Node('none'))
    for side in source_sides.all('side'):
        sides.append({k: side.attrs.get(k, '') for k in
                      ('side', 'controller', 'allow_player', 'current_player', 'player_id',
                       'faction', 'team_name', 'gold', 'recruit')})
        sides[-1]['recruit'] = sides[-1]['recruit'][:120]
    row['sides'] = sides
    row['players'] = [s for s in sides if s['allow_player'] not in {'no', 'false', '0'}]
    row['human_sides'] = sum(s['controller'] in {'human', 'network'} for s in row['players'])
    row['ai_sides'] = sum(s['controller'] == 'ai' for s in row['players'])
    row['teams'] = [s['team_name'] for s in row['players']]
    if not replays or (not row['has_start'] and not row['has_scenario']):
        row['status'] = 'no_replay_history'
        return row
    tags = Counter()
    intents = Counter()
    prefixes = []
    from_sides = Counter()
    dependent = cosmetic = undos = 0
    partial_last = False
    controllers = Counter()
    commands_all = [c for node in replays for c in node.all('command')]
    for command in commands_all:
        kids = [n for n in command.children if n.tag not in COSMETIC]
        if not kids:
            cosmetic += 1
            continue
        tags.update(n.tag for n in kids)
        if command.attrs.get('dependent') in {'yes', 'true', '1'}:
            dependent += 1
        elif command.attrs.get('undo') in {'yes', 'true', '1'}:
            undos += 1
        from_sides[command.attrs.get('from_side', '')] += 1
        if len(prefixes) < PREFIX_DEPTH:
            stable = Node('command', {k: v for k, v in command.attrs.items() if k not in SKIP}, kids)
            prefixes.append(dig(canonical(stable)))
        for n in kids:
            if n.tag in DECISIONS:
                intents[n.tag] += 1
            if 'controller' in n.tag or n.tag in {'side_drop', 'change_side'}:
                controllers[n.tag] += 1
        checks = [n for n in kids if n.tag == 'checkup']
        partial_last = bool(checks) and all(not n.attrs and not n.children for n in checks)
    row.update(commands=len(commands_all), semantic=sum(tags.values()),
               dependent=dependent, cosmetic=cosmetic, undo_commands=undos,
               intents=dict(intents), actions=sum(intents.values()),
               command_tags=dict(tags), from_sides=dict(from_sides),
               controller_commands=dict(controllers),
               partial_last=partial_last, prefixes=prefixes,
               end_marker=any(tags[t] for t in ('surrender', 'endlevel', 'game_end')),
               end_turn=tags['end_turn'])
    row['map'], row['map_why'] = map_identity(scenario)
    row['controller_changes'] = controller_changes(commands_all,
        [dict(s, player=s['current_player'] or s['player_id']) for s in row['sides']])
    row['status'] = 'candidate'
    row['millis'] = round((time.perf_counter() - t0) * 1000, 1)
    return row


def main():
    files = sorted(str(p) for month in MONTHS for p in (BASE / month).rglob('*.bz2'))
    out = ROOT / 'tmp/replay_inventory_2026q3.jsonl'
    started = time.time()
    # The sweep is long enough to be interrupted; resume after the rows already
    # on disk instead of decompressing a month again.
    done = set()
    if out.exists():
        done = {json.loads(line)['source'] for line in out.open(encoding='utf-8')}
        files = [f for f in files
                 if str(Path(f).relative_to(BASE)).replace('\\', '/') not in done]
        print(f'resuming with {len(files)} files; {len(done)} already on disk', flush=True)
    with out.open('a', encoding='utf-8') as stream, ProcessPoolExecutor(max_workers=16) as pool:
        for index, row in enumerate(pool.map(scan, files, chunksize=8), 1):
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            if index % 2000 == 0:
                print(f'{index}/{len(files)} {time.time()-started:.0f}s', flush=True)
    print(f'wrote {out} files={len(files)} in {time.time()-started:.0f}s')


if __name__ == '__main__':
    main()
