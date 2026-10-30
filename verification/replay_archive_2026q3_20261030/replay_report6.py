"""Funnel and candidate selection for the 2026 archive months."""
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


def table(counter, limit=20, width=42):
    total = sum(counter.values()) or 1
    for key, count in counter.most_common(limit):
        print(f'  {str(key)[:width]:<{width}} {count:>7}  {count/total:6.1%}')


def clusters_of(rows):
    clusters = defaultdict(list)
    for r in rows:
        prefix = r.get('prefixes') or []
        key = (r['map'], r['version'], r['era_id'], tuple(sorted(r['teams'])),
               tuple(s['faction'] for s in r.get('players') or []),
               tuple(prefix[:8]) if len(prefix) >= 8 else ('short', r['source']))
        clusters[key].append(r)
    return clusters


def main():
    inventory = [json.loads(line) for line in
                 (ROOT / 'tmp/replay_inventory_2026q3.jsonl').open(encoding='utf-8')]
    parsed = [r for r in inventory if r['status'] == 'candidate']
    for row in inventory:
        row['all_human'] = bool(row.get('players')) and row['human_sides'] == len(row['players'])
        row['clean_provenance'] = not row.get('controller_changes')
    print(f"files {len(inventory)}; parsed {len(parsed)}")
    print('\n== version')
    table(Counter(r.get('version') for r in inventory), 12)
    print('\n== era')
    table(Counter(r.get('era_id') for r in inventory), 10)
    print('\n== gates, in learning/human.compatibility order')
    table(Counter(r.get('map_why') or 'n/a' for r in inventory), 8)
    print('\n== frozen map identity (ten boards)')
    table(Counter(r.get('map') for r in parsed if r.get('map')), 12)

    def gate(r):
        if r['status'] != 'candidate':
            return 'malformed'
        if r.get('campaign_type') != 'multiplayer':
            return 'not multiplayer'
        if r.get('era_id') != 'era_default':
            return 'custom era'
        if r.get('scenario_addon'):
            return 'addon scenario'
        if r.get('mp_addons') or r.get('active_mods') or r.get('mod_defines'):
            return 'required addons/mods'
        if not r.get('map'):
            return 'map not frozen'
        if r.get('version') != '1.18.8':
            return 'version != 1.18.8'
        if not r.get('has_start'):
            return 'missing [replay_start]'
        return 'eligible'
    print('\n== eligibility funnel (strict contract)')
    table(Counter(gate(r) for r in inventory), 10)
    shape = [r for r in parsed if gate(r) in ('version != 1.18.8', 'missing [replay_start]')]
    print(f'\nfrozen-map standard-era mainline files: {len(shape)}')
    print('  gates', Counter(gate(r) for r in shape).most_common())
    print('  versions', Counter(r['version'] for r in shape).most_common())
    print('  maps', Counter(r['map'] for r in shape).most_common())
    print('  all-human', sum(r['all_human'] for r in shape))
    print('  clean provenance', sum(r['clean_provenance'] for r in shape))
    print('  has replay_start', sum(r['has_start'] for r in shape))
    print('  end marker', sum(r['end_marker'] for r in shape))
    print('  actions>=20', sum(r['actions'] >= 20 for r in shape))

    live = [r for r in shape if r['all_human'] and r['actions'] >= 20]
    clusters = clusters_of(live)
    best = [max(g, key=lambda r: (r['semantic'], r['actions'])) for g in clusters.values()]
    clean = [r for r in best if r['clean_provenance']]
    print(f'\n== all-human, >=20 decisions: {len(live)} files, {len(best)} unique games')
    print('   decisions total', sum(r['actions'] for r in best),
          'clean', sum(r['actions'] for r in clean))
    print('   clean games', len(clean))
    print('   formats', Counter(fmt(r) for r in best).most_common(),
          'clean', Counter(fmt(r) for r in clean).most_common())
    print('   versions', Counter(r['version'] for r in best).most_common())
    print('   maps', Counter(r['map'] for r in best).most_common(), '\n   clean', Counter(r['map'] for r in clean).most_common())
    print('   files per cluster', Counter(len(g) for g in clusters.values()).most_common(8))
    print('   end marker', sum(r['end_marker'] for r in best), 'clean', sum(r['end_marker'] for r in clean))
    print('   captures needed', sum(r['has_start'] for r in best), 'of', len(best))
    print('   split tier', Counter(TIER[r['map']].get('duel') or TIER[r['map']].get('ffa4') for r in best).most_common())

    out = ROOT / 'tmp/replay_candidates_2026q3.json'
    out.write_text(json.dumps([r['source'] for r in best], indent=0), encoding='utf-8')
    print(f'\nwrote {out}')


def fmt(row):
    players = row.get('players') or []
    teams = Counter(p['team_name'] for p in players)
    if len(players) == 2 and len(teams) == 2:
        return 'duel'
    if len(players) == 4 and len(teams) == 2 and sorted(teams.values()) == [2, 2]:
        return 'team2v2'
    if len(teams) == len(players) and len(players) > 2:
        return f'ffa{len(players)}'
    return 'other'


if __name__ == '__main__':
    main()
