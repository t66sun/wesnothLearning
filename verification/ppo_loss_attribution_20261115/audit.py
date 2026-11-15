"""Attribute frozen PPO proposals to their losses without committing an update."""
from collections import Counter, defaultdict
import math
from pathlib import Path
import random
from statistics import mean
import sys
import time

import torch
from torch.func import functional_call
from torch.optim.adam import adam

from learning import ppo
from learning.bc_anchor import weights_sha256
from learning.common import read_json, sha256
from learning.data import advantages, make_bc_sampler, read_shards
from learning.export import load_model
from learning.model import batch
from learning.tasks import TASK_ID
from learning.updates import prepare, setup
from verification.duel_ppo_comparison_20261106.audit import write_new

from optimizer_probe import trajectories
from review import verify_capture

TERMS = ('actor', 'critic', 'entropy', 'rehearsal')
MANIFEST_SHA = '36b2cdbb84b1df705d677a2a1dbeca343d7f92b39b7f5ea837454d0939bffad2'
PROBES_PER_ROLE = 6


def group(name):
    if name.startswith('value.'):
        return 'value'
    if name.startswith(('scorer.', 'local.')):
        return 'policy'
    return 'shared'


def gradients(model, params, selection, sampler, rng, micro, indices, adv, ret, manifest):
    parts = {name: [None] * len(params) for name in TERMS}
    losses = dict.fromkeys(TERMS, 0.)
    rehearsal_mix = Counter()
    cache = {}
    kl = 0.
    for window in selection:
        for offset in range(0, len(window), micro):
            rows = window[offset:offset + micro]
            logits, values = model(*batch(rows, history_cache=cache))
            dist = torch.distributions.Categorical(logits=logits)
            logp = dist.log_prob(torch.tensor([r['choice'] for r in rows]))
            ids = [indices[id(r)] for r in rows]
            delta = logp - logp.new_tensor([r['log_probability'] for r in rows])
            ratio = delta.exp()
            pool = sampler.sample(len(rows), rng)
            rehearsal_mix.update((r['source'], r['engine_id'], r.get('data_pool', r.get('data_role', 'original'))) for r in pool)
            bc_logits, _ = model(*batch(pool, history_cache=cache))
            objectives = (-torch.minimum(ratio * adv[ids], ratio.clamp(.8, 1.2) * adv[ids]).mean(),
                          .5 * (values - ret[ids]).square().mean(),
                          -manifest['entropy'] * dist.entropy().mean(),
                          manifest['bc_aux'] * torch.nn.functional.cross_entropy(
                              bc_logits, torch.tensor([r['choice'] for r in pool])))
            factor = len(rows) / len(window) / len(selection)
            kl += float(((ratio - 1) - delta).sum().detach()) / len(window) / len(selection)
            for name, loss in zip(TERMS, objectives, strict=True):
                losses[name] += float(loss.detach()) * factor
                values = torch.autograd.grad(loss * factor, params, allow_unused=True,
                                             retain_graph=name != 'rehearsal')
                for i, value in enumerate(values):
                    if value is not None:
                        prev = parts[name][i]
                        parts[name][i] = value if prev is None else prev + value
    assert kl <= ppo.KL_LIMIT
    return parts, losses, kl, {'/'.join(k): v for k, v in sorted(rehearsal_mix.items())}


def group_stats(names, params, parts):
    stats = {}
    for block in ('shared', 'policy', 'value'):
        ids = [i for i, n in enumerate(names) if group(n) == block]
        flat = {k: torch.cat([(p[i] if p[i] is not None else torch.zeros_like(params[i])).flatten()
                              for i in ids]).double() for k, p in parts.items()}
        norms = {k: float(x.norm()) for k, x in flat.items()}
        stats[block] = {k: dict(norm=n, cosine=float(flat[k] @ flat['actor']) / (n * norms['actor'])
                               if n and norms['actor'] else None) for k, n in norms.items()}
    return stats


def clipped(parts, omitted=None, zero_control=False):
    grads = []
    for column in zip(*parts.values(), strict=True):
        available = [x if key != omitted else torch.zeros_like(x)
                     for key, x in zip(TERMS, column, strict=True) if x is not None]
        if not available:
            grads.append(None)
            continue
        full = sum(available)
        if zero_control:
            full = full + 0. * available[-1]
        grads.append(full)
    norm = torch.linalg.vector_norm(torch.stack([x.norm() for x in grads if x is not None]))
    scale = (.5 / (norm + 1e-6)).clamp(max=1)
    return [None if x is None else x * scale for x in grads], float(norm)


class ProposalCaptured(Exception):
    pass


class ObserveOptimizer:
    def __init__(self, model):
        self.model = model
        self.observed = None

    def zero_grad(self):
        self.model.zero_grad(set_to_none=True)

    def step(self):
        self.observed = [p.grad for p in self.model.parameters()]
        raise ProposalCaptured


def production_parity(model, records, rehearsal, expected, manifest, step, rng_state, plan_hash):
    observer = ObserveOptimizer(model)
    random.setstate(rng_state)
    try:
        ppo.update(model, observer, records, bc_records=rehearsal, epochs=manifest['epochs'],
                   minibatch=manifest['minibatch'], entropy=manifest['entropy'], bc_aux=manifest['bc_aux'],
                   allow_policy_rehearsal=True, plan_seed=manifest['seed'],
                   progress=dict(epoch=0, step=step, plan_version=ppo.PLAN_VERSION, plan_hash=plan_hash))
    except ProposalCaptured:
        pass
    assert observer.observed is not None
    errors = []
    for actual, proposed in zip(observer.observed, expected, strict=True):
        assert (actual is None) == (proposed is None)
        if actual is not None:
            torch.testing.assert_close(actual, proposed, rtol=3e-5, atol=2e-7)
            errors.append(float((actual - proposed).abs().max()))
    observer.zero_grad()
    return max(errors)


@torch.no_grad()
def proposal(base, state, grads, rate):
    names, g, m, v, ticks, max_v = [], [], [], [], [], []
    if state:
        settings, = state['param_groups']
    else:
        settings = dict(params=list(range(len(base))), betas=(.9, .999), eps=1e-8,
                        weight_decay=0, amsgrad=False, maximize=False)
    result = dict(base)
    for (name, p), grad, key in zip(base.items(), grads, settings['params'], strict=True):
        if grad is None:
            continue
        result[name] = p.clone()
        names.append(name)
        g.append(grad)
        previous = state['state'].get(key, {}) if state else {}
        m.append(previous['exp_avg'].clone() if previous else torch.zeros_like(p))
        v.append(previous['exp_avg_sq'].clone() if previous else torch.zeros_like(p))
        ticks.append(previous['step'].clone() if previous else torch.tensor(0.))
        if settings['amsgrad']:
            max_v.append(previous['max_exp_avg_sq'].clone() if previous else torch.zeros_like(p))
    b1, b2 = settings['betas']
    adam([result[n] for n in names], g, m, v, max_v, ticks, lr=rate, beta1=b1, beta2=b2,
         eps=settings['eps'], weight_decay=settings['weight_decay'], amsgrad=settings['amsgrad'],
         maximize=settings['maximize'], foreach=settings.get('foreach'), fused=settings.get('fused'),
         decoupled_weight_decay=settings.get('decoupled_weight_decay', False))
    return result


def holdback(jobs):
    inputs, meta = [], []
    for job in jobs:
        rows = trajectories([job])
        credit, _ = advantages(rows, lam=1.)
        assert len({r['game_id'] for r in rows}) == 1 and not any(r.get('truncated') for r in rows)
        for i in range(8):
            idx = i * (len(rows) - 1) // 7
            r = rows[idx]
            if len(r['candidates']) > 1:
                inputs.append(r)
                meta.append((job['id'], job['meta']['map'], r['choice'], len(r['candidates']), credit[idx]))
    return [batch(inputs[i:i + 16]) for i in range(0, len(inputs), 16)], meta


@torch.no_grad()
def readout(model, weights, inputs, meta, reference=None):
    cache, logits = {}, []
    for args in inputs:
        payload = args[-1] | {'history_cache': cache}
        pred, _ = functional_call(model, weights, (*args[:-1], payload), strict=True)
        logits.extend(pred.double().unbind())
    logits = [x[:n] for x, (_, _, _, n, _) in zip(logits, meta, strict=True)]
    if reference is None:
        return logits
    game = defaultdict(lambda: dict(rows=0, positive=0, margin=0., positive_logp=0., projection=0., kl=0.))
    for (gid, board, j, _, credit), orig, alt in zip(meta, reference, logits, strict=True):
        old, new = orig.log_softmax(-1), alt.log_softmax(-1)
        diff = float(new[j] - old[j])
        r = game[gid]
        r['map'] = board
        r['rows'] += 1
        r['projection'] += credit * diff
        r['kl'] += float((old.exp() * (old - new)).sum())
        if credit > 0:
            other = torch.arange(len(orig)) != j
            r['positive'] += 1
            r['margin'] += float((alt[j] - alt[other].max()) - (orig[j] - orig[other].max()))
            r['positive_logp'] += diff
    for r in game.values():
        for key in ('projection', 'kl'):
            r[key] /= r['rows']
        for key in ('margin', 'positive_logp'):
            r[key] = r[key] / r['positive'] if r['positive'] else None
    return dict(kl=mean(r['kl'] for r in game.values()), games=dict(game))


def match(weights, measured, target, base, evaluate):
    if measured['kl'] <= 1.01 * target:
        return dict(scale=1., **measured)
    delta = {name: weights[name] - p for name, p in base.items()}
    lo, hi = 0., 1.
    factor = math.sqrt(target / measured['kl'])
    for _ in range(16):
        scored = evaluate({n: p + factor * delta[n] for n, p in base.items()})
        error = scored['kl'] / target - 1.
        if abs(error) <= .01:
            return dict(scale=factor, **scored)
        if error < 0:
            lo = factor
        else:
            hi = factor
        guess = factor * math.sqrt(target / scored['kl']) if scored['kl'] > 0 else hi
        factor = guess if lo < guess < hi else (lo + hi) / 2
    raise ValueError('could not match the held-back KL within one percent')


def analyze(model, optimizer, records, rehearsal, hold_jobs, manifest):
    model.train()
    records = prepare(model, records, rehearsal)
    params = tuple(model.parameters())
    base = {name: p.detach() for name, p in model.named_parameters()}
    adv, ret = map(torch.tensor, advantages(records))
    adv = (adv - adv.mean()) / adv.std(unbiased=False).clamp(min=1e-6)
    indices = {id(r): i for i, r in enumerate(records)}
    _, windows, width, micro, steps = setup(model, records, manifest['minibatch'])
    order = ppo._epoch_order(manifest['seed'], 0, len(windows))
    plan_hash = ppo._plan_hash(windows, order)
    steps_kept = {i * (steps - 1) // (PROBES_PER_ROLE - 1) for i in range(PROBES_PER_ROLE)}
    assert len(steps_kept) == PROBES_PER_ROLE
    sampler = make_bc_sampler(rehearsal, allow_policy=True)
    rng = random.Random(manifest['seed'])
    inputs, meta = holdback(hold_jobs)
    anchor = readout(model, base, inputs, meta)
    def evaluate(weights):
        return readout(model, weights, inputs, meta, anchor)

    result = []
    for step in range(steps):
        if step > max(steps_kept):
            break
        window_ids = order[step * width:(step + 1) * width]
        selection = [windows[i] for i in window_ids]
        if step not in steps_kept:
            for window in selection:
                for i in range(0, len(window), micro):
                    sampler.sample(len(window[i:i + micro]), rng)
            continue
        seed_state = rng.getstate()
        parts, loss, kl, mix = gradients(model, params, selection, sampler, rng, micro, indices, adv, ret, manifest)
        stats = group_stats(tuple(base), params, parts)
        full, norm = clipped(parts)
        parity = production_parity(model, records, rehearsal, full, manifest, step, seed_state, plan_hash)
        rate = manifest['stock_lr']
        weights = proposal(base, optimizer, full, rate)
        control = proposal(base, optimizer, clipped(parts, zero_control=True)[0], rate)
        assert all(torch.equal(weights[k], control[k]) for k in weights)
        raw = evaluate(weights)
        comparisons = {}
        for term in TERMS:
            grads, alt_norm = clipped(parts, omitted=term)
            alt = proposal(base, optimizer, grads, rate)
            measured = evaluate(alt)
            target = min(raw['kl'], measured['kl'])
            assert target > 0
            equal = match(weights, raw, target, base, evaluate)
            equal_alt = match(alt, measured, target, base, evaluate)
            assert abs(equal['kl'] - equal_alt['kl']) <= .01001 * target
            comparisons[term] = dict(raw=measured, norm=alt_norm, matched_full=equal, matched_omitted=equal_alt)
        result.append(dict(step=step, windows=window_ids,
                           update_games=dict(Counter(r['game_id'] for w in selection for r in w)),
                           targets=sum(map(len, selection)), loss=loss, approximate_kl=kl, rehearsal_mix=mix,
                           groups=stats, preclip_norm=norm, parity_max_error=parity, full=raw, omitted=comparisons))
        print(f"epoch=0 step={step} targets={result[-1]['targets']} parity_error={parity:.3g}", flush=True)
    return dict(epoch=0, plan_hash=plan_hash, steps=steps, sampler=sampler.source_identities,
                rehearsal_rows_excluded=sampler.rows_excluded, proposals=result)


def main(manifest_path, out, limit):
    started = time.monotonic()
    assert sha256(manifest_path) == MANIFEST_SHA and not out.exists()
    manifest = read_json(manifest_path)
    base = Path(manifest['capture_root'])
    capture, jobs, _, ledger, archive = verify_capture(base)
    assert capture['runtime'] == manifest['runtime'] and archive['archive_sha256'] == manifest['capture_archive_sha256']
    by_id = {j['id']: j for j in jobs}
    assert all(sha256(Path(p)) == s for p, s in manifest['rehearsal'].items())
    rehearsal = read_shards(list(manifest['rehearsal']), partition='train', limit=manifest['rehearsal_rows'],
                            format_name='duel', seed=manifest['seed'], expected_task=TASK_ID)
    assert len(rehearsal) == manifest['rehearsal_rows']
    traces = {}
    for name, spec in manifest['roles'].items():
        if name not in limit:
            continue
        print(name, flush=True)
        assert spec['checkpoint'] == capture['roles'][name]
        assert spec['shards'] == {j: ledger[j]['trajectory_sha256']
                                  for j in spec['training_games'] + spec['scored_holdback_games']}
        checkpoint = spec['checkpoint']
        path = Path(checkpoint['path'])
        assert sha256(path) == checkpoint['checkpoint_sha256']
        model, state = load_model(path, 'duel')
        assert weights_sha256(model.state_dict()) == checkpoint['weights_sha256']
        optimizer = state['optimizer'] if spec['adam'] == 'checkpoint' else None
        if optimizer:
            assert {g['lr'] for g in optimizer['param_groups']} == {manifest['stock_lr']}
        records = trajectories([by_id[j] for j in spec['training_games']])
        assert len(records) == spec['on_policy_rows']
        traces[name] = analyze(model, optimizer, records, rehearsal,
                               [by_id[j] for j in spec['scored_holdback_games']], manifest)
        assert weights_sha256(model.state_dict()) == checkpoint['weights_sha256']
        traces[name].update(checkpoint=checkpoint, adam=spec['adam'])
    assert set(traces) == set(limit)
    write_new(out, dict(issue=357, manifest_sha256=MANIFEST_SHA, capture_archive_sha256=archive['archive_sha256'],
                        source_ppo_sha256=sha256(Path(ppo.__file__)), script_sha256=sha256(Path(__file__)),
                        torch=str(torch.__version__), wall_seconds=time.monotonic() - started, roles=traces,
                        new_games=0, committed_updates=0))


if __name__ == '__main__':
    torch.set_num_threads(1)
    path, dest, *roles = sys.argv[1:]
    manifest_path = Path(path).resolve()
    main(manifest_path, Path(dest).resolve(), roles or list(read_json(manifest_path)['roles']))
