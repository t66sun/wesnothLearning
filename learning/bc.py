"""Behaviour-cloning update loop, auxiliary objective and imitation quality."""
import time
import random

import torch

from .data import make_bc_sampler
from .formats import record_format
from .model import batch
from .updates import prepare, setup


def update(model, optimizer, records, bc_records=None, epochs=4, minibatch=256, deadline=float('inf'),
           progress=None, on_step=None):
    """Run supervised updates over all training windows.

    Each window carries equal weight regardless of its length, and each real
    decision counts once when reporting coverage.
    """
    records = prepare(model, records, bc_records)
    device, windows, sequence_count, micro, steps = setup(model, records, minibatch)
    window_index = {id(r): w for w in windows for r in w}
    sampler = make_bc_sampler(records)
    start = progress or dict(epoch=0, step=0)
    loss_sum = start.get('loss_sum', 0.)
    updates = start.get('updates', 0)
    decisions_seen = start.get('decisions_seen', 0)
    for epoch in range(start['epoch'], epochs):
        for step in range(start['step'] if epoch == start['epoch'] else 0, steps):
            if time.time() >= deadline:
                return dict(updates=updates, loss=loss_sum / max(1, updates), interrupted=True)
            batch_rng = random.getstate()
            optimizer.zero_grad()
            selected_windows = [window_index[id(r)] for r in sampler.sample(sequence_count)]
            total_value = 0.
            step_decisions = 0
            for window in selected_windows:
                # Each window has equal weight; long games do not dominate short ones.
                for offset in range(0, len(window), micro):
                    if time.time() >= deadline:
                        optimizer.zero_grad()
                        random.setstate(batch_rng)
                        return dict(updates=updates, loss=loss_sum / max(1, updates), interrupted=True)
                    rows = window[offset:offset + micro]
                    logits, values = model(*batch(rows, device))
                    dist = torch.distributions.Categorical(logits=logits)
                    chosen = torch.tensor([r['choice'] for r in rows], device=device)
                    logp = dist.log_prob(chosen)
                    valid = torch.tensor([r.get('value_valid', True) for r in rows], device=device, dtype=torch.bool)
                    targets = torch.tensor([r.get('reward', 0) or 0 for r in rows], device=device)
                    loss = -logp.mean() + .1 * auxiliary_loss(logits, rows)
                    if valid.any():
                        loss = loss + .5 * (values[valid] - targets[valid]).square().mean()
                    if not torch.isfinite(loss):
                        raise ValueError('nonfinite training loss')
                    weighted = loss * len(rows) / len(window) / sequence_count
                    weighted.backward()
                    total_value += float(weighted.detach())
                    step_decisions += len(rows)
            torch.nn.utils.clip_grad_norm_(model.parameters(), .5)
            if time.time() >= deadline:
                optimizer.zero_grad()
                random.setstate(batch_rng)
                return dict(updates=updates, loss=loss_sum / max(1, updates), interrupted=True)
            optimizer.step()
            loss_sum += total_value
            updates += 1
            decisions_seen += step_decisions
            if on_step:
                cursor = dict(epoch=epoch + 1, step=0) if step + 1 == steps else dict(epoch=epoch, step=step + 1)
                on_step(dict(cursor, loss_sum=loss_sum, updates=updates, decisions_seen=decisions_seen))
    return dict(updates=updates, loss=loss_sum / max(1, updates), interrupted=False, approx_kl=0., kl_stopped=False,
                decisions_seen=decisions_seen, unique_families_seen=len({r['game_family'] for r in records}),
                effective_dataset_passes=decisions_seen / len(records), sequence_windows=len(windows),
                microbatch=micro)


def auxiliary_loss(logits, rows):
    """Marginal supervision of type, actor, and target/destination, with exact CE retained."""
    losses = []
    def identity(candidate, key):
        if key == 'kind':
            return candidate['kind']
        if key == 'actor':
            return (candidate.get('actor') or {}).get('id')
        target = candidate.get('target')
        return target['id'] if target else (candidate.get('tx', candidate.get('x')), candidate.get('ty', candidate.get('y')))
    for i, r in enumerate(rows):
        row = logits[i, :len(r['candidates'])]
        normalizer = torch.logsumexp(row, 0)
        chosen = r['candidates'][r['choice']]
        for key in ('kind', 'actor', 'destination'):
            indices = [j for j, c in enumerate(r['candidates']) if identity(c, key) == identity(chosen, key)]
            losses.append(normalizer - torch.logsumexp(row[indices], 0))
    return torch.stack(losses).mean()


@torch.no_grad()
def imitation_quality(model, records, minimum=32, thresholds=None):
    import math
    device = next(model.parameters()).device
    thresholds = thresholds or dict(all=.4, recruit=.6, move=.35, attack=.35)
    model.eval()
    metrics = {}
    for fmt in [model.format_name]:
        rows = [r for r in records if r['split'] == 'validation' and record_format(r) == fmt and len(r['candidates']) > 1]
        loss = uniform = correct = chance = 0.
        kinds = {k: dict(samples=0, correct=0) for k in ('recruit', 'move', 'attack')}
        for offset in range(0, len(rows), 64):
            chunk = rows[offset:offset + 64]
            logits, _ = model(*batch(chunk, device))
            target = torch.tensor([r['choice'] for r in chunk], device=device)
            loss += float(torch.nn.functional.cross_entropy(logits, target, reduction='sum'))
            correct += float((logits.argmax(1) == target).sum())
            predicted = logits.argmax(1).tolist()
            for i, r in enumerate(chunk):
                kind = r.get('actual', r['candidates'][r['choice']]).get('kind')
                if kind == 'move_attack':
                    kind = 'attack'
                if kind in kinds:
                    kinds[kind]['samples'] += 1
                    kinds[kind]['correct'] += int(predicted[i] == r['choice'])
            uniform += sum(math.log(len(r['candidates'])) for r in chunk)
            chance += sum(1 / len(r['candidates']) for r in chunk)
        count = len(rows)
        for k, v in kinds.items():
            v['accuracy'] = v['correct'] / max(1, v['samples'])
        effective = count >= minimum and loss < .85 * uniform and correct / max(1, count) >= thresholds['all']
        effective = effective and all(v['samples'] >= minimum and v['accuracy'] >= thresholds[k] for k, v in kinds.items())
        metrics[fmt] = dict(samples=count, cross_entropy=loss / max(1, count), uniform_entropy=uniform / max(1, count),
                            kinds=kinds, accuracy=correct / max(1, count), uniform_accuracy=chance / max(1, count),
                            effective=effective)
    return dict(effective=all(m['effective'] for m in metrics.values()), formats=metrics)
