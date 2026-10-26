"""Does the differentiable context path agree with the inference path?"""
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
rows = []
for g in range(4):
    path = '%s/duel/data/rollout-%05d-duel-g%d.jsonl.gz' % (RUN, 99, g)
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            row, _ = unpack_line(line)
            if not row.get('faults') and row.get('choice', -1) >= 0:
                rows.append(row)
rows = attach_histories(rows)
rows = [r for r in rows if r['split'] == 'train']
model, path = load_model('%s/duel/policies/v%06d-sample/model.pt' % (RUN, 99), 'duel', 'cpu')
chunk = training_windows(rows, turns=8)[0][:32]
chosen = torch.tensor([r['choice'] for r in chunk])
old = torch.tensor([r['log_probability'] for r in chunk])


def run(mode, grad, key):
    getattr(model, mode)()
    context = torch.enable_grad() if grad else torch.no_grad()
    with context:
        logits, values = model(*batch(chunk, 'cpu'))
    dist = torch.distributions.Categorical(logits=logits)
    return dist.log_prob(chosen).detach(), values.detach(), dist.entropy().detach()


ref = run('eval', False, 'base')
for mode in ('eval', 'train'):
    for grad in (True, False):
        lp, val, ent = run(mode, grad, '%s-%s' % (mode, grad))
        print('%-5s grad=%-5s  max|dlogp| %.3e  max|dvalue| %.3e  max|dentropy| %.3e  ratio mean %.6f' % (
            mode, grad, float((lp - ref[0]).abs().max()), float((val - ref[1]).abs().max()),
            float((ent - ref[2]).abs().max()), float(torch.exp(lp - old).mean())))
lp, val, ent = ref
print('reference: |old logp| mean %.4f max %.4f, ratio mean %.6f, entropy mean %.4f' % (
    float(old.abs().mean()), float(old.abs().max()), float(torch.exp(lp - old).mean()), float(ent.mean())))
# Which rows diverge under grad, if any?
lp, _, _ = run('train', True, 'g')
diff = (lp - ref[0]).abs()
top = diff.argsort(descending=True)[:6].tolist()
for i in top:
    row = chunk[i]
    print('  turn %d nhist %d ncand %d choice %d  dlogp %.3e' % (
        row['turn'], len(row['_history']), len(row['candidates']), row['choice'], float(diff[i])))
