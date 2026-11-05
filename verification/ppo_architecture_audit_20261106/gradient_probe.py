"""Loss-gradient measurements on frozen data; no optimizer step or state save."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import random
import re
import statistics

import torch
from learning.data import advantages, make_bc_sampler, read_shards
from learning.export import load_model
from learning.model import batch


def flatten(model):
    return torch.cat([(p.grad if p.grad is not None else torch.zeros_like(p)).reshape(-1)
                      for p in model.parameters()])


def gradient(model, rows, kind, advantage=None, returns=None):
    model.zero_grad(set_to_none=True)
    logits, values=model(*batch(rows))
    chosen=torch.tensor([r['choice'] for r in rows])
    dist=torch.distributions.Categorical(logits=logits)
    if kind=='actor':
        old=torch.tensor([r['log_probability'] for r in rows])
        ratio=(dist.log_prob(chosen)-old).exp()
        loss=-torch.minimum(ratio*advantage,ratio.clamp(.8,1.2)*advantage).mean()
    elif kind=='value': loss=.5*(values-returns).square().mean()
    elif kind=='entropy': loss=-.01*dist.entropy().mean()
    else: loss=.1*torch.nn.functional.cross_entropy(logits,chosen)
    loss.backward()
    return float(loss.detach()),flatten(model).detach().clone()


def cosine(a,b):
    return float(torch.dot(a,b)/(a.norm()*b.norm()).clamp(min=1e-30))


def inspect(root,fmt):
    directory=root/fmt
    state=json.loads((directory/'state.json').read_text())
    history=[h for h in state['history'] if h['method']=='ppo']
    outputs=[]
    for h in (history[0],history[-1]):
        jobs=json.loads((directory/'schedules'/f"ppo-batch-{h['batch']:06}.json").read_text())
        rows=read_shards([j['shard'] for j in jobs],format_name=fmt)
        a,ret=advantages(rows)
        a=torch.tensor(a);a=(a-a.mean())/a.std(unbiased=False).clamp(min=1e-6)
        # Evenly spread across the whole batch; this is a diagnostic sample,
        # not the production window-equal optimizer objective.
        ids=torch.linspace(0,len(rows)-1,64).long().unique().tolist()
        chosen=[rows[i] for i in ids]
        paths=[]
        for path in state['teacher_shards']+state['dagger_shards']+state['policy_shards']:
            match=re.search(r'rollout-(\d+)-',Path(path).name)
            if not match or int(match.group(1))<=h['batch']: paths.append(path)
        version=int(jobs[0]['meta']['version'].removeprefix('v'))
        rehearsal=read_shards(paths,partition='train',limit=2048,seed=20261017+version,format_name=fmt)
        sampler=make_bc_sampler(rehearsal,allow_policy=True,exclude_teacher_impl='gpt6astra',
            exclude_teacher_sha=jobs[0]['meta']['teacher_source_sha256'])
        replay=sampler.sample(len(chosen),rng=random.Random(20261106))
        model_path=Path(jobs[0]['bots'][jobs[0]['meta']['seat']-1]).parent/'model.pt'
        model,_=load_model(model_path,fmt)
        losses={};grads={}
        for kind in ('actor','value','entropy','rehearsal'):
            losses[kind],grads[kind]=gradient(model,replay if kind=='rehearsal' else chosen,kind,
                                            a[ids],torch.tensor(ret)[ids])
        combined=sum(grads.values())
        outputs.append(dict(batch=h['batch'],rows=len(chosen),full_batch=len(rows),
            rehearsal_identities=sampler.source_identities,excluded_rehearsal=sampler.rows_excluded,
            scaled_loss=losses,scaled_gradient_norms={k:float(v.norm()) for k,v in grads.items()},
            cosine_with_actor={k:cosine(grads['actor'],v) for k,v in grads.items() if k!='actor'},
            combined_norm=float(combined.norm()),combined_actor_cosine=cosine(combined,grads['actor']),
            note='Uniform 64-row diagnostic, coefficients match production; no optimizer step.'))
    return outputs


def occupancy(root):
    events=[json.loads(line) for line in (root/'scheduler.jsonl').open()]
    starts={};durations=defaultdict(list)
    for row in events:
        key=(row['format'],row['id'])
        if row['event']=='start': starts[key]=row['time']
        elif key in starts:
            phase=row['id'].split('-')[0]
            durations[row['format']+'/'+phase].append(row['time']-starts.pop(key))
    return {key:dict(games=len(values),worker_wall_seconds=sum(values),mean_seconds=statistics.mean(values))
            for key,values in sorted(durations.items())}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run',type=Path);p.add_argument('output',type=Path)
    args=p.parse_args();torch.set_num_threads(1)
    result=dict(occupancy=occupancy(args.run),formats={})
    for fmt in ('duel','team2v2'):
        result['formats'][fmt]=inspect(args.run,fmt)
        args.output.write_text(json.dumps(result,indent=2)+'\n')
        print(fmt,'gradient probe complete',flush=True)
