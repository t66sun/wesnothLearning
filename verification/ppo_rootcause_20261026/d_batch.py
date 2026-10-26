"""Locate the batched-vs-single-row divergence and summarise ratio statistics."""
import gzip
import os
import sys

import torch

sys.path.insert(0, os.environ.get('WL_SOURCE', 'WesnothLearning'))
from learning.model import batch                                  # noqa: E402
from learning.rowpack import unpack_line                          # noqa: E402
from learning.sequences import attach_histories, training_windows  # noqa: E402
from learning.export import load_model                            # noqa: E402

RUN = os.environ.get('WL_RUN', '.')
fmt, version = 'duel', 99
rows = []
for g in range(4):
    path = '%s/%s/data/rollout-%05d-%s-g%d.jsonl.gz' % (RUN, fmt, version, fmt, g)
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            row, _ = unpack_line(line)
            if not row.get('faults') and row.get('choice', -1) >= 0:
                rows.append(row)
rows = attach_histories(rows)
rows = [r for r in rows if r['split'] == 'train']
model, path = load_model('%s/%s/policies/v%06d-sample/model.pt' % (RUN, fmt, version), fmt, 'cpu')
model.eval()
windows = training_windows(rows, turns=8)
print('windows', [len(w) for w in windows])

chunk = windows[0][:32]
with torch.no_grad():
    logits, values = model(*batch(chunk, 'cpu'))
    dist = torch.distributions.Categorical(logits=logits)
    chosen = torch.tensor([r['choice'] for r in chunk])
    batched = dist.log_prob(chosen)
    single = []
    single_value = []
    for row in chunk:
        lg, v = model(*batch([row], 'cpu'))
        single.append(float(torch.distributions.Categorical(logits=lg).log_prob(torch.tensor([row['choice']]))[0]))
        single_value.append(float(v[0]))
single = torch.tensor(single)
old = torch.tensor([r['log_probability'] for r in chunk])
print('chunk rows %d candidate counts %s' % (len(chunk), sorted({len(r['candidates']) for r in chunk})))
print('batched-vs-single logp max %.3e' % float((batched - single).abs().max()))
print('batched-vs-recorded logp max %.3e' % float((batched - old).abs().max()))
print('single-vs-recorded  logp max %.3e' % float((single - old).abs().max()))
print('value batched-vs-recorded max %.3e  single max %.3e' % (
    float((values - torch.tensor([r['value'] for r in chunk])).abs().max()),
    float((torch.tensor(single_value) - torch.tensor([r['value'] for r in chunk])).abs().max())))
order = (batched - old).abs().argsort(descending=True)
for i in order[:6].tolist():
    row = chunk[i]
    print('  row toy=%s turn %d decision %s choice %d ncand %d |dlogp| %.3e old %.4f new %.4f nhist %d' % (
        row['game_id'][-6:], row['turn'], row.get('decision'), row['choice'], len(row['candidates']),
        float((batched - old).abs()[i]), float(old[i]), float(batched[i]), len(row['_history'])))

# ratio statistics per microbatch with the same weighting ppo uses
for window in windows[:2]:
    for offset in range(0, len(window), 32):
        piece = window[offset:offset + 32]
        with torch.no_grad():
            lg, _ = model(*batch(piece, 'cpu'))
            lp = torch.distributions.Categorical(logits=lg).log_prob(torch.tensor([r['choice'] for r in piece]))
        o = torch.tensor([r['log_probability'] for r in piece])
        ratio = torch.exp(lp - o)
        print('window size %d chunk %d ratio mean %.4f min %.4f max %.4f clip %.3f |old| mean %.3f max %.3f' % (
            len(window), len(piece), float(ratio.mean()), float(ratio.min()), float(ratio.max()),
            float((ratio - 1).abs().gt(.2).float().mean()), float(o.abs().mean()), float(o.abs().max())))
