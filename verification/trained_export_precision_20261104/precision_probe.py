from collections import Counter
import copy, inspect, json, sys, time
from pathlib import Path
import torch
from learning import model as net
from learning.export import load_model, verify_numerics
from learning.sequences import read_raw_shards
from unittest.mock import patch

root=Path('/home/tongshu/acceptance/bc_v6_readiness_20261103/runs/bc_readiness/duel')
rows=read_raw_shards([root/'data/rollout-00036-duel-g0.jsonl.gz'],format_name='duel')
model,_=load_model(root/'latest.pt','duel'); precise=copy.deepcopy(model).double().eval(); model.eval()
original=net.batch

def floating64(x):
    if isinstance(x,torch.Tensor): return x.double() if x.is_floating_point() else x
    if isinstance(x,dict): return {k:floating64(v) for k,v in x.items()}
    return x

def batch64(*args,**kwargs): return tuple(floating64(v) for v in original(*args,**kwargs))

# Use the original verification loop, adding only a diagnostic after both runtimes have returned.
from learning import export
source=inspect.getsource(verify_numerics).replace('error=max(error,abs(value.item()-v),candidate_error)', 'record(model,row,logits,value,scores,v); error=max(error,abs(value.item()-v),candidate_error)').replace("if not math.isfinite(error) or error>1e-5:", "if not math.isfinite(error):")
maxima={}; counts=Counter(); first=[]; sep=[]
def record(model,row,logits,value,scores,v):
    with patch.object(net,'batch',batch64): out,val=precise(*batch64([row],'cpu'))
    for i in range(len(row['candidates'])):
        a=logits[0,i].item(); b=out[0,i].item(); c=scores[i+1]; diffs={'float32_lua':abs(a-c),'float64_lua':abs(b-c),'float32_float64':abs(a-b)}
        for k,d in diffs.items():
            counts[k]+=int(d>1e-5)
            if d>maxima.get(k,{}).get('error',0): maxima[k]=dict(error=d,turn=row['turn'],decision=row['decision'],action=i,torch32=a,torch64=b,lua=c)
        if diffs['float32_lua']>1e-5 and len(first)<2: first.append((row['turn'],row['decision'],i,a,b,c))
    sep.append((abs(value.item()-v),abs(val.item()-v)))
ns=dict(vars(export),record=record);exec(source,ns)
start=time.monotonic();result=ns['verify_numerics'](model,rows)
print(json.dumps(dict(rows=len(rows),logits=sum(len(r['candidates']) for r in rows),first=first,maxima=maxima,counts=counts,value_maxima=[max(p[i] for p in sep) for i in range(2)],seconds=time.monotonic()-start),indent=2))
