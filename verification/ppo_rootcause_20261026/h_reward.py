"""Hand-check own-turn GAE, potential shaping and truncation bootstrap on a frozen PPO batch."""
import argparse
import collections
import gzip
import json
import math
import os
import sys

SRC = os.environ['WL_SOURCE']
RUN = os.environ['WL_RUN']
sys.path.insert(0, SRC)
from learning.rowpack import unpack_line  # noqa: E402
from learning import rewards  # noqa: E402
from learning.data import advantages  # noqa: E402


def rows(path):
    out = []
    with gzip.open(path, 'rt', encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if line:
                row, _ = unpack_line(line)
                out.append(row)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--format', default='duel')
    parser.add_argument('--version', type=int, default=99)
    parser.add_argument('--games', type=int, default=4)
    args = parser.parse_args()
    batch = []
    for index in range(args.games):
        path = '%s/%s/data/rollout-%05d-%s-g%d.jsonl.gz' % (RUN, args.format, args.version, args.format, index)
        batch.extend(rows(path))
    print('rows', len(batch), 'games', len({r['game_id'] for r in batch}))
    reward = [r['reward'] for r in batch]
    print('reward mean %.6f min %.6f max %.6f nonzero %d/%d' % (
        sum(reward) / len(reward), min(reward), max(reward), sum(1 for v in reward if abs(v) > 1e-12), len(reward)))
    pieces = collections.Counter()
    totals = collections.Counter()
    for row in batch:
        _total, parts = rewards.transition_reward(row['reward_raw'], row.get('reward_after', row['reward_raw']),
                                          row['reward_config'], terminal_reward=0., terminal=False, delta_turn=1, components=True)
        for key, value in parts.items():
            pieces[key] += abs(value)
            totals[key] += value
    total = sum(pieces.values()) or 1.
    for key in sorted(pieces):
        print('  piece %-9s abs_sum %10.4f share %.3f signed %10.4f' % (key, pieces[key], pieces[key] / total, totals[key]))
    trunc = [r for r in batch if r.get('truncated')]
    print('truncated rows', len(trunc), 'with bootstrap', sum(1 for r in trunc if r.get('bootstrap_value') is not None))
    adv, ret = advantages(batch)
    print('advantage mean %.6f std %.6f min %.3f max %.3f' % (
        sum(adv) / len(adv), (sum((a - sum(adv) / len(adv)) ** 2 for a in adv) / len(adv)) ** .5, min(adv), max(adv)))
    # hand-check one short game sequence
    by_game = collections.defaultdict(list)
    for index, row in enumerate(batch):
        by_game[(row['game_id'], row['side'])].append(index)
    key = min(by_game, key=lambda k: len(by_game[k]))
    seq = sorted(by_game[key], key=lambda i: (batch[i]['turn'], batch[i]['decision']))
    print('hand check game %s side %s rows %d' % (key[0], key[1], len(seq)))
    for index in seq:
        row = batch[index]
        print('   turn %3d dec %2d reward %+.6f raw %s after %s value %+.6f adv %+.6f ret %+.6f trunc %s boot %s' % (
            row['turn'], row['decision'], row['reward'],
            json.dumps(row['reward_raw'], sort_keys=True), json.dumps(row.get('reward_after'), sort_keys=True),
            row['value'], adv[index], ret[index], bool(row.get('truncated')), row.get('bootstrap_value')))
    # independent recomputation of the last row: gae at terminal = delta
    last = batch[seq[-1]]
    print('last row expected delta = reward + 0 - value = %.6f ; gae %.6f' % (
        last['reward'] - last['value'], adv[seq[-1]]))


if __name__ == '__main__':
    main()
