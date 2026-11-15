"""Freeze and, with approval, run only the #356 optimizer diagnostic on copies."""
from collections import defaultdict
import json
from pathlib import Path
import random
from statistics import mean
import sys
import time

import torch

from learning.bc_anchor import weights_sha256
from learning.common import read_json, sha256
from learning.data import advantages, read_shards
from learning.export import load_model
from learning.model import batch
from learning.ppo import KL_LIMIT, update
from learning.tasks import TASK_ID
from verification.duel_ppo_comparison_20261106.audit import write_new

from review import verify_capture
from replay import normalized

SINGLE_LIMIT = 120
TOTAL_LIMIT = 1200
STOCK_LR = 1e-4
HALF_LR = 5e-5
PLAN_SEED = 2026111756


def trajectories(jobs):
    return read_shards([Path(j['shard']) for j in jobs],format_name='duel',expected_task=TASK_ID)


def scored_inputs(base):
    earliest=Path('/home/tongshu/acceptance/ppo322-formal-20261114-wGKDQ4/source/runs/ppo322/cells')
    rehearsal=[]
    for name in ('astra-202611141','astra-202611142'):
        rehearsal.extend(read_json(earliest/name/'duel/schedules/ppo-batch-000038.json'))
    return rehearsal


def freeze(destination,base):
    m,jobs,_,ledger,archive=verify_capture(base)
    roles={}
    for role in m['roles']:
        these=[j for j in jobs if j['meta']['role']==role]
        train=[j for j in these if j['meta']['map']=='the_freelands']
        check=[j for j in these if j['meta']['map']!='the_freelands']
        data=trajectories(train)
        assert len(train)==8 and len(check)==16 and all(r['split']=='train' for r in data)
        identity=m['roles'][role]
        state=torch.load(identity['path'],map_location='cpu',weights_only=False)
        assert weights_sha256(state['model'])==identity['weights_sha256']
        assert role=='bc' or state['optimizer']['param_groups'][0]['lr']==STOCK_LR
        roles[role]=dict(checkpoint=identity,adam='fresh' if role=='bc' else 'checkpoint',
                         training_games=[j['id'] for j in train], scored_holdback_games=[j['id'] for j in check],
                         on_policy_rows=len(data),shards={j['id']:ledger[j['id']]['trajectory_sha256'] for j in these})
    rehearsal=scored_inputs(base)
    control=read_shards([j['shard'] for j in rehearsal],partition='train',limit=1024,
                        format_name='duel',seed=PLAN_SEED,expected_task=TASK_ID)
    assert len(control)==1024 and all(r['source']=='policy' for r in control)
    m=dict(issue=356, capture_root=str(base), capture_archive_sha256=archive['archive_sha256'],
           runtime=m['runtime'], script_sha256=sha256(Path(__file__)),
           roles=roles,rehearsal={j['shard']:sha256(Path(j['shard'])) for j in rehearsal},
           rehearsal_rows=1024,seed=PLAN_SEED,epochs=4,minibatch=256,entropy=.01,bc_aux=.1,
           stock_lr=STOCK_LR,comparison_lr=HALF_LR,kl_limit=KL_LIMIT,
           condition='Stock KL stop before two effective passes on v38 and at least two PPO endpoints',
           progress_gate='More committed visits and higher held-back MC projection at at most +0.005 KL in at least two PPO copies',
           new_games=0,maximum_arms=8,seconds=dict(admission=120,per_arm=SINGLE_LIMIT,audit=120,total=TOTAL_LIMIT))
    write_new(destination,m)
    print(json.dumps(dict(sha256=sha256(destination),roles={k:r['on_policy_rows'] for k,r in roles.items()},
                          new_games=0,optimizer_updates=0),indent=2))


def heldback(model,rows):
    games=defaultdict(list)
    for row in rows: games[row['game_id']].append(row)
    ids={id(row):i for i,row in enumerate(rows)}
    sampled=[rows2[n*(len(rows2)-1)//7] for rows2 in games.values() for n in range(8)]
    adv,_=advantages(rows,lam=1.)
    mc=normalized(adv)[[ids[id(row)] for row in sampled]].double()
    prior={}
    with torch.no_grad():
        for offset in range(0,len(sampled),16):
            segment=sampled[offset:offset+16]
            logits=model(*batch(segment,history_cache=prior))[0].double().log_softmax(-1)
            for i,row in enumerate(segment):
                yield logits[i,:len(row['candidates'])],row['choice'],float(mc[offset+i])


def compare(before,after):
    kl,projection=[],[]
    for (a,p,m),(b,q,n) in zip(before,after,strict=True):
        assert p==q and m==n
        kl.append(float((a.exp()*(a-b)).sum()))
        projection.append(m*float(b[p]-a[p]))
    return dict(heldback_rows=len(kl),exact_forward_kl=mean(kl),mc_log_probability_projection=mean(projection))


def execute(manifest,out):
    started=time.time()
    launch=read_json(manifest)
    assert launch['script_sha256']==sha256(Path(__file__)) and KL_LIMIT==launch['kl_limit']==.02
    base=Path(launch['capture_root'])
    m,jobs,_,ledger,archive=verify_capture(base)
    assert archive['archive_sha256']==launch['capture_archive_sha256'] and m['runtime']==launch['runtime']
    by_id={j['id']:j for j in jobs}
    control=launch['rehearsal']
    assert all(sha256(Path(p))==s for p,s in control.items())
    rehearsal=read_shards(list(control),partition='train',limit=1024,format_name='duel',
                           seed=PLAN_SEED,expected_task=TASK_ID)
    assert len(rehearsal)==1024
    for role,x in launch['roles'].items():
        assert x['checkpoint']==m['roles'][role]
        assert x['shards']=={j:ledger[j]['trajectory_sha256'] for j in x['training_games']+x['scored_holdback_games']}
    assert time.time()-started<=launch['seconds']['admission']

    def one(role,lr):
        x=launch['roles'][role]
        clock=time.time()
        deadline=min(clock+SINGLE_LIMIT,started+TOTAL_LIMIT-120)
        random.seed(PLAN_SEED)
        torch.manual_seed(PLAN_SEED)
        candidate,state=load_model(Path(x['checkpoint']['path']),'duel')
        optimizer=torch.optim.Adam(candidate.parameters(),lr=STOCK_LR)
        if x['adam']=='checkpoint': optimizer.load_state_dict(state['optimizer'])
        for g in optimizer.param_groups: g['lr']=lr
        candidate.eval()
        train=trajectories([by_id[j] for j in x['training_games']])
        check=trajectories([by_id[j] for j in x['scored_holdback_games']])
        assert len(train)==x['on_policy_rows']
        before=list(heldback(candidate,check))
        learning=update(candidate,optimizer,train,bc_records=rehearsal,epochs=4,minibatch=256,
                        deadline=deadline,entropy=.01,bc_aux=.1,allow_policy_rehearsal=True,
                        plan_seed=PLAN_SEED,ppo_aux_target='historical_action')
        candidate.eval()
        after=list(heldback(candidate,check))
        assert time.time()<=deadline and not learning['interrupted']
        return dict(lr=lr, ledger=learning, wall_seconds=time.time()-clock,
                    final_weights_sha256=weights_sha256(candidate.state_dict()), **compare(before,after))

    stock={r:one(r,STOCK_LR) for r in launch['roles']}
    stopped={r for r,x in stock.items() if x['ledger']['kl_stopped'] and x['ledger']['effective_dataset_passes']<2.}
    triggered='bc' in stopped and len(stopped)>=3
    half={r:one(r,HALF_LR) for r in stock} if triggered else {}
    better=[]
    for r,x in half.items():
        y=stock[r]
        if (r!='bc' and x['ledger']['committed_decisions']>y['ledger']['committed_decisions']
                and x['mc_log_probability_projection']>y['mc_log_probability_projection']
                and x['exact_forward_kl']<=y['exact_forward_kl']+.005):
            better.append(r)
    assert time.time()-started<=TOTAL_LIMIT
    write_new(out,dict(manifest_sha256=sha256(manifest),stock=stock,comparison=half,
                       comparable_ppo_improvements=better,followup_warranted=len(better)>=2,
                       comparison_triggered=triggered,new_games=0,wall_seconds=time.time()-started))


if __name__=='__main__':
    torch.set_num_threads(1)
    action,path,argument,*args=sys.argv[1:]
    p=Path(path).resolve()
    if action=='prepare':
        freeze(p,Path(argument).resolve())
    elif action=='run':
        assert sha256(p)==argument
        out=Path(args[0]).resolve()
        assert not out.exists()
        execute(p,out)
    else:
        raise ValueError('expected prepare or run')
