"""One final fixed development trial, not independent acceptance evidence."""
import json,math,random,time
from unittest.mock import patch
import torch
from learning.common import ROOT,read_json,write_json
from learning.model import Policy
from learning.sequences import read_shards,training_windows
from learning.train import train,imitation_quality,auxiliary_loss

torch.set_num_threads(1)
old=ROOT/'verification/bc_quality_ubuntu_20261023'
out=ROOT/'verification/bc_quality_fix_20261023'
assert (out/'holdout_plan.json').exists()
paths=sorted((old/'data/ffa4').glob('*.jsonl.gz'))
training=read_shards(paths,partition='train',limit=2048,seed=71,format_name='ffa4')
development=read_shards(paths,partition='validation',limit=1024,seed=71,format_name='ffa4')
steps=math.ceil(len(training_windows(training))/4);assert 120%steps==0
torch.manual_seed(99);random.seed(99);model=Policy('ffa4')
optimizer=torch.optim.Adam(model.parameters(),lr=3e-4)

def objective(logits,rows):
 losses=[]
 for i,row in enumerate(rows):
  n=len(row['candidates']);chosen=row['choice']
  if n<=1:continue
  scores=logits[i,:n];wrong=torch.cat([scores[:chosen],scores[chosen+1:]])
  losses.append(torch.relu(1+wrong.max()-scores[chosen]))
 ranking=torch.stack(losses).mean() if losses else logits.sum()*0
 # The train loop multiplies auxiliary_loss by .1.
 return auxiliary_loss(logits,rows)+10*ranking

start=time.monotonic()
def progress(cursor):
 if cursor['updates']%20==0:print('RANK_TRIAL',cursor['updates'],round(time.monotonic()-start,1),flush=True)
with patch('learning.train.auxiliary_loss',objective):
 result=train(model,optimizer,training,'bc',epochs=120//steps,minibatch=256,deadline=time.time()+1800,on_step=progress)
assert result['updates']==120 and not result['interrupted']
quality=imitation_quality(model,development)
torch.save(dict(model=model.state_dict(),format='ffa4'),out/'ffa4_rank_trial.pt')
write_json(out/'rank_development_result.json',dict(training=result,development_quality=quality,
 objective='exact CE + original auxiliary/10 + hinge(1 + max wrong logit - teacher logit)',seconds=time.monotonic()-start))
print('RANK_TRIAL_RESULT',json.dumps(quality),flush=True)
