"""Forward-only checks against recorded actions and unchanged behavior weights."""
import json
from pathlib import Path
import torch
from learning.export import load_model
from learning.data import read_shards
from learning.model import batch

torch.set_num_threads(1)
root=Path(__file__).resolve().parent
results={}
for fmt in ('duel','ffa4','team2v2'):
    model,_=load_model(root/(fmt+'_behavior.pt'),fmt);model.eval()
    rows=read_shards([root/(fmt+'_ppo.jsonl.gz')],format_name=fmt)
    # Evenly cover the real full trajectory, keeping each raw memory prefix.
    chosen=sorted({round(i*(len(rows)-1)/47) for i in range(min(48,len(rows)))})
    sampled=[rows[i] for i in chosen]
    differences=[];kls=[]
    with torch.no_grad():
        for start in range(0,len(sampled),16):
            chunk=sampled[start:start+16];logits,_=model(*batch(chunk))
            new=torch.distributions.Categorical(logits=logits).log_prob(torch.tensor([r['choice'] for r in chunk]))
            old=torch.tensor([r['log_probability'] for r in chunk]);delta=new-old
            differences.extend(delta.abs().tolist());kls.append(float((delta.exp()-1-delta).mean()))
    result=dict(trajectory_rows=len(rows),checked=len(sampled),turns=sorted({r['turn'] for r in sampled}),max_logp_difference=max(differences),max_chunk_kl=max(kls),matches=max(differences)<1e-4)
    results[fmt]=result
    print(fmt,json.dumps(result),flush=True)
(root/'replay-probe.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
assert all(x['matches'] for x in results.values()), 'unchanged behavior policy differs from recorded log probability'
