"""Merge the per-file inventory with frozen-map identity and print the funnel."""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from learning.maps import SPLITS  # noqa: E402

TIER = {}
for fmt, parts in SPLITS.items():
    for part, names in parts.items():
        for name in names:
            TIER.setdefault(name, {})[fmt] = part
FROZEN = {name for by_fmt in TIER.values() for name in by_fmt}


def table(counter, limit=20, width=40):
    total = sum(counter.values()) or 1
    for key, count in counter.most_common(limit):
        print(f'  {str(key)[:width]:<{width}} {count:>7}  {count/total:6.1%}')


def games(rows):
    """Collapse files of one game: same board, config and 8-command prefix."""
    clusters = defaultdict(list)
    for r in rows:
        prefix = r.get('prefixes') or []
        key = (r['map'], r['version'], r['era_id'], tuple(sorted(r['teams'])),
               tuple(zip(r.get('factions', ()), ())) if r.get('factions') else (),
               tuple(prefix[:8]) if len(prefix) >= 8 else ('short', r['source']))
        clusters[key].append(r)
    return clusters


def main():
    inventory = [json.loads(line) for line in (ROOT / 'tmp/replay_inventory.jsonl').open(encoding='utf-8')]
    maps = {row['source']: row for row in
            (json.loads(line) for line in (ROOT / 'tmp/map_all.jsonl').open(encoding='utf-8'))}
    for row in inventory:
        name = row['source'].split('/')[-1]
        hit = maps.get(name, {})
        row['map'] = hit.get('map')
        row['map_why'] = hit.get('why')
        row['factions'] = [s['faction'] for s in row.get('players') or []]
        row['all_human'] = bool(row.get('players')) and row['human_sides'] == len(row['players'])

    print(f"files {len(inventory)}; parsed {sum(r['status']=='candidate' for r in inventory)}")
    print('\n== map identity vs ten frozen boards')
    table(Counter(r['map_why'] for r in inventory), 6)
    table(Counter(r['map'] for r in inventory if r['map']), 12)
    frozen = [r for r in inventory if r['map']]
    print(f'\nfrozen-map files {len(frozen)}')

    def gate(r):
        if r['status'] != 'candidate':
            return r['status']
        if r.get('campaign_type') != 'multiplayer':
            return 'not multiplayer'
        if not r['map']:
            return 'map not frozen'
        if r.get('era_id') != 'era_default':
            return 'custom era'
        if r.get('scenario_addon'):
            return 'addon scenario'
        if r.get('mp_addons') or r.get('active_mods') or r.get('mod_defines'):
            return 'required addons/mods'
        if r.get('version') != '1.18.8':
            return 'version != 1.18.8'
        return 'eligible'
    print('\n== eligibility funnel (strict contract)')
    table(Counter(gate(r) for r in inventory), 10)
    shape = [r for r in inventory if gate(r) == 'version != 1.18.8']
    print(f'\nfrozen-map standard-era mainline files blocked only by version: {len(shape)}')
    print('  versions', Counter(r['version'] for r in shape).most_common())
    print('  maps', Counter(r['map'] for r in shape).most_common())
    print('  era', Counter(r['era_id'] for r in shape).most_common())
    print('  human/ai', Counter((r['human_sides'], r['ai_sides']) for r in shape).most_common(8))
    print('  all-human files', sum(r['all_human'] for r in shape))
    print('  has replay_start', sum(r['has_start'] for r in shape))
    print('  end marker', sum(r['end_marker'] for r in shape))
    print('  actions', sorted(r['actions'] for r in shape)[:: max(1, len(shape) // 10)])
    print('  actions>=20', sum(r['actions'] >= 20 for r in shape))

    live = [r for r in shape if r['all_human'] and r['actions'] >= 20]
    print(f'\n== all-human with >=20 decisions: {len(live)} files')
    clusters = games(live)
    best = [max(group, key=lambda r: (r['semantic'], r['actions'])) for group in clusters.values()]
    print(f'   unique games {len(best)}')
    print('   per-game decisions', sorted(r['actions'] for r in best)[:: max(1, len(best) // 10)])
    print('   per-game by map', Counter(r['map'] for r in best).most_common())
    print('   per-game by version', Counter(r['version'] for r in best).most_common())
    print('   per-game version x map', Counter((r['version'], r['map']) for r in best).most_common())
    print('   files per cluster', Counter(len(g) for g in clusters.values()).most_common(8))
    print('   total decisions', sum(r['actions'] for r in best))
    print('   planned split tier',
          Counter((TIER[r['map']].get('duel') or TIER[r['map']].get('ffa4'), r['map']) for r in best).most_common(12))
    print('   captures needed (games with replay_start)',
          sum(r['has_start'] for r in best), 'of', len(best))

    print('\n== 20 longest all-human frozen-map games')
    for r in sorted(best, key=lambda r: -r['actions'])[:20]:
        print(f"  {r['actions']:>5} acts {r['version']:>8} {r['map']:<22} start={r['has_start']!s:<5}"
              f" end={r['end_marker']!s:<5} {r['source']}")

    out = ROOT / 'tmp/replay_candidates.json'
    out.write_text(json.dumps([r['source'] for r in best], indent=0), encoding='utf-8')
    print(f'\nwrote {out}')


if __name__ == '__main__':
    main()
