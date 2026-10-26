"""Zero-step behaviour replay and gradient decomposition on one frozen PPO batch.

Modes
  replay  recompute the recorded behaviour log-probability and value with the
          frozen weights that produced the batch; no parameter changes.
  grad    decompose the exact PPO objective of the same batch into policy,
          value, entropy and BC-rehearsal gradients and compare directions.

Reads the run directory read-only; writes nothing.
"""
import argparse
import gzip
import json
import math
import os
import sys

import torch

sys.path.insert(0, os.environ.get('WL_SOURCE', '.'))
from learning.data import advantages, make_bc_sampler            # noqa: E402
from learning.model import batch                                  # noqa: E402
from learning.rowpack import unpack_line                          # noqa: E402
from learning.sequences import attach_histories, training_windows  # noqa: E402

RUN = os.environ.get('WL_RUN', '.')


def load_rows(paths):
    rows = []
    for path in paths:
        with gzip.open(path, 'rt', encoding='utf-8') as stream:
            for line in stream:
                row, _ = unpack_line(line)
                if row.get('faults'):
                    continue
                rows.append(row)
    return rows


def load_model(fmt, version):
    from learning.export import load_model as loader
    path = '%s/%s/policies/v%06d-sample/model.pt' % (RUN, fmt, version)
    model, _ = loader(path, fmt, 'cpu')
    model.eval()
    return model, path


def replay(args):
    fmt, version = args.format, args.version
    paths = ['%s/%s/data/rollout-%05d-%s-g%d.jsonl.gz' % (RUN, fmt, version, fmt, g)
             for g in range(args.games)]
    rows = load_rows(paths)
    rows = attach_histories(rows)
    scored = [r for r in rows if r.get('choice', -1) >= 0]
    print('rows %d scored %d' % (len(rows), len(scored)))
    print('splits', {s: sum(1 for r in scored if r['split'] == s) for s in ('train', 'validation')})
    print('sources', sorted({r['source'] for r in scored}))
    print('versions', sorted({r['version'] for r in scored}))

    model, path = load_model(fmt, version)
    print('model', path)
    worst = []
    hist_turns = []
    with torch.no_grad():
        for row in scored[:args.limit]:
            logits, values = model(*batch([row], 'cpu'))
            dist = torch.distributions.Categorical(logits=logits)
            logp = float(dist.log_prob(torch.tensor([row['choice']]))[0])
            old_logp = float(row['log_probability'])
            value = float(values[0])
            old_value = float(row['value'])
            hist_turns.append((row['turn'], len(row['_history']),
                               row['_history'][-1]['turn'] if row['_history'] else None))
            worst.append((abs(logp - old_logp), abs(value - old_value), logp, old_logp, value, old_value))
    worst.sort(reverse=True)
    print('n compared', len(worst))
    print('logp  max|diff| %.3e  mean|diff| %.3e' % (
        worst[0][0], sum(w[0] for w in worst) / len(worst)))
    print('value max|diff| %.3e  mean|diff| %.3e' % (
        max(w[1] for w in worst), sum(w[1] for w in worst) / len(worst)))
    print('worst five (|dlogp|, |dvalue|, logp, old_logp, value, old_value):')
    for w in worst[:5]:
        print('   %.3e %.3e %.6f %.6f %.6f %.6f' % w)
    k3 = [(math.exp(w[3] - w[2]) - 1) - (w[3] - w[2]) for w in worst]
    print('per-row k3 of recorded logp vs old  mean %.3e max %.3e' % (
        sum(k3) / len(k3), max(k3)))
    print('history shape sample', hist_turns[:6], hist_turns[-3:])
    gaps = [1 for t, n, last in hist_turns if t > 1 and (not n or last != t - 1)]
    print('rows at turn>1 with missing/non-adjacent prefix %d of %d' % (
        len(gaps), sum(1 for t, _, _ in hist_turns if t > 1)))
    # PPO drops non-train rows before the update (learning/updates.py prepare).
    kept = [r for r in scored if r['split'] == 'train']
    print('rows dropped by prepare split filter %d of %d' % (len(scored) - len(kept), len(scored)))
    windows = training_windows(kept, turns=8)
    print('windows %d decisions %d steps/epoch %d planned steps %d' % (
        len(windows), sum(len(w) for w in windows), max(1, (len(windows) + 3) // 4),
        max(1, (len(windows) + 3) // 4) * args.epochs))


def grad(args):
    fmt, version = args.format, args.version
    paths = ['%s/%s/data/rollout-%05d-%s-g%d.jsonl.gz' % (RUN, fmt, version, fmt, g)
             for g in range(args.games)]
    records = [r for r in load_rows(paths) if r.get('choice', -1) >= 0]
    records = attach_histories(records)
    records = [r for r in records if r['split'] == 'train']
    model, path = load_model(fmt, version)
    model.train()
    adv, ret = advantages(records)
    adv = torch.tensor(adv, dtype=torch.float32)
    adv = (adv - adv.mean()) / adv.std(unbiased=False).clamp(min=1e-6)
    ret = torch.tensor(ret, dtype=torch.float32)
    windows = training_windows(records, turns=8)
    selected = windows[:4]
    index_of = {id(r): i for i, r in enumerate(records)}
    print('model', path, 'records', len(records), 'windows', len(windows))

    chunks = []
    for window in selected:
        for offset in range(0, len(window), 32):
            chunk = window[offset:offset + 32]
            chunks.append((chunk, len(chunk) / len(window) / len(selected)))
    print('microbatches %d decisions %d' % (len(chunks), sum(len(c) for c, _ in chunks)))

    rehearsal = None
    if args.rehearsal:
        pool = load_rows(['%s/%s/data/teacher-%05d-%s-t0.jsonl.gz' % (RUN, fmt, version, fmt)])
        pool = [r for r in pool if r.get('choice', -1) >= 0 and r['split'] == 'train']
        sampler = make_bc_sampler(pool)
        rehearsal = sampler.sample(sum(len(c) for c, _ in chunks))
        print('rehearsal rows %d from %d pool rows' % (len(rehearsal), len(pool)))
        offset = 0
        pairs = []
        for chunk, weight in chunks:
            pairs.append((chunk, rehearsal[offset:offset + len(chunk)], weight))
            offset += len(chunk)
    else:
        pairs = [(chunk, None, weight) for chunk, weight in chunks]

    terms = {}
    for name in ('policy', 'value', 'entropy', 'rehearsal'):
        if name == 'rehearsal' and not args.rehearsal:
            continue
        model.zero_grad(set_to_none=True)
        total = 0.
        for chunk, reh, weight in pairs:
            logits, values = model(*batch(chunk, 'cpu'))
            dist = torch.distributions.Categorical(logits=logits)
            chosen = torch.tensor([r['choice'] for r in chunk])
            old = torch.tensor([r['log_probability'] for r in chunk])
            ratio = torch.exp(dist.log_prob(chosen) - old)
            index = [index_of[id(r)] for r in chunk]
            if name == 'policy':
                loss = -torch.minimum(ratio * adv[index], ratio.clamp(.8, 1.2) * adv[index]).mean()
            elif name == 'value':
                loss = .5 * (values - ret[index]).square().mean()
            elif name == 'entropy':
                loss = -args.entropy * dist.entropy().mean()
            else:
                bc_logits, _ = model(*batch(reh, 'cpu'))
                loss = args.bc_aux * torch.nn.functional.cross_entropy(
                    bc_logits, torch.tensor([r['choice'] for r in reh]))
            (loss * weight).backward()
            total += float(loss.detach()) * weight
        vector = torch.cat([(p.grad if p.grad is not None else torch.zeros_like(p)).reshape(-1).clone()
                            for p in model.parameters()])
        terms[name] = vector
        print('%-10s loss %+0.6f grad_norm %.6e' % (name, total, float(vector.norm())))
    for a in terms:
        for b in terms:
            if a < b:
                cos = float(torch.nn.functional.cosine_similarity(terms[a], terms[b], dim=0))
                scale = float(terms[b].norm() / terms[a].norm()) if float(terms[a].norm()) else 0.
                print('cos(%-9s,%-9s) %+0.4f norm_ratio b/a %.3f' % (a, b, cos, scale))
    with torch.no_grad():
        stats = []
        for chunk, reh, weight in pairs:
            logits, values = model(*batch(chunk, 'cpu'))
            dist = torch.distributions.Categorical(logits=logits)
            chosen = torch.tensor([r['choice'] for r in chunk])
            old = torch.tensor([r['log_probability'] for r in chunk])
            ratio = torch.exp(dist.log_prob(chosen) - old)
            index = [index_of[id(r)] for r in chunk]
            stats.append((weight, adv[index], ratio, dist.entropy(), values, ret[index], old))
    a = torch.cat([s[1] for s in stats])
    w = torch.tensor([s[0] for s in stats]).repeat_interleave(torch.tensor([len(s[1]) for s in stats])).float()
    r = torch.cat([s[2] for s in stats])
    print('advantages mean %+0.4f std %.4f  ratio mean %.6f  clip fraction %.4f' % (
        float(a.mean()), float(a.std()), float((r * w).sum()), float(((r - 1).abs() > .2).float().mean())))
    print('weighted entropy %.6f  value mse %.6f  |old logp| mean %.6f max %.6f' % (
        float(sum(float(s[3].mean()) * s[0] for s in stats)),
        float(sum(float(((s[4] - s[5]) ** 2).mean()) * s[0] for s in stats)),
        float(torch.cat([s[6] for s in stats]).abs().mean()),
        float(torch.cat([s[6] for s in stats]).abs().max())))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('replay', 'grad'))
    parser.add_argument('--format', default='duel')
    parser.add_argument('--version', type=int, default=99)
    parser.add_argument('--games', type=int, default=4)
    parser.add_argument('--limit', type=int, default=48)
    parser.add_argument('--epochs', type=int, default=4)
    parser.add_argument('--entropy', type=float, default=.01)
    parser.add_argument('--bc-aux', type=float, default=.1)
    parser.add_argument('--rehearsal', type=int, default=1)
    args = parser.parse_args()
    if args.mode == 'replay':
        replay(args)
    else:
        grad(args)


if __name__ == '__main__':
    main()
