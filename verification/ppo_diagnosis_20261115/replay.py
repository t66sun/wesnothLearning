"""Replay already recorded pure-Astra batches. This module does no game or optimizer work."""
from collections import Counter, defaultdict
from copy import copy
import json
import math
from pathlib import Path
import random
from statistics import mean, pvariance
import sys

import torch

from audit_archive import RUNS, terminal_points, records, weights
from learning.bc_anchor import weights_sha256
from learning.common import read_json, sha256
from learning.data import advantages, make_bc_sampler, read_shards
from learning.export import load_model
from learning.model import batch
from learning.sequences import training_windows
from learning.tasks import TASK_ID, value_target


def absolute_summary(values):
    ordered = sorted(abs(x) for x in values)
    return dict(max=ordered[-1], p95=ordered[int(len(ordered)*.95)])


def normalized(values):
    values = torch.tensor(values, dtype=torch.float32)
    return (values-values.mean())/values.std(unbiased=False).clamp(min=1e-6)


def forward(model, rows):
    pp, vv, hh, margin, action = [], [], [], [], []
    cache = {}
    with torch.no_grad():
        for start in range(0, len(rows), 32):
            part = rows[start:start+32]
            logits, v = model(*batch(part, history_cache=cache))
            dist = torch.distributions.Categorical(logits=logits)
            pp.extend(dist.log_prob(torch.tensor([r['choice'] for r in part])).tolist())
            vv.extend(v.tolist())
            hh.extend(dist.entropy().tolist())
            best = dist.probs.topk(min(2, logits.shape[-1]), dim=-1).values
            margin.extend((best[:,0]-best[:,1]).tolist() if best.shape[-1]==2 else best[:,0].tolist())
            action.extend(logits.argmax(-1).tolist())
    return dict(logp=pp, value=vv, entropy=hh, margin=margin, action=action)


def calibration(games):
    z = {key: rows[0]['terminal_reward'] for key,rows in games.items()}
    labels = [r['terminal_reward'] for rows in games.values() for r in rows]
    predicted = [r['value']+r['terminal_reward']-value_target(r) for rows in games.values() for r in rows]
    errors = [p-y for p,y in zip(predicted,labels)]
    summary = dict(games=len(games), rows=len(labels), mean_bias=mean(errors), mse=mean(e*e for e in errors),
                   explained_variance=(1-pvariance(errors)/pvariance(labels)) if pvariance(labels)>0 else None)
    per_game = []
    for key, rows in games.items():
        loo = mean(y for game,y in z.items() if game!=key)
        err = [r['value']-value_target(r) for r in rows]
        per_game.append((mean(err),mean(e*e for e in err)-(loo-z[key])**2))
    rng=random.Random(2026111755)
    draws=sorted(mean(x[1] for x in rng.choices(per_game,k=len(per_game))) for _ in range(10000))
    summary.update(equal_game_bias=mean(x[0] for x in per_game),
                   mse_minus_loo_game_constant=mean(x[1] for x in per_game),
                   mse_gap_ci=[draws[250],draws[9750]])
    return summary


def reward_and_clock(rows, adv, ret):
    phi = [r['terminal_reward']-value_target(r) for r in rows]
    games=defaultdict(list)
    for i,row in enumerate(rows):
        games[row['game_id'],row['side']].append(i)
        assert row['reward_config']['gamma']==1 and row['reward_config']['explore']==0
    bare=[0.]*len(rows)
    for ids in games.values():
        tail=ids[-1]
        v_next=0.
        continuation=0.
        for i,following in zip(reversed(ids),[None,*reversed(ids[1:])]):
            row=rows[i]
            span=0 if following is None else rows[following]['turn']-row['turn']
            this_v=row['value']+phi[i]
            actual=row['terminal_reward'] if i==tail else 0.
            continuation=actual+v_next-this_v+row['reward_config']['gae_lambda']**span*continuation
            bare[i]=continuation
            v_next=this_v
    mc,mc_ret=advantages(rows,lam=1.)
    expected=[value_target(r) for r in rows]
    assert max(abs(x-y) for x,y in zip(mc_ret,expected))<1e-9
    td=absolute_summary(a-b for a,b in zip(adv,bare))
    assert td['max']<1e-9
    row_index={id(row):i for i,row in enumerate(rows)}
    by_turn=defaultdict(list)
    window_weight={}
    windows=training_windows(rows)
    for win in windows:
        for r in win:
            i=row_index[id(r)]
            by_turn[r['game_id'],r['side'],r['turn']].append(i)
            window_weight[i]=1/(len(windows)*len(win))
    large={i for ids in by_turn.values() if len(ids)>=12 for i in ids}
    norm=normalized(adv).tolist()
    total=sum(abs(a)*window_weight[i] for i,a in enumerate(norm))
    large_turn_mass=sum(abs(norm[i])*window_weight[i] for i in large)/total
    balanced_total=sum(mean(abs(norm[i]) for i in ids) for ids in by_turn.values())
    balanced_large=sum(mean(abs(norm[i]) for i in ids) for ids in by_turn.values() if len(ids)>=12)
    signs=mean((a>=0)==(b>=0) for a,b in zip(norm,normalized(mc).tolist()))
    return dict(potential_coordinate_error=td, mc_telescopes=True, centered_sign_agreement_vs_mc=signs,
                own_turns=len(by_turn), twelve_plus_action_turns=sum(len(v)>=12 for v in by_turn.values()),
                twelve_plus_rows=len(large), equal_window_absolute_advantage_mass=large_turn_mass,
                equal_turn_absolute_advantage_mass=balanced_large/balanced_total)


def gradient_readout(model, rehearsal, rows, adv, ret):
    selected = training_windows(rows)[0][:16]
    index={id(r):i for i,r in enumerate(rows)}
    xs=[index[id(r)] for r in selected]
    logits,values=model(*batch(selected))
    d=torch.distributions.Categorical(logits=logits)
    logp=d.log_prob(torch.tensor([r['choice'] for r in selected]))
    old=torch.tensor([r['log_probability'] for r in selected])
    ratio=(logp-old).exp()
    a=normalized(adv)[xs]
    samples=make_bc_sampler(rehearsal,allow_policy=True).sample(len(selected),rng=random.Random(2026111757))
    other,_=model(*batch(samples))
    point=[-torch.minimum(ratio*a,ratio.clamp(.8,1.2)*a).mean(),
           .5*(values-torch.tensor(ret)[xs]).square().mean(),
           -.01*d.entropy().mean(), .1*torch.nn.functional.cross_entropy(other,torch.tensor([r['choice'] for r in samples]))]
    parameters=list(model.named_parameters())
    gradients=[torch.autograd.grad(loss,[p for _,p in parameters],retain_graph=True,allow_unused=True) for loss in point]
    grouping=defaultdict(list)
    for i,(name,_) in enumerate(parameters):
        grouping[name.partition('.')[0]].append(i)
    result={}
    for group, ids in grouping.items():
        data=[torch.cat([(grads[i] if grads[i] is not None else torch.zeros_like(parameters[i][1])).flatten()
                         for i in ids]) for grads in gradients]
        norms=[float(g.norm()) for g in data]
        cos=[float(torch.dot(data[0],g))/(norms[0]*n) if norms[0]*n else None for n,g in zip(norms,data)]
        result[group]=dict(weighted_norm=norms,cosine_to_actor=cos)
    return dict(loss_order=['actor','value','entropy','historical_action'],groups=result,
                rehearsal='first behavior batch policy rows; fixed micro-window probe')


def inspect_batch(duel, entry, outcomes, anchor, later):
    path=duel/'schedules'/f"ppo-batch-{entry['batch']:06d}.json"
    jobs=read_json(path)
    fmt='duel'
    shard_paths=[Path(j['shard']) for j in jobs]
    policy_path=Path(jobs[0]['bots'][jobs[0]['meta']['seat']-1]).parent/'model.pt'
    ident=weights(policy_path)
    assert ident['weights_sha256']==entry['policy_sha256_before']
    model,_=load_model(policy_path,fmt)
    model.eval()
    rows=read_shards(shard_paths,format_name=fmt)
    assert len(rows)==entry['eligible_decisions']
    games=defaultdict(list)
    for row in rows:
        assert row['source']=='policy' and row['task_id']==TASK_ID and row['value_valid'] and not row['truncated']
        games[row['game_id']].append(row)
    assert set(games)=={j['id'] for j in jobs}
    for j in jobs:
        seat=j['meta']['seat']
        points=terminal_points(j,outcomes[j['id']],seat)
        assert all(r['side']==seat and r['terminal_reward']==2*points/3-1 and
                   len(r['candidates'])>r['choice']>=0 for r in games[j['id']])
    assert sum(map(len,training_windows(rows)))==len(rows)
    positions=[i*(len(rows)-1)//127 for i in range(128)]
    selected=[rows[i] for i in positions]
    replay=forward(model,selected)
    logp=absolute_summary(g-r['log_probability'] for g,r in zip(replay['logp'],selected))
    value=absolute_summary(g-r['value'] for g,r in zip(replay['value'],selected))
    ratio=absolute_summary(math.exp(g-r['log_probability'])-1. for g,r in zip(replay['logp'],selected))
    assert logp['max']<=1e-5 and value['max']<=1e-5
    s=next(r for r in selected if r['choice']!=len(r['candidates'])-1 and len(r['candidates'])>3)
    alt=copy(s)
    alt['candidates']=list(s['candidates'])
    alt['candidates'][s['choice']],alt['candidates'][0 if s['choice'] else 1]=(alt['candidates'][0 if s['choice'] else 1],
                                                                                alt['candidates'][s['choice']])
    scramble=abs(forward(model,[alt])['logp'][0]-s['log_probability'])
    t=max((r for r in selected if r.get('_history')),key=lambda r:len(r['_history']))
    drop=abs(forward(model,[dict(t,_history=[])])['logp'][0]-t['log_probability'])
    adv,ret=advantages(rows)
    clock=reward_and_clock(rows,adv,ret)
    reference=forward(anchor,selected)
    measures=dict(logp=logp,value=value,ratio=ratio,control_candidate_swap=scramble,control_drop_prefix=drop,
                  sampled_matches_own_argmax=sum(r['choice']==i for r,i in zip(selected,replay['action'])),
                  argmax_differs_from_v38=sum(a!=b for a,b in zip(replay['action'],reference['action'])),
                  mean_entropy=mean(replay['entropy']),mean_v38_entropy_same_rows=mean(reference['entropy']),
                  mean_top2_probability_margin=mean(replay['margin']))
    return (dict(batch=entry['batch'],version=jobs[0]['meta']['version'],model=ident,
                 schedule_sha256=sha256(path),shards={p.name:sha256(p) for p in shard_paths},
                 rows=len(rows),replayed=len(selected),map_counts=Counter(j['meta']['map'] for j in jobs),
                 score=Counter(terminal_points(j,outcomes[j['id']],j['meta']['seat']) for j in jobs),
                 diagnostic=measures,critic=calibration(games),clock=clock,
                 gradients=gradient_readout(model,later,rows,adv,ret) if later else None),games,rows)


def main():
    path=Path(sys.argv[1])
    anchor_path=Path(read_json(path)['cohort']['bc']['path'])
    anchor,_=load_model(anchor_path,'duel')
    anchor.eval()
    base,late={},{}
    results={}
    for cell in sorted((RUNS['322']/'cells').glob('astra-*')):
        duel=cell/'duel'
        state=read_json(duel/'state.json')
        h=[r for r in state['history'] if r['method']=='ppo']
        jobs={r['id']:r for r in records(duel/'jobs.jsonl')}
        early,early_games,policy=inspect_batch(duel,h[0],jobs,anchor,None)
        final,final_games,_=inspect_batch(duel,h[-1],jobs,anchor,policy)
        assert early['model']['weights_sha256']==read_json(path)['cohort']['bc']['weights_sha256']
        prefix=cell.name
        base.update({(prefix,k):v for k,v in early_games.items()})
        late.update({(prefix,k):v for k,v in final_games.items()})
        results[prefix]=dict(v38=early,late_behavior=final)
    print(json.dumps(dict(batches=results, pooled_v38=calibration(base), pooled_late_behavior=calibration(late),
                          games_started=0, optimizer_updates=0), indent=2))


if __name__=='__main__':
    torch.set_num_threads(1)
    main()
