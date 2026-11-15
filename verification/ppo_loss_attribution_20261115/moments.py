"""Check the inherited-Adam control at the exact first #356 proposal."""
from pathlib import Path
import sys
import time

import torch

from audit import (MANIFEST_SHA, ObserveOptimizer, ProposalCaptured, holdback, match, proposal, readout)
from learning import ppo
from learning.bc_anchor import weights_sha256
from learning.common import read_json, sha256
from learning.data import read_shards
from learning.export import load_model
from learning.tasks import TASK_ID
from optimizer_probe import trajectories
from verification.duel_ppo_comparison_20261106.audit import write_new
import random


def observe(model, train, rehearsal, settings):
    observer = ObserveOptimizer(model)
    random.seed(settings['seed'])
    try:
        ppo.update(model, observer, train, bc_records=rehearsal, epochs=settings['epochs'],
                   minibatch=settings['minibatch'], entropy=settings['entropy'], bc_aux=settings['bc_aux'],
                   allow_policy_rehearsal=True, plan_seed=settings['seed'])
    except ProposalCaptured:
        pass
    assert observer.observed is not None
    return observer.observed


def main(manifest, attribution, out):
    started = time.monotonic()
    m = read_json(manifest)
    a = read_json(attribution)
    assert sha256(manifest) == a['manifest_sha256'] == MANIFEST_SHA and a['new_games'] == a['committed_updates'] == 0
    assert sha256(Path(__file__).with_name('audit.py')) == a['script_sha256']
    jobs = {j['id']: j for j in read_json(Path(m['capture_root']) / 'capture-schedule.json')}
    assert all(sha256(Path(p)) == s for p, s in m['rehearsal'].items())
    rehearsal = read_shards(list(m['rehearsal']), partition='train', limit=m['rehearsal_rows'],
                            format_name='duel', seed=m['seed'], expected_task=TASK_ID)
    scores = {}
    for name, spec in m['roles'].items():
        c = spec['checkpoint']
        assert c == a['roles'][name]['checkpoint'] and sha256(Path(c['path'])) == c['checkpoint_sha256']
        assert all(sha256(Path(jobs[j]['shard'])) == digest for j, digest in spec['shards'].items())
        model, state = load_model(Path(c['path']), 'duel')
        model.train()
        optimizer = state['optimizer'] if spec['adam'] == 'checkpoint' else None
        train = trajectories([jobs[j] for j in spec['training_games']])
        grads = observe(model, train, rehearsal, m)
        zero = [None if g is None else torch.zeros_like(g) for g in grads]
        base = {n: p.detach() for n, p in model.named_parameters()}
        inputs, meta = holdback([jobs[j] for j in spec['scored_holdback_games']])
        baseline = readout(model, base, inputs, meta)
        def evaluate(weights):
            return readout(model, weights, inputs, meta, baseline)
        full_weights = proposal(base, optimizer, grads, m['stock_lr'])
        moment_weights = proposal(base, optimizer, zero, m['stock_lr'])
        full, moment = evaluate(full_weights), evaluate(moment_weights)
        original = a['roles'][name]['proposals'][0]
        assert original['step'] == 0 and abs(full['kl'] - original['full']['kl']) < 1e-8
        target = min(full['kl'], moment['kl'])
        scores[name] = dict(full=full, moments_only=moment, active_parameters=sum(g is not None for g in grads))
        if optimizer:
            assert target > 0
            mf = match(full_weights, full, target, base, evaluate)
            mm = match(moment_weights, moment, target, base, evaluate)
            assert abs(mf['kl'] - mm['kl']) <= .01001 * target
            scores[name].update(matched_full=mf, matched_moments=mm)
        else:
            assert all(torch.equal(base[k], moment_weights[k]) for k in base)
        assert weights_sha256(model.state_dict()) == c['weights_sha256']
        print(f'{name} full_kl={full["kl"]:.8g} moments_only_kl={moment["kl"]:.8g}', flush=True)
    write_new(out, dict(attribution_sha256=sha256(attribution), scores=scores,
                        wall_seconds=time.monotonic() - started, new_games=0, committed_updates=0))


if __name__ == '__main__':
    torch.set_num_threads(1)
    main(*(Path(p).resolve() for p in sys.argv[1:]))
