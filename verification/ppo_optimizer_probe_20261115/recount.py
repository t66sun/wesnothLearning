"""Independently recount the #356 optimizer probe from its frozen inputs and final cursor."""
from collections import Counter, defaultdict
import json
import math
from pathlib import Path
import sys

import torch

from learning.common import read_json, sha256
from learning.data import read_shards
from learning.export import load_model
from learning.ppo import _epoch_order, _plan_hash, _target_key
from learning.tasks import TASK_ID
from learning.updates import prepare, setup

LAUNCH_SHA = '36b2cdbb84b1df705d677a2a1dbeca343d7f92b39b7f5ea837454d0939bffad2'


def bucket(rows):
    groups = defaultdict(Counter)
    for row in rows:
        groups['turn_band']['01-05' if row['turn'] <= 5 else '06-15' if row['turn'] <= 15 else '16-30'] += 1
        groups['action'][row['candidates'][row['choice']]['kind']] += 1
    return groups


def reconstruct(arm, spec, windows, count, steps, epochs, seed):
    ledger = arm['ledger']
    cursor = ledger['cursor']
    assert not ledger['interrupted'] and arm['wall_seconds'] <= 120
    assert cursor['plan_seed'] == seed and cursor['scope'] == 'batch'
    stopped = ledger['kl_stopped']
    assert stopped == (ledger['exit'] == 'kl_stop')
    assert (ledger['approx_kl'] > .02) == stopped
    committed, rejected, never = [], [], []
    n_committed = 0
    for epoch in range(epochs):
        order = _epoch_order(seed, epoch, len(windows))
        if cursor['epoch'] == epoch:
            assert cursor['plan_hash'] == _plan_hash(windows, order)
        for step in range(steps):
            batch = order[step*count:(step+1)*count]
            if (epoch, step) < (cursor['epoch'], cursor['step']):
                committed.extend(batch)
                n_committed += 1
            elif stopped and (epoch, step) == (cursor['epoch'], cursor['step']):
                rejected.extend(batch)
            else:
                never.extend(batch)
    assert n_committed == ledger['updates'] == ledger['committed_steps']
    assert len(committed) == ledger['committed_window_visits']
    assert len(rejected)+len(never) == ledger['stopped_by_kl_windows'] if stopped else not rejected and not never
    visit = lambda indices: [r for i in indices for r in windows[i]]
    c, r, n = map(visit,(committed,rejected,never))
    assert len(c)==ledger['committed_decisions'] and len(c)+len(r)==ledger['inspected_decisions']
    assert len(c)+len(r)+len(n)==spec['on_policy_rows']*epochs
    accepted = {_target_key(row) for row in c}
    unvisited = [row for win in windows for row in win if _target_key(row) not in accepted]
    assert len(accepted)+len(unvisited)==spec['on_policy_rows']
    assert ledger['policy_sha256_before']==spec['checkpoint']['weights_sha256']
    assert ledger['policy_sha256_after']==arm['final_weights_sha256']
    if n_committed:
        assert arm['final_weights_sha256']!=ledger['policy_sha256_before']
    assert math.isfinite(arm['exact_forward_kl']) and arm['exact_forward_kl']>=0
    assert math.isfinite(arm['mc_log_probability_projection']) and arm['heldback_rows']==128
    assert math.isclose(ledger['effective_dataset_passes'],len(c)/spec['on_policy_rows'],abs_tol=1e-12)
    return dict(accepted_steps=n_committed, planned_steps=steps*epochs, committed_visits=len(c),
                rejected_visits=len(r), unattempted_visits=len(n), distinct_targets=len(accepted),
                untouched_targets=len(unvisited), rejected_step_windows=len(rejected),
                effective_passes=ledger['effective_dataset_passes'], stopped=stopped,
                examined_gate_statistic=ledger['approx_kl'], holdback_kl=arm['exact_forward_kl'],
                holdback_mc_projection=arm['mc_log_probability_projection'],
                committed_strata=bucket(c),rejected_strata=bucket(r),untouched_strata=bucket(unvisited))


def main(root):
    probe=root/'optimizer-probe.json'
    result=root/'probe-result.json'
    assert (root/'probe-launcher.exit').read_text().strip()=='0' and sha256(probe)==LAUNCH_SHA
    m, x = read_json(probe),read_json(result)
    assert x['manifest_sha256']==LAUNCH_SHA and x['new_games']==0 and 0<x['wall_seconds']<=1200
    base=Path(m['capture_root'])
    assert sha256(base/'capture-metadata.tar.gz')==m['capture_archive_sha256']
    jobs={j['id']:j for j in read_json(base/'capture-schedule.json')}
    assert set(x['stock'])==set(m['roles'])
    assert not x['comparison'] or set(x['comparison'])==set(m['roles'])
    for path,expected in m['rehearsal'].items():
        assert sha256(Path(path))==expected
    rehearsal=read_shards(list(m['rehearsal']),partition='train',limit=m['rehearsal_rows'],
                          format_name='duel',seed=m['seed'],expected_task=TASK_ID)
    assert len(rehearsal)==m['rehearsal_rows']
    rows={}
    for name,spec in m['roles'].items():
        for game,expected in spec['shards'].items():
            assert sha256(Path(jobs[game]['shard']))==expected
        path=Path(spec['checkpoint']['path'])
        assert sha256(path)==spec['checkpoint']['checkpoint_sha256']
        model,_=load_model(path,'duel')
        sample=read_shards([jobs[j]['shard'] for j in spec['training_games']],
                            format_name='duel',expected_task=TASK_ID)
        _,windows,count,_,steps=setup(model,prepare(model,sample,rehearsal),m['minibatch'])
        assert sum(map(len,windows))==len(sample)==spec['on_policy_rows']
        arms={}
        for label,lr in (('stock',m['stock_lr']),('comparison',m['comparison_lr'])):
            if name not in x[label]:
                continue
            a=x[label][name]
            assert a['lr']==lr
            arms[label]=reconstruct(a,spec,windows,count,steps,m['epochs'],m['seed'])
        rows[name]=arms
    trigger={r for r,a in rows.items() if a['stock']['stopped'] and a['stock']['effective_passes']<2}
    expected='bc' in trigger and len(trigger)>=3
    assert expected==x['comparison_triggered']==bool(x['comparison'])
    improved=[]
    for r,pair in rows.items():
        if not expected or r=='bc':
            continue
        base,alt=pair['stock'],pair['comparison']
        if (alt['committed_visits']>base['committed_visits'] and alt['holdback_mc_projection']>base['holdback_mc_projection']
                and alt['holdback_kl']<=base['holdback_kl']+.005):
            improved.append(r)
    assert improved==x['comparable_ppo_improvements'] and (len(improved)>=2)==x['followup_warranted']
    print(json.dumps(dict(manifest_sha256=LAUNCH_SHA, result_sha256=sha256(result), rows=rows,
                          trigger_roles=sorted(trigger), comparison_triggered=expected,
                          eligible_ppo_copies=improved, followup_warranted=len(improved)>=2,
                          wall_seconds=x['wall_seconds'], new_games=0),indent=2))


if __name__=='__main__':
    torch.set_num_threads(1)
    main(Path(sys.argv[1]).resolve())
