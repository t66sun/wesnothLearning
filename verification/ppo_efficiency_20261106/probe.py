"""Frozen PPO cost/shift diagnostic: no optimizer, games, or checkpoint writes."""
import argparse
from collections import defaultdict
from contextlib import contextmanager
import json
import os
from pathlib import Path
import platform
import random
import re
import time

import torch
from learning.data import advantages, make_bc_sampler, read_shards
from learning.export import load_model
from learning.model import batch
from learning.ppo import _digest, _epoch_order
from learning.sequences import read_raw_shards
from learning.updates import prepare, rollout_identity, setup

from census import sha256, summary


class Timings:
    def __init__(self):
        self.values = defaultdict(lambda: dict(wall_seconds=0., cpu_seconds=0., calls=0))

    @contextmanager
    def scope(self, name):
        wall, cpu = time.perf_counter(), time.process_time()
        try:
            yield
        finally:
            value = self.values[name]
            value['wall_seconds'] += time.perf_counter() - wall
            value['cpu_seconds'] += time.process_time() - cpu
            value['calls'] += 1

    def call(self, name, function, *args, **kwargs):
        with self.scope(name):
            return function(*args, **kwargs)


def model_path(job):
    return Path(job['bots'][job['meta']['seat'] - 1]).parent / 'model.pt'


def checkpoint_difference(before, after):
    delta = sum((a.detach() - b.detach()).square().sum().item()
                for a, b in zip(before.parameters(), after.parameters())) ** .5
    norm = sum(a.detach().square().sum().item() for a in before.parameters()) ** .5
    return dict(parameter_l2_change=delta, relative_parameter_l2_change=delta / norm)


def score(model, rows, windows, micro):
    model.eval()
    scores = {}
    cache = {}
    with torch.no_grad():
        for window in windows:
            for offset in range(0, len(window), micro):
                selected = window[offset:offset + micro]
                logits, values = model(*batch(selected, history_cache=cache))
                logps = logits.log_softmax(-1)
                for index, row in enumerate(selected):
                    scores[id(row)] = (logps[index, :len(row['candidates'])].clone(), float(values[index]))
    return scores


def movement(before, after, rows, windows, micro, history):
    old = score(before, rows, windows, micro)
    new = score(after, rows, windows, micro)
    per_window = []
    baseline_error = []
    baseline_value_error = []
    for window in windows:
        sampled = []
        exact = []
        for row in window:
            prior, prior_value = old[id(row)]
            current, _ = new[id(row)]
            action = row['choice']
            difference = current[action] - row['log_probability']
            sampled.append(float(difference.exp() - 1 - difference))
            exact.append(float((prior.exp() * (prior - current)).sum()))
            baseline_error.append(abs(float(prior[action]) - row['log_probability']))
            baseline_value_error.append(abs(prior_value - row['value']))
        per_window.append(dict(rows=len(window), sampled_kl=sum(sampled) / len(sampled),
                               exact_kl=sum(exact) / len(exact)))
    stopped = None
    if history['kl_stopped']:
        cursor = history['cursor']
        order = _epoch_order(cursor['plan_seed'], cursor['epoch'], len(windows))
        indices = order[cursor['step'] * 4:(cursor['step'] + 1) * 4]
        stopped = dict(window_indices=indices,
            sampled_kl=sum(per_window[i]['sampled_kl'] for i in indices) / len(indices),
            exact_kl=sum(per_window[i]['exact_kl'] for i in indices) / len(indices),
            decisions=sum(per_window[i]['rows'] for i in indices))
    return dict(**checkpoint_difference(before, after),
        whole_batch_window_mean_sampled_kl=sum(w['sampled_kl'] for w in per_window) / len(per_window),
        whole_batch_window_mean_exact_kl=sum(w['exact_kl'] for w in per_window) / len(per_window),
        whole_batch_row_mean_exact_kl=sum(w['exact_kl'] * w['rows'] for w in per_window) / len(rows),
        logged_kl=history['approx_kl'], stopped_selection=stopped,
        baseline_logp_max_error=max(baseline_error), baseline_value_max_error=max(baseline_value_error),
        windows=per_window)


def one_pass(model, rows, bc, windows, micro, sequence_count, reward, seed, timings):
    """One production-order epoch, fixed weights; backwards use equal window weights."""
    model.train()
    a, returns = advantages(rows)
    a = torch.tensor(a)
    a = (a - a.mean()) / a.std(unbiased=False).clamp(min=1e-6)
    returns = torch.tensor(returns)
    row_ids = {id(row): index for index, row in enumerate(rows)}
    sampler = make_bc_sampler(bc, allow_policy=True, exclude_teacher_impl='gpt6astra')
    rng = random.Random(seed)
    order = _epoch_order(20261017, 0, len(windows))
    original_context = model.context
    role = 'ppo'

    def context(*args, **kwargs):
        return timings.call(role + '_history_context_inclusive', original_context, *args, **kwargs)

    model.context = context
    try:
        with timings.scope('one_epoch_total'):
            for start in range(0, len(order), sequence_count):
                selected = [windows[i] for i in order[start:start + sequence_count]]
                model.zero_grad(set_to_none=True)
                cache = {}
                for window in selected:
                    for offset in range(0, len(window), micro):
                        current = window[offset:offset + micro]
                        role = 'ppo'
                        tensors = timings.call('ppo_pack', batch, current, history_cache=cache)
                        logits, values = timings.call('ppo_forward_inclusive', model, *tensors)
                        with timings.scope('ppo_objective'):
                            dist = torch.distributions.Categorical(logits=logits)
                            choices = torch.tensor([r['choice'] for r in current])
                            logp = dist.log_prob(choices)
                            old = torch.tensor([r['log_probability'] for r in current])
                            ratio = (logp - old).exp()
                            indices = [row_ids[id(r)] for r in current]
                            actor = -torch.minimum(ratio * a[indices], ratio.clamp(.8, 1.2) * a[indices]).mean()
                            loss = actor + .5 * (values - returns[indices]).square().mean() - reward['entropy'] * dist.entropy().mean()
                        replay = timings.call('rehearsal_sample', sampler.sample, len(current), rng=rng)
                        role = 'rehearsal'
                        tensors = timings.call('rehearsal_pack', batch, replay, history_cache=cache)
                        bc_logits, _ = timings.call('rehearsal_forward_inclusive', model, *tensors)
                        with timings.scope('rehearsal_objective'):
                            loss = loss + reward['bc_aux'] * torch.nn.functional.cross_entropy(
                                bc_logits, torch.tensor([r['choice'] for r in replay]))
                            weighted = loss * len(current) / len(window) / len(selected)
                        timings.call('combined_backward', weighted.backward)
                        assert torch.isfinite(weighted)
        model.zero_grad(set_to_none=True)
    finally:
        model.context = original_context
    return dict(supervised_rows=len(rows), logical_steps=(len(windows) + sequence_count - 1) // sequence_count,
                rehearsal_identities=sampler.source_identities, excluded_rehearsal_rows=sampler.rows_excluded)


def inspect_batch(root, fmt, state, history, repetitions):
    directory = root / fmt
    schedule_path = directory / 'schedules' / f"ppo-batch-{history['batch']:06}.json"
    jobs = json.loads(schedule_path.read_text())
    before_path = model_path(jobs[0])
    next_path = directory / 'schedules' / f"ppo-batch-{history['batch'] + 1:06}.json"
    after_path = model_path(json.loads(next_path.read_text())[0])
    model, _ = load_model(before_path, fmt)
    after, _ = load_model(after_path, fmt)
    assert _digest(model) == history['policy_sha256_before']
    assert _digest(after) == history['policy_sha256_after']
    version = int(jobs[0]['meta']['version'].removeprefix('v'))
    corpus = []
    for path in state['teacher_shards'] + state['dagger_shards'] + state['policy_shards']:
        match = re.search(r'rollout-(\d+)-', Path(path).name)
        if match is None or int(match.group(1)) <= history['batch']:
            corpus.append(path)
    paths = [j['shard'] for j in jobs]
    measurements = []
    input_paths = [schedule_path, next_path, before_path, after_path] + list(map(Path, paths))
    for repeat in range(repetitions):
        timing = Timings()
        read_stats = {}
        rows = timing.call('read_rollout', read_shards, paths, format_name=fmt)
        bc = timing.call('read_rehearsal', read_shards, corpus, partition='train', limit=2048,
                         seed=20261017 + version, format_name=fmt, stats=read_stats)
        assert len(rows) == history['eligible_decisions']
        assert read_stats == history['reads']['bc']
        timing.call('rollout_content_identity', rollout_identity, rows)
        timing.call('rehearsal_content_identity', rollout_identity, bc)
        rows = timing.call('prepare_validate', prepare, model, rows, bc)
        _, windows, count, micro, _ = setup(model, rows, 256)
        assert len(windows) == history['sequence_windows']
        if repeat == 0:
            warm = rows[:min(micro, len(rows))]
            logits, values = model(*batch(warm))
            (logits[:, 0].mean() + values.mean()).backward()
            model.zero_grad(set_to_none=True)
        work = one_pass(model, rows, bc, windows, micro, count, jobs[0]['reward_config'], 20261106, timing)
        assert _digest(model) == history['policy_sha256_before']
        measurements.append(dict(repetition=repeat, timings=dict(timing.values), work=work, read_stats=read_stats))
    shift = movement(model, after, rows, windows, micro, history)
    dagger_paths = [str(Path(p).with_name(Path(p).name.replace('.jsonl.gz', '.dagger.jsonl.gz'))) for p in paths]
    dagger_time = Timings()
    dagger = dagger_time.call('read_raw_dagger', read_raw_shards, dagger_paths, format_name=fmt)
    input_paths += list(map(Path, dagger_paths))
    return dict(format=fmt, batch=history['batch'], version=version, measurements=measurements, shift=shift,
        work_shape=dict(rows=len(rows), candidates=summary([len(r['candidates']) for r in rows]),
                        history_turns=summary([len(r['_history']) for r in rows]), windows=len(windows)),
        dagger=dict(raw_rows=len(dagger), supervised_rows=sum(r['choice'] >= 0 for r in dagger),
                    compressed_bytes=sum(Path(p).stat().st_size for p in dagger_paths),
                    timings=dict(dagger_time.values)),
        inputs={str(p): sha256(p) for p in input_paths})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--repetitions', type=int, default=2)
    args = parser.parse_args()
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    result = dict(host=platform.node(), python=platform.python_version(), torch=torch.__version__,
                  threads=torch.get_num_threads(), process_id=os.getpid(),
                  note='One frozen-weight epoch per repetition; optimizer is never constructed. First reads have cold process caches, not cold OS caches.',
                  batches=[])
    for fmt in ('duel', 'team2v2'):
        state = json.loads((args.run / fmt / 'state.json').read_text())
        history = [h for h in state['history'] if h['method'] == 'ppo']
        for entry in (history[0], history[len(history) // 2], history[-1]):
            print(fmt, entry['batch'], 'start', flush=True)
            result['batches'].append(inspect_batch(args.run, fmt, state, entry, args.repetitions))
            args.output.write_text(json.dumps(result, indent=2) + '\n')
            print(fmt, entry['batch'], 'complete', flush=True)
