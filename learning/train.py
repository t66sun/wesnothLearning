import random
import time
from pathlib import Path
import torch
from .model import batch
from .data import advantages, validate_record, bc_sample, make_bc_sampler
from .sequences import training_windows, attach_histories
from .features import schema
from .formats import FORMATS, record_format
from .model import ARCHITECTURE


def checkpoint(path, model, optimizer, **metadata):
    state = dict(model=model.state_dict(), optimizer=optimizer.state_dict(),
                 python_rng=random.getstate(), torch_rng=torch.get_rng_state(),
                 cuda_rng=torch.cuda.get_rng_state_all() if next(model.parameters()).device.type=='cuda' else [],
                 features=schema(),architecture=ARCHITECTURE, **metadata)
    state['format']=model.format_name
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    torch.save(state, temporary)
    temporary.replace(path)


def restore_rng(state, device='cpu'):
    random.setstate(state['python_rng'])
    torch.set_rng_state(state['torch_rng'].cpu())
    if torch.device(device).type=='cuda' and state.get('cuda_rng'):
        torch.cuda.set_rng_state_all([r.cpu() for r in state['cuda_rng']])


def train(model, optimizer, records, method, epochs=4, minibatch=256, deadline=float('inf'),
          progress=None, on_step=None, bc_records=None, shaping_weight=None, entropy=.01, bc_aux=.1,
          allow_policy_rehearsal=False):
    if method not in ('bc', 'ppo'):
        raise ValueError('method must be bc or ppo')
    if not all('_history' in r for r in records): records=attach_histories(records)
    for r in records: validate_record(r, model.format_name)
    for r in bc_records or []: validate_record(r, model.format_name)
    records = [r for r in records if r['split'] == 'train']
    if not records:
        raise ValueError('no training games')
    if method == 'ppo' and len({r['version'] for r in records}) != 1:
        raise ValueError('PPO batch must use one frozen policy version')
    if method=='ppo':
        for key in ('reward_version','reward_formula_id','engine_id','rules_version','rng_version'):
            if len({r[key] for r in records})!=1: raise ValueError('PPO batch mixes '+key)
        if len({__import__('json').dumps(r['reward_config'],sort_keys=True) for r in records})!=1:
            raise ValueError('PPO batch mixes reward configurations')
    if method=='ppo' and any(r['source']!='policy' or (not r.get('value_valid',True) and not (r.get('truncated') and r.get('bootstrap_value') is not None)) for r in records):
        raise ValueError('PPO requires on-policy complete trajectories')
    if method=='ppo' and not bc_records: raise ValueError('PPO requires same-format BC rehearsal data')
    device = next(model.parameters()).device
    adv, ret = advantages(records,shaping_weight=shaping_weight) if method=='ppo' else ([0.]*len(records), [0.]*len(records))
    adv = torch.tensor(adv, dtype=torch.float32, device=device)
    ret = torch.tensor(ret, dtype=torch.float32, device=device)
    groups = {model.format_name: list(range(len(records)))}
    if any(not ids for ids in groups.values()):
        raise ValueError('a training update requires every configured format')
    for ids in groups.values():
        a = adv[ids]
        adv[ids] = (a - a.mean()) / a.std(unbiased=False).clamp(min=1e-6)
    model.train()
    windows=training_windows(records,turns=8)
    sequence_count=4 if device.type=='cpu' else 8
    micro=min(minibatch,32 if device.type=='cpu' else 64)
    if micro<1: raise ValueError('minibatch must be positive')
    row_index={id(r):i for i,r in enumerate(records)}
    window_index={id(r):w for w in windows for r in w}
    sampler=make_bc_sampler(records) if method=='bc' else None
    rehearsal_sampler=make_bc_sampler(bc_records, allow_policy=allow_policy_rehearsal) if method=='ppo' else None
    steps=max(1,(len(windows)+sequence_count-1)//sequence_count)
    start=progress or dict(epoch=0,step=0)
    loss_sum=start.get('loss_sum',0.);updates=start.get('updates',0)
    kl=0.;decisions_seen=start.get('decisions_seen',0)
    for epoch in range(start['epoch'],epochs):
        for step in range(start['step'] if epoch==start['epoch'] else 0,steps):
            if time.time() >= deadline:
                return dict(updates=updates, loss=loss_sum/max(1,updates), interrupted=True)
            optimizer.zero_grad()
            selected_windows=([window_index[id(r)] for r in sampler.sample(sequence_count)] if sampler
                              else random.choices(windows,k=sequence_count))
            total_value=0.;step_decisions=0
            for window in selected_windows:
                # Each window has equal weight; long games do not dominate short ones.
                for offset in range(0,len(window),micro):
                    if time.time()>=deadline:
                        optimizer.zero_grad();return dict(updates=updates,loss=loss_sum/max(1,updates),interrupted=True)
                    rows=window[offset:offset+micro]
                    logits,values=model(*batch(rows,device))
                    dist=torch.distributions.Categorical(logits=logits)
                    chosen=torch.tensor([r['choice'] for r in rows],device=device)
                    logp=dist.log_prob(chosen)
                    if method=='bc':
                        valid=torch.tensor([r.get('value_valid',True) for r in rows],device=device,dtype=torch.bool)
                        targets=torch.tensor([r.get('reward',0) or 0 for r in rows],device=device)
                        loss=-logp.mean()+.1*auxiliary_loss(logits,rows)
                        if valid.any(): loss=loss+.5*(values[valid]-targets[valid]).square().mean()
                    else:
                        selected=[row_index[id(r)] for r in rows]
                        old=torch.tensor([r['log_probability'] for r in rows],device=device)
                        ratio=torch.exp(logp-old);a=adv[selected]
                        kl=float(((ratio-1)-(logp-old)).mean().detach())
                        if kl>.02:
                            optimizer.zero_grad();return dict(updates=updates,loss=loss_sum/max(1,updates),interrupted=False,approx_kl=kl,kl_stopped=True)
                        loss=-torch.minimum(ratio*a,ratio.clamp(.8,1.2)*a).mean()+.5*(values-ret[selected]).square().mean()-entropy*dist.entropy().mean()
                        rehearsal=rehearsal_sampler.sample(len(rows))
                        bc_logits,_=model(*batch(rehearsal,device))
                        loss=loss+bc_aux*torch.nn.functional.cross_entropy(bc_logits,torch.tensor([r['choice'] for r in rehearsal],device=device))
                    if not torch.isfinite(loss): raise ValueError('nonfinite training loss')
                    weighted=loss*len(rows)/len(window)/sequence_count
                    weighted.backward();total_value+=float(weighted.detach());step_decisions+=len(rows)
            torch.nn.utils.clip_grad_norm_(model.parameters(), .5)
            if time.time()>=deadline:
                optimizer.zero_grad()
                return dict(updates=updates,loss=loss_sum/max(1,updates),interrupted=True)
            optimizer.step()
            loss_sum+=total_value;updates+=1;decisions_seen+=step_decisions
            if on_step:
                cursor=dict(epoch=epoch+1,step=0) if step+1==steps else dict(epoch=epoch,step=step+1)
                on_step(dict(cursor,loss_sum=loss_sum,updates=updates,decisions_seen=decisions_seen))
    return dict(updates=updates, loss=loss_sum/max(1,updates), interrupted=False,approx_kl=kl,kl_stopped=False,
        decisions_seen=decisions_seen,unique_families_seen=len({r['game_family'] for r in records}),
        effective_dataset_passes=decisions_seen/len(records),sequence_windows=len(windows),microbatch=micro)


def auxiliary_loss(logits,rows):
    """Marginal supervision of type, actor, and target/destination, with exact CE retained."""
    losses=[]
    def identity(candidate,key):
        if key=='kind': return candidate['kind']
        if key=='actor': return (candidate.get('actor') or {}).get('id')
        target=candidate.get('target')
        return target['id'] if target else (candidate.get('tx',candidate.get('x')),candidate.get('ty',candidate.get('y')))
    for i,r in enumerate(rows):
        row=logits[i,:len(r['candidates'])];normalizer=torch.logsumexp(row,0)
        chosen=r['candidates'][r['choice']]
        for key in ('kind','actor','destination'):
            indices=[j for j,c in enumerate(r['candidates']) if identity(c,key)==identity(chosen,key)]
            losses.append(normalizer-torch.logsumexp(row[indices],0))
    return torch.stack(losses).mean()


@torch.no_grad()
def imitation_quality(model, records, minimum=32, thresholds=None):
    import math
    device=next(model.parameters()).device
    thresholds=thresholds or dict(all=.4,recruit=.6,move=.35,attack=.35)
    model.eval();metrics={}
    for fmt in [model.format_name]:
        rows=[r for r in records if r['split']=='validation' and record_format(r)==fmt and len(r['candidates'])>1]
        loss=uniform=correct=chance=0.;kinds={k:dict(samples=0,correct=0) for k in ('recruit','move','attack')}
        for offset in range(0,len(rows),64):
            chunk=rows[offset:offset+64]
            logits,_=model(*batch(chunk,device))
            target=torch.tensor([r['choice'] for r in chunk],device=device)
            loss+=float(torch.nn.functional.cross_entropy(logits,target,reduction='sum'))
            correct+=float((logits.argmax(1)==target).sum())
            predicted=logits.argmax(1).tolist()
            for i,r in enumerate(chunk):
                kind=r.get('actual',r['candidates'][r['choice']]).get('kind')
                if kind=='move_attack':kind='attack'
                if kind in kinds:
                    kinds[kind]['samples']+=1;kinds[kind]['correct']+=int(predicted[i]==r['choice'])
            uniform+=sum(math.log(len(r['candidates'])) for r in chunk)
            chance+=sum(1/len(r['candidates']) for r in chunk)
        count=len(rows)
        for k,v in kinds.items():v['accuracy']=v['correct']/max(1,v['samples'])
        effective=count>=minimum and loss<.85*uniform and correct/max(1,count)>=thresholds['all']
        effective=effective and all(v['samples']>=minimum and v['accuracy']>=thresholds[k] for k,v in kinds.items())
        metrics[fmt]=dict(samples=count,cross_entropy=loss/max(1,count),uniform_entropy=uniform/max(1,count),kinds=kinds,
                          accuracy=correct/max(1,count),uniform_accuracy=chance/max(1,count),
                          effective=effective)
    return dict(effective=all(m['effective'] for m in metrics.values()),formats=metrics)
