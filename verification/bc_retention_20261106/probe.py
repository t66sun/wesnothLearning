"""Frozen BC retention diagnosis. No optimizer, collection, or checkpoint writes."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import re
import statistics

import torch

from learning.data import advantages, make_bc_sampler, read_shards
from learning.export import load_model
from learning.model import batch


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def weights_digest(model):
    value = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        value.update(name.encode())
        value.update(tensor.detach().cpu().numpy().tobytes())
    return value.hexdigest()


def forward_kl(anchor_logits, student_logits, mask):
    """Per-row KL(anchor || student), with no gradient through the anchor."""
    anchor_logp = anchor_logits.detach().log_softmax(-1).masked_fill(~mask, 0.)
    student_logp = student_logits.log_softmax(-1).masked_fill(~mask, 0.)
    probability = anchor_logp.exp().masked_fill(~mask, 0.)
    return (probability * (anchor_logp - student_logp)).sum(-1)


def describe(values):
    values = list(values)
    return dict(n=len(values), mean=statistics.mean(values),
                min=min(values), max=max(values)) if values else dict(n=0)


def identity(rows):
    keys = [(r['game_id'], r['side'], r['turn'], r.get('decision')) for r in rows]
    return dict(rows=len(rows), games=len({r['game_id'] for r in rows}),
                scenario_families=len({r['scenario_family'] for r in rows}),
                sources=dict(Counter(r['source'] for r in rows)),
                splits=dict(Counter(r['split'] for r in rows)),
                rows_sha256=hashlib.sha256(json.dumps(keys).encode()).hexdigest(),
                history_turns=describe(len(r['_history']) for r in rows))


def inference(model, rows):
    output = []
    cache = {}
    model.eval()
    with torch.no_grad():
        for start in range(0, len(rows), 32):
            part = rows[start:start + 32]
            logits, _ = model(*batch(part, history_cache=cache))
            output.extend(logits[i, :len(r['candidates'])].clone()
                          for i, r in enumerate(part))
    return output


def compare(rows, anchor_logits, student_logits):
    measurements = []
    for row, anchor, student in zip(rows, anchor_logits, student_logits):
        q = anchor.softmax(-1)
        p = student.softmax(-1)
        choice = int(anchor.argmax())
        measurements.append(dict(
            kl=float(forward_kl(anchor, student, torch.ones_like(anchor, dtype=torch.bool))),
            total_variation=float((p - q).abs().sum() / 2),
            top1_agreement=float(student.argmax() == choice),
            anchor_choice_probability=float(p[choice]),
            anchor_entropy=float(torch.distributions.Categorical(logits=anchor).entropy()),
            student_entropy=float(torch.distributions.Categorical(logits=student).entropy()),
            kind=row['candidates'][choice]['kind'], turn=row['turn']))

    def group(items):
        return {key: describe(item[key] for item in items) for key in
                ('kl', 'total_variation', 'top1_agreement', 'anchor_choice_probability',
                 'anchor_entropy', 'student_entropy')}

    return dict(all=group(measurements),
                by_anchor_kind={kind: group([m for m in measurements if m['kind'] == kind])
                                for kind in sorted({m['kind'] for m in measurements})},
                by_turn={name: group([m for m in measurements if (m['turn'] <= 30) == early])
                         for name, early in (('through_30', True), ('after_30', False))})


def flatten(model):
    return torch.cat([(p.grad if p.grad is not None else torch.zeros_like(p)).reshape(-1)
                      for p in model.parameters()]).detach().clone()


def gradient(model, rows, kind, *, anchor=None, advantage=None, returns=None):
    model.zero_grad(set_to_none=True)
    # Each model rebuilds its own recurrent state from the same raw history.
    tensors = batch(rows)
    logits, values = model(*tensors)
    chosen = torch.tensor([r['choice'] for r in rows])
    dist = torch.distributions.Categorical(logits=logits)
    if kind == 'actor':
        ratio = (dist.log_prob(chosen) - torch.tensor([r['log_probability'] for r in rows])).exp()
        loss = -torch.minimum(ratio * advantage, ratio.clamp(.8, 1.2) * advantage).mean()
    elif kind == 'value':
        loss = .5 * (values - returns).square().mean()
    elif kind == 'entropy':
        loss = -.01 * dist.entropy().mean()
    elif kind == 'hard_replay':
        loss = .1 * torch.nn.functional.cross_entropy(logits, chosen)
    elif kind == 'bc_anchor':
        with torch.no_grad():
            target, _ = anchor(*batch(rows))
        loss = .1 * forward_kl(target, logits, tensors[4]).mean()
    else:
        raise ValueError(kind)
    loss.backward()
    return float(loss.detach()), flatten(model)


def cosine(left, right):
    denominator = float(left.norm() * right.norm())
    return float(torch.dot(left, right)) / denominator if denominator > 1e-20 else None


def inspect_gradients(model, anchor, rows, replay):
    advantage, returns = advantages(rows)
    advantage = torch.tensor(advantage)
    advantage = (advantage - advantage.mean()) / advantage.std(unbiased=False).clamp(min=1e-6)
    ids = torch.linspace(0, len(rows) - 1, min(64, len(rows))).long().unique().tolist()
    selected = [rows[i] for i in ids]
    losses, gradients = {}, {}
    for kind in ('actor', 'value', 'entropy', 'hard_replay', 'bc_anchor'):
        losses[kind], gradients[kind] = gradient(
            model, replay if kind in ('hard_replay', 'bc_anchor') else selected, kind,
            anchor=anchor, advantage=advantage[ids], returns=torch.tensor(returns)[ids])
    main = gradients['actor'] + gradients['value'] + gradients['entropy']
    return dict(ppo_rows=identity(selected), replay_rows=identity(replay), scaled_losses=losses,
                scaled_gradient_norms={k: float(v.norm()) for k, v in gradients.items()},
                cosine_with_actor={k: cosine(gradients['actor'], v) for k, v in gradients.items()},
                cosine_with_value={k: cosine(gradients['value'], v) for k, v in gradients.items()},
                hard_vs_anchor_cosine=cosine(gradients['hard_replay'], gradients['bc_anchor']),
                combined={k: dict(norm=float((main + gradients[k]).norm()),
                                  actor_cosine=cosine(main + gradients[k], gradients['actor']))
                          for k in ('hard_replay', 'bc_anchor')},
                note='64 evenly spread PPO decisions, normalized on the full batch; same 64 '
                     'eligible replay states for both auxiliary targets. Diagnostic mean, not '
                     'the production window-equal logical-batch objective. Coefficients .5/.01/.1; '
                     'historical 60-turn rewards; no optimizer step.')


def inspect(root, fmt):
    directory = root / fmt
    state_path = directory / 'state.json'
    state = json.loads(state_path.read_text())
    history = [h for h in state['history'] if h['method'] == 'ppo']
    anchor_path = directory / 'last_bc.pt'
    anchor, saved = load_model(anchor_path, fmt)
    anchor.eval().requires_grad_(False)
    anchor_before = weights_digest(anchor)
    source_paths = {anchor_path, state_path}
    result = dict(anchor=dict(path=str(anchor_path), checkpoint_sha256=digest(anchor_path),
                              weights_sha256=anchor_before, version=saved['runner']['version']),
                  historical_batches=len(history), training_cohorts=[])

    paths = sorted(directory.glob('data/teacher-*.jsonl.gz'))
    source_paths.update(paths)
    admission = {}
    validation = read_shards(paths, partition='validation', limit=512, seed=20261017,
                             format_name=fmt, stats=admission)
    assert validation and all(r['split'] == 'validation' for r in validation)
    baseline = inference(anchor, validation)
    result['validation'] = dict(identity=identity(validation), admission=admission, models={})
    for name in ('last_bc.pt', 'selected.pt', 'last_ppo.pt'):
        path = directory / name
        source_paths.add(path)
        model, saved = load_model(path, fmt)
        before = weights_digest(model)
        measured = compare(validation, baseline, inference(model, validation))
        assert weights_digest(model) == before
        result['validation']['models'][name] = dict(
            checkpoint_sha256=digest(path), weights_sha256=before,
            version=saved['runner']['version'], comparison=measured)

    for h in (history[0], history[-1]):
        schedule = directory / 'schedules' / f"ppo-batch-{h['batch']:06}.json"
        jobs = json.loads(schedule.read_text())
        paths = [Path(j['shard']) for j in jobs]
        rows = read_shards(paths, format_name=fmt)
        assert rows and all(r['split'] == 'train' and r['source'] == 'policy' for r in rows)
        model_path = Path(jobs[0]['bots'][jobs[0]['meta']['seat'] - 1]).parent / 'model.pt'
        source_paths.update([schedule, model_path, *paths])
        model, _ = load_model(model_path, fmt)
        before = weights_digest(model)
        version = int(jobs[0]['meta']['version'].removeprefix('v'))
        paths = []
        for path in state['teacher_shards'] + state['dagger_shards'] + state['policy_shards']:
            match = re.search(r'rollout-(\d+)-', Path(path).name)
            if not match or int(match.group(1)) <= h['batch']:
                paths.append(Path(path))
        source_paths.update(paths)
        pool = read_shards(paths, partition='train', limit=2048, seed=20261017 + version, format_name=fmt)
        sampler = make_bc_sampler(pool, allow_policy=True, exclude_teacher_impl='gpt6astra',
                                  exclude_teacher_sha=jobs[0]['meta']['teacher_source_sha256'])
        replay = sampler.sample(64, rng=random.Random(20261106))
        assert all(r['source'] == 'policy' and r['split'] == 'train' for r in replay)
        ids = torch.linspace(0, len(rows) - 1, min(128, len(rows))).long().unique().tolist()
        selected = [rows[i] for i in ids]
        cohort = dict(batch=h['batch'], version=version, identity=identity(selected),
                      policy_weights_sha256=before, source_pool_rows=len(pool),
                      excluded_control_rows=sampler.rows_excluded,
                      rehearsal_identities=sampler.source_identities,
                      logged_excluded_control_rows=h['rehearsal_rows_excluded'],
                      rehearsal_log_match=(sampler.rows_excluded == h['rehearsal_rows_excluded']
                                           and sampler.source_identities == h['rehearsal_sources']),
                      comparison=compare(selected, inference(anchor, selected), inference(model, selected)),
                      gradients=inspect_gradients(model, anchor, rows, replay))
        assert weights_digest(model) == before
        assert weights_digest(anchor) == anchor_before
        assert all(p.grad is None for p in anchor.parameters())
        result['training_cohorts'].append(cohort)
        print(fmt, 'batch', h['batch'], 'complete', flush=True)
    result['input_files'] = [dict(path=str(path), sha256=digest(path)) for path in sorted(source_paths)]
    result['assertions'] = dict(anchor_weights_unchanged=True, student_weights_unchanged=True,
                                anchor_no_grad=True, training_states_policy_only=True,
                                validation_not_used_for_gradients=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--format', choices=('duel', 'team2v2'), required=True)
    args = parser.parse_args()
    torch.set_num_threads(1)
    result = dict(format=args.format, torch_version=torch.__version__,
                  seed=20261106, diagnostic=inspect(args.run, args.format))
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
