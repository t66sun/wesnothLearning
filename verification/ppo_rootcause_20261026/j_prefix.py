"""Compare stored behaviour logp against replay for every row, grouped by prefix shape."""
import argparse
import gzip
import os
import sys

import torch

SRC = os.environ['WL_SOURCE']
RUN = os.environ['WL_RUN']
sys.path.insert(0, SRC)
from learning.rowpack import unpack_line  # noqa: E402
from learning.model import batch  # noqa: E402
from learning.export import load_model  # noqa: E402
from learning.sequences import attach_histories  # noqa: E402


def rows(path):
    out = []
    with gzip.open(path, 'rt', encoding='utf-8') as handle:
        for line in handle:
            line = line.strip()
            if line:
                out.append(unpack_line(line)[0])
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--format', default='duel')
    parser.add_argument('--version', type=int, default=99)
    parser.add_argument('--mode', default='sample')
    parser.add_argument('--games', type=int, default=4)
    args = parser.parse_args()
    data = []
    for index in range(args.games):
        data.extend(rows('%s/%s/data/rollout-%05d-%s-g%d.jsonl.gz' % (RUN, args.format, args.version, args.format, index)))
    print('rows', len(data), 'decision range', min(r['decision'] for r in data), max(r['decision'] for r in data))
    prepared = attach_histories(list(data))
    path = '%s/%s/policies/v%06d-%s/model.pt' % (RUN, args.format, args.version, args.mode)
    model, _state = load_model(path, args.format)
    model.eval()
    logps = []
    with torch.no_grad():
        for start in range(0, len(prepared), 32):
            chunk = prepared[start:start + 32]
            logits, _value = model(*batch(chunk, 'cpu'))
            logp = torch.log_softmax(logits, -1)
            index = torch.tensor([r['choice'] for r in chunk])
            logps.extend(float(v) for v in logp.gather(1, index[:, None]).squeeze(1))
    buckets = {}
    worst = []
    for row, logp in zip(prepared, logps):
        diff = abs(logp - row['log_probability'])
        key = (row['ctrl_committed'] if 'ctrl_committed' in row else row.get('committed'), len(row['_history']), row['turn'])
        buckets.setdefault((len(row['_history']), row.get('committed')), []).append(diff)
        worst.append((diff, row['turn'], row['decision'], len(row['_history']), row['log_probability'], logp))
    print('overall max %.6f mean %.6f' % (max(buckets and [max(v) for v in buckets.values()]), sum(sum(v) for v in buckets.values()) / len(logps)))
    for key in sorted(buckets):
        values = buckets[key]
        print('  history %2d committed %-5s n %3d max %.3e mean %.3e' % (key[0], key[1], len(values), max(values), sum(values) / len(values)))
    worst.sort(reverse=True)
    for item in worst[:6]:
        print('  worst diff %.3e turn %d decision %d hist %d recorded %.4f replay %.4f' % item)


if __name__ == '__main__':
    main()
