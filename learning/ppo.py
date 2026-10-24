"""On-policy PPO update over a deterministic per-epoch window plan."""
import hashlib
import json
import random
import time

import torch

from .data import advantages, make_bc_sampler
from .model import batch
from .updates import prepare, setup

PLAN_VERSION = 2
KL_LIMIT = .02


def _digest(model):
    digest = hashlib.sha256()
    for name in sorted(model.state_dict()):
        digest.update(name.encode())
        digest.update(model.state_dict()[name].detach().to('cpu').numpy().tobytes())
    return digest.hexdigest()


def _target_key(row):
    return (row['game_id'], row['side'], row['turn'], row.get('decision'))


def _window_signature(window):
    return '|'.join(str(_target_key(row)) for row in window)


def _epoch_order(seed, epoch, count):
    order = list(range(count))
    random.Random(f'{seed}:{epoch}:{count}').shuffle(order)
    return order


def _plan_hash(windows, order):
    digest = hashlib.sha256()
    for index in order:
        digest.update(_window_signature(windows[index]).encode())
        digest.update(b';')
    return digest.hexdigest()


def update(model, optimizer, records, bc_records=None, epochs=4, minibatch=256, deadline=float('inf'),
           progress=None, on_step=None, shaping_weight=None, entropy=.01, bc_aux=.1,
           allow_policy_rehearsal=False, plan_seed=0):
    """Run PPO updates over one frozen policy version with BC rehearsal.

    Windows are visited once per epoch in a plan derived from ``plan_seed`` and
    the epoch index; no window is sampled twice.  A logical optimizer batch is
    checked for KL as a whole before any parameter changes.
    """
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
    rehearsal_sampler = make_bc_sampler(bc_records, allow_policy=allow_policy_rehearsal)
    start = progress or dict(epoch=0, step=0)
    loss_sum = start.get('loss_sum', 0.)
    updates = start.get('updates', 0)
    kl = 0.
    decisions_seen = start.get('decisions_seen', 0)
    inspected = 0
    committed = 0
    before = _digest(model)
    cursor = dict(epoch=start.get('epoch', 0), step=start.get('step', 0), plan_version=PLAN_VERSION,
                  plan_seed=plan_seed)
    if start.get('plan_hash'):
        cursor['plan_hash'] = start['plan_hash']
    targets = [_target_key(row) for window in windows for row in window]
    repeated = len(targets) - len(set(targets))

    def result(exit, interrupted=False, kl_stopped=False):
        return dict(updates=updates, loss=loss_sum / max(1, updates), approx_kl=kl,
                    interrupted=interrupted, kl_stopped=kl_stopped, decisions_seen=decisions_seen,
                    unique_families_seen=len({r['game_family'] for r in records}),
                    effective_dataset_passes=decisions_seen / len(records), sequence_windows=len(windows),
                    microbatch=micro, exit=exit, plan_version=PLAN_VERSION, plan_migrated=plan_migrated,
                    planned_windows=len(windows), planned_targets=len(targets), repeated_targets=repeated,
                    inspected_decisions=inspected, committed_decisions=committed,
                    policy_sha256_before=before, policy_sha256_after=_digest(model), cursor=cursor)

    plan_migrated = progress is not None and progress.get('plan_version', 1) != PLAN_VERSION
    if not windows:
        return result('completed')

    for epoch in range(start['epoch'], epochs):
        order = _epoch_order(plan_seed, epoch, len(windows))
        epoch_hash = _plan_hash(windows, order)
        if epoch == start['epoch'] and cursor.get('plan_hash') and cursor['plan_hash'] != epoch_hash:
            raise ValueError('rollout window plan changed since the saved cursor')
        for step in range(start['step'] if epoch == start['epoch'] else 0, steps):
            if time.time() >= deadline:
                cursor = dict(epoch=epoch, step=step, plan_version=PLAN_VERSION, plan_seed=plan_seed,
                              plan_hash=epoch_hash)
                return result('deadline', interrupted=True)
            batch_rng = random.getstate()
            optimizer.zero_grad()
            selected = [windows[index] for index in order[step * sequence_count:(step + 1) * sequence_count]]
            total_value = 0.
            inspected_batch = 0
            batch_committed = 0
            batch_kl_sum = 0.
            for window in selected:
                window_kl_sum = 0.
                window_decisions = 0
                # Each window has equal weight; long games do not dominate short ones.
                for offset in range(0, len(window), micro):
                    if time.time() >= deadline:
                        optimizer.zero_grad()
                        random.setstate(batch_rng)
                        cursor = dict(epoch=epoch, step=step, plan_version=PLAN_VERSION, plan_seed=plan_seed,
                                      plan_hash=epoch_hash)
                        return result('deadline', interrupted=True)
                    rows = window[offset:offset + micro]
                    inspected_batch += len(rows)
                    inspected += len(rows)
                    logits, values = model(*batch(rows, device))
                    dist = torch.distributions.Categorical(logits=logits)
                    chosen = torch.tensor([r['choice'] for r in rows], device=device)
                    logp = dist.log_prob(chosen)
                    selected_rows = [row_index[id(r)] for r in rows]
                    old = torch.tensor([r['log_probability'] for r in rows], device=device)
                    ratio = torch.exp(logp - old)
                    a = adv[selected_rows]
                    window_kl_sum += float(((ratio - 1) - (logp - old)).sum().detach())
                    window_decisions += len(rows)
                    loss = -torch.minimum(ratio * a, ratio.clamp(.8, 1.2) * a).mean() + .5 * (values - ret[selected_rows]).square().mean() - entropy * dist.entropy().mean()
                    rehearsal = rehearsal_sampler.sample(len(rows))
                    bc_logits, _ = model(*batch(rehearsal, device))
                    loss = loss + bc_aux * torch.nn.functional.cross_entropy(bc_logits, torch.tensor([r['choice'] for r in rehearsal], device=device))
                    if not torch.isfinite(loss):
                        raise ValueError('nonfinite training loss')
                    weighted = loss * len(rows) / len(window) / len(selected)
                    weighted.backward()
                    total_value += float(weighted.detach())
                    batch_committed += len(rows)
                if window_decisions:
                    batch_kl_sum += window_kl_sum / window_decisions
            kl = batch_kl_sum / len(selected) if selected else 0.
            if kl > KL_LIMIT:
                optimizer.zero_grad()
                random.setstate(batch_rng)
                cursor = dict(epoch=epoch, step=step, plan_version=PLAN_VERSION, plan_seed=plan_seed,
                              plan_hash=epoch_hash)
                return result('kl_stop', kl_stopped=True)
            torch.nn.utils.clip_grad_norm_(model.parameters(), .5)
            if time.time() >= deadline:
                optimizer.zero_grad()
                random.setstate(batch_rng)
                cursor = dict(epoch=epoch, step=step, plan_version=PLAN_VERSION, plan_seed=plan_seed,
                              plan_hash=epoch_hash)
                return result('deadline', interrupted=True)
            optimizer.step()
            committed += batch_committed
            loss_sum += total_value
            updates += 1
            decisions_seen += inspected_batch
            if step + 1 == steps:
                cursor = dict(epoch=epoch + 1, step=0, plan_version=PLAN_VERSION, plan_seed=plan_seed)
            else:
                cursor = dict(epoch=epoch, step=step + 1, plan_version=PLAN_VERSION, plan_seed=plan_seed,
                              plan_hash=epoch_hash)
            if on_step:
                on_step(dict(cursor, loss_sum=loss_sum, updates=updates, decisions_seen=decisions_seen,
                             inspected_decisions=inspected, committed_decisions=committed))
    return result('completed')
