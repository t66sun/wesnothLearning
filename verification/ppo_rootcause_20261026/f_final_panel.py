"""Final-panel identity audit: how many distinct scenario blocks does a panel hold?

Reads only the run's jobs.jsonl; prints per-block score and the identity tuple of
every final-panel job, then counts distinct scenario keys.
"""
import collections
import json
import os
import sys

RUN = os.environ.get('WL_RUN', '.')
POINTS = {'win': 3., 'draw': 1., 'loss': 0.}


def official_score(result, side):
    bots = result.get('bots') or []
    sides = result.get('sides') or {}
    if 'rank_points' in result and result['rank_points']:
        points = result['rank_points'].get(str(side), 0.)
        return float(points) / max(1, len(bots) - 1)
    winner = result.get('winner')
    return 3. if winner == side else 1. if winner in (0, None) else 0.


def panel(fmt, label_prefix):
    path = '%s/%s/jobs.jsonl' % (RUN, fmt)
    jobs = []
    with open(path, 'r', encoding='utf-8') as stream:
        for line in stream:
            try:
                record = json.loads(line)
            except Exception:
                continue
            meta = record.get('meta') or {}
            if not str(meta.get('label', '')).startswith(label_prefix):
                continue
            jobs.append(record)
    blocks = collections.defaultdict(list)
    for record in jobs:
        meta = record['meta']
        meta['_score'] = sum(official_score(record['result'], side)
                             for side in meta['policy_sides']) / len(meta['policy_sides'])
        meta['_seed'] = record.get('seed', meta.get('seed'))
        meta['_factions'] = tuple(record['result'].get('factions') or ())
        meta['_turns'] = record['result'].get('turns')
        meta['_reason'] = record['result'].get('reason')
        blocks[meta['block']].append(meta)
    print('%s %-6s jobs %d blocks %d' % (fmt, label_prefix, len(jobs), len(blocks)))
    scores = {}
    keys = collections.defaultdict(set)
    for block in sorted(blocks):
        members = blocks[block]
        scores[block] = sum(m['_score'] for m in members) / len(members)
        for m in members:
            keys[block].add((m.get('map_sha256'), m['_factions'], tuple(m.get('bots') or ()),
                             m.get('control'), m['_seed']))
    ordered = [scores[b] for b in sorted(scores)]
    print('  per-block score', ['%.4f' % s for s in ordered])
    flat = [
        tuple((m.get('map_sha256'), m['_factions'], tuple(m.get('bots') or ()), m.get('control'),
               m.get('rotation'), m.get('context'), m['_seed'])
              for m in sorted(blocks[b], key=lambda m: (m.get('rotation'), m.get('context') or '')))
        for b in sorted(blocks)]
    for block in sorted(blocks)[:8]:
        for m in sorted(blocks[block], key=lambda m: (m.get('rotation'), m.get('context') or '')):
            print('  block %2d rot %s ctx %-8s map %-8s seed %-10s factions %-24s bots %d turns %s score %.4f'
                  % (block, m.get('rotation'), m.get('context'), m.get('map'),
                     m['_seed'], ','.join(x[:4] for x in m['_factions']), len(m.get('bots') or []),
                     m['_turns'], m['_score']))
    seen = {}
    periods = []
    for period in range(1, len(flat) + 1):
        if all(flat[i] == flat[i - period] for i in range(period, len(flat))):
            periods.append(period)
            break
    print('  distinct scenario blocks %d of %d, minimum repeat period %s'
          % (len(set(flat)), len(flat), periods[0] if periods else 'none'))
    counts = collections.Counter(flat)
    print('  block multiplicity', sorted(counts.values(), reverse=True))
    # exact score repetition
    score_period = None
    for period in range(1, len(ordered) + 1):
        if all(abs(ordered[i] - ordered[i - period]) < 1e-9 for i in range(period, len(ordered))):
            score_period = period
            break
    print('  score repeat period %s  distinct scores %d' % (score_period, len(set(round(s, 9) for s in ordered))))


if __name__ == '__main__':
    for fmt in ('duel', 'ffa4', 'team2v2'):
        panel(fmt, sys.argv[1] if len(sys.argv) > 1 else 'final')
