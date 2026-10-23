"""Second and structurally different development hypothesis: cheap kind pooling."""
import json,math,random,time
import torch
from torch import nn
from learning.common import ROOT,write_json
from learning.features import ACTION
from learning.model import Policy
from learning.sequences import read_shards,training_windows
from learning.train import train,imitation_quality

torch.set_num_threads(1)
old=ROOT/'verification/bc_quality_ubuntu_20261023'
out=ROOT/'verification/bc_quality_fix_20261023';out.mkdir(exist_ok=True)
kinds=('end_turn','recruit','move','attack','move_attack')
indices=[next(i for i,(name,_) in enumerate(ACTION) if name==kind) for kind in kinds]
class PooledScorer(nn.Module):
 def __init__(self,base,context):
  super().__init__();self.base=base;self.context=context
  self.kind=nn.Sequential(nn.Linear(context+5*128,32),nn.ReLU(),nn.Linear(32,5))
  nn.init.zeros_(self.kind[-1].weight);nn.init.zeros_(self.kind[-1].bias)
 def forward(self,inputs):
  hidden=self.base[:-1](inputs);logits=self.base[-1](hidden)
  types=inputs[...,self.context:][...,indices]
  pools=[]
  for kind in range(5):
   mask=types[...,kind]>0
   pool=hidden.masked_fill(~mask[...,None],-torch.inf).amax(1)
   pools.append(torch.where(mask.any(1,keepdim=True),pool,torch.zeros_like(pool)))
  bias=self.kind(torch.cat([inputs[:,0,:self.context],*pools],-1))
  return logits+(types*bias[:,None]).sum(-1,keepdim=True)
paths=sorted((old/'data/ffa4').glob('*.jsonl.gz'))
training=read_shards(paths,partition='train',limit=2048,seed=71,format_name='ffa4')
development=read_shards(paths,partition='validation',limit=1024,seed=71,format_name='ffa4')
torch.manual_seed(99);random.seed(99);model=Policy('ffa4')
model.scorer=PooledScorer(model.scorer,model.scene_width+128+64)
optimizer=torch.optim.Adam(model.parameters(),lr=3e-4)
steps=math.ceil(len(training_windows(training))/4);assert 120%steps==0
start=time.monotonic()
def progress(cursor):
 if cursor['updates']%20==0:print('POOL_TRIAL',cursor['updates'],round(time.monotonic()-start,1),flush=True)
result=train(model,optimizer,training,'bc',epochs=120//steps,minibatch=256,deadline=time.time()+1800,on_step=progress)
assert result['updates']==120 and not result['interrupted']
quality=imitation_quality(model,development)
torch.save(dict(model=model.state_dict(),format='ffa4'),out/'ffa4_pool_trial.pt')
write_json(out/'pool_development_result.json',dict(training=result,development_quality=quality,
 parameters=sum(p.numel() for p in model.parameters()),seconds=time.monotonic()-start))
print('POOL_TRIAL_RESULT',json.dumps(quality),flush=True)
