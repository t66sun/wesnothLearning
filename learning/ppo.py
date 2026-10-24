"""On-policy PPO update over frozen-version windows."""
import json
import random
import time

import torch

from .data import advantages, make_bc_sampler
from .model import batch
from .updates import prepare, setup


def update(model, optimizer, records, bc_records=None, epochs=4, minibatch=256, deadline=float('inf'),
           progress=None, on_step=None, shaping_weight=None, entropy=.01, bc_aux=.1,
           allow_policy_rehearsal=False):
    """Run PPO updates over one frozen policy version with BC rehearsal."""
    records = prepare(model, records, bc_records)
    if len({r['version'] for r in records}) != 1:
        raise ValueError('PPO batch must use one frozen policy version')
    for key in ('reward_version', 'reward_formula_id', 'engine_id', 'rules_version', 'rng_version'):
        if len({r[key] for r in records}) != 1:
            raise ValueError('PPO batch mixes ' + key)
    if len({json.dumps(r['reward_config'], sort_keys=True) for r in records}) != 1:
        raise ValueError('PPO batch mixes reward configurations')
    if any(r['source'] != 'policy' or (not r.get('value_valid', True) and not (r.get('truncated') and r.get('bootstrap_value') is not None)) for r in records):
        raise ValueError('PPO requires on-policy complete trajectories')
    if not bc_records:
        raise ValueError('PPO requires same-format BC rehearsal data')
    device = next(model.parameters()).device
    adv, ret = advantages(records, shaping_weight=shaping_weight)
    adv = torch.tensor(adv, dtype=torch.float32, device=device)
    ret = torch.tensor(ret, dtype=torch.float32, device=device)
    groups = {model.format_name: list(range(len(records)))}
    if any(not ids for ids in groups.values()):
        raise ValueError('a training update requires every configured format')
    for ids in groups.values():
        a = adv[ids]
        adv[ids] = (a - a.mean()) / a.std(unbiased=False).clamp(min=1e-6)
    device, windows, sequence_count, micro, steps = setup(model, records, minibatch)
    model.train()
    row_index = {id(r): i for i, r in enumerate(records)}
    window_index = {id(r): w for w in windows for r in w}
    rehearsal_sampler = make_bc_sampler(bc_records, allow_policy=allow_policy_rehearsal)
    start = progress or dict(epoch=0, step=0)
    loss_sum = start.get('loss_sum', 0.)
    updates = start.get('updates', 0)
    kl = 0.
    decisions_seen = start.get('decisions_seen', 0)
    for epoch in range(start['epoch'], epochs):
        for step in range(start['step'] if epoch == start['epoch'] else 0, steps):
            if time.time() >= deadline:
                return dict(updates=updates, loss=loss_sum / max(1, updates), interrupted=True)
            optimizer.zero_grad()
            selected_windows = random.choices(windows, k=sequence_count)
            total_value = 0.
            step_decisions = 0
            for window in selected_windows:
                # Each window has equal weight; long games do not dominate short ones.
                for offset in range(0, len(window), micro):
                    if time.time() >= deadline:
                        optimizer.zero_grad()
                        return dict(updates=updates, loss=loss_sum / max(1, updates), interrupted=True)
                    rows = window[offset:offset + micro]
                    logits, values = model(*batch(rows, device))
                    dist = torch.distributions.Categorical(logits=logits)
                    chosen = torch.tensor([r['choice'] for r in rows], device=device)
                    logp = dist.log_prob(chosen)
                    selected = [row_index[id(r)] for r in rows]
                    old = torch.tensor([r['log_probability'] for r in rows], device=device)
                    ratio = torch.exp(logp - old)
                    a = adv[selected]
                    kl = float(((ratio - 1) - (logp - old)).mean().detach())
                    if kl > .02:
                        optimizer.zero_grad()
                        return dict(updates=updates, loss=loss_sum / max(1, updates), interrupted=False,
                                    approx_kl=kl, kl_stopped=True)
                    loss = -torch.minimum(ratio * a, ratio.clamp(.8, 1.2) * a).mean() + .5 * (values - ret[selected]).square().mean() - entropy * dist.entropy().mean()
                    rehearsal = rehearsal_sampler.sample(len(rows))
                    bc_logits, _ = model(*batch(rehearsal, device))
                    loss = loss + bc_aux * torch.nn.functional.cross_entropy(bc_logits, torch.tensor([r['choice'] for r in rehearsal], device=device))
                    if not torch.isfinite(loss):
                        raise ValueError('nonfinite training loss')
                    weighted = loss * len(rows) / len(window) / sequence_count
                    weighted.backward()
                    total_value += float(weighted.detach())
                    step_decisions += len(rows)
            torch.nn.utils.clip_grad_norm_(model.parameters(), .5)
            if time.time() >= deadline:
                optimizer.zero_grad()
                return dict(updates=updates, loss=loss_sum / max(1, updates), interrupted=True)
            optimizer.step()
            loss_sum += total_value
            updates += 1
            decisions_seen += step_decisions
            if on_step:
                cursor = dict(epoch=epoch + 1, step=0) if step + 1 == steps else dict(epoch=epoch, step=step + 1)
                on_step(dict(cursor, loss_sum=loss_sum, updates=updates, decisions_seen=decisions_seen))
    return dict(updates=updates, loss=loss_sum / max(1, updates), interrupted=False, approx_kl=kl, kl_stopped=False,
                decisions_seen=decisions_seen, unique_families_seen=len({r['game_family'] for r in records}),
                effective_dataset_passes=decisions_seen / len(records), sequence_windows=len(windows),
                microbatch=micro)
