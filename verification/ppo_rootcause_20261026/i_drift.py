"""Measure behavioural drift between exported checkpoints on one frozen batch.

KL is computed over the full candidate distribution (all finite logits), not the
sampled action, and argmax agreement is the fraction of rows whose greedy choice
matches the earliest exported version.
"""
import argparse
import glob
import gzip
import os
import re
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


def distribution(model, data):
    out = []
    with torch.no_grad():
        for start in range(0, len(data), 32):
            chunk = data[start:start + 32]
            logits, _value = model(*batch(chunk, 'cpu'))
            logp = torch.log_softmax(logits, -1)
            p = logp.exp()
            p = torch.where(torch.isfinite(logp), p, torch.zeros_like(p))
            p = p / p.sum(-1, keepdim=True).clamp(min=1e-30)
            logp = torch.where(torch.isfinite(logp), logp, torch.zeros_like(logp))
            out.append((p, logp))
    return torch.cat([a for a, _ in out]), torch.cat([b for _, b in out])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--format', default='duel')
    parser.add_argument('--version', type=int, default=99)
    parser.add_argument('--games', type=int, default=4)
    args = parser.parse_args()
    data = []
    for index in range(args.games):
        data.extend(rows('%s/%s/data/rollout-%05d-%s-g%d.jsonl.gz' % (RUN, args.format, args.version, args.format, index)))
    data = attach_histories([r for r in data if r['split'] == 'train'])
    print('rows', len(data))
    dirs = {}
    for path in glob.glob('%s/%s/policies/*/model.pt' % (RUN, args.format)):
        match = re.search(r'/v(\d{6})-greedy/model\.pt$', path.replace('\\', '/'))
        if match:
            dirs[int(match.group(1))] = path
    versions = sorted(dirs)
    if len(versions) > 8:
        versions = sorted({versions[0], versions[-1]} | {min(versions, key=lambda v: abs(v - t)) for t in (100, 200, 300, 400)})
    print('versions', versions, 'base', versions[0])
    base = None
    for version in versions:
        model, _state = load_model(dirs[version], args.format)
        model.eval()
        p, logp = distribution(model, data)
        choice = logp.argmax(-1)
        entropy = float((-(p * logp).sum(-1)).mean())
        line = 'v%-4d entropy %.4f' % (version, entropy)
        if base is None:
            base = (p, logp, choice)
            line += '  (reference)'
        else:
            kl = float((base[0] * (base[1] - logp)).sum(-1).mean())
            total = float(((p + base[0]) * 0.5 * ((logp - base[1]))).sum(-1).mean())
            agree = float((choice == base[2]).float().mean())
            line += '  KL(v%d||v%d) %.6f  symmetric %.6f  changed decisions %.2f%%' % (
                versions[0], version, kl, abs(total), 100 * (1 - agree))
        print(line)


if __name__ == '__main__':
    main()
