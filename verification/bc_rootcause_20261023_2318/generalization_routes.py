"""Two evidence-directed routes: context regularization and lower-variance BC draws."""
import json,math,random,time
from concurrent.futures import ProcessPoolExecutor
import torch
from learning.common import ROOT,write_json
from learning.model import Policy,batch
from learning.data import make_bc_sampler
from learning.sequences import read_shards,training_windows
from learning.train import train,imitation_quality,auxiliary_loss

old=ROOT/'verification/bc_quality_ubuntu_20261023';out=ROOT/'verification/bc_rootcause_20261023_2318'

def run(arm):
 torch.set_num_threads(1)
 paths=sorted((old/'data/ffa4').glob('*.jsonl.gz'))
 training=read_shards(paths,partition='train',limit=2048,seed=71,format_name='ffa4')
 development=read_shards(paths,partition='validation',limit=1024,seed=71,format_name='ffa4')
 torch.manual_seed(99);random.seed(99);model=Policy('ffa4');optimizer=torch.optim.Adam(model.parameters(),lr=3e-4)
 start=time.monotonic()
 if arm=='context_dropout':
  def dropout(module,inputs):
   if not torch.is_grad_enabled():return inputs
   x=inputs[0];width=model.scene_width+192
   mask=torch.empty(x.shape[0],1,width,device=x.device).bernoulli_(.5)*2
   return (torch.cat([x[...,:width]*mask,x[...,width:]],-1),)
  hook=model.scorer.register_forward_pre_hook(dropout)
  steps=math.ceil(len(training_windows(training))/4)
  result=train(model,optimizer,training,'bc',epochs=120//steps,minibatch=256,deadline=time.time()+900)
  hook.remove()
 else:
  sampler=make_bc_sampler(training);seen=0
  for step in range(120):
   rows=sampler.sample(192);optimizer.zero_grad()
   for begin in range(0,len(rows),32):
    chunk=rows[begin:begin+32];scores,values=model(*batch(chunk));labels=torch.tensor([r['choice'] for r in chunk])
    loss=torch.nn.functional.cross_entropy(scores,labels)+.1*auxiliary_loss(scores,chunk)
    valid=torch.tensor([r.get('value_valid',True) for r in chunk],dtype=torch.bool)
    if valid.any():loss=loss+.5*(values[valid]-torch.tensor([r.get('reward',0) or 0 for r in chunk])[valid]).square().mean()
    (loss*len(chunk)/len(rows)).backward()
   torch.nn.utils.clip_grad_norm_(model.parameters(),.5);optimizer.step();seen+=len(rows)
   if (step+1)%40==0:print('DECISION_DRAWS',step+1,round(time.monotonic()-start,1),flush=True)
  result=dict(updates=120,decisions_seen=seen)
 quality=imitation_quality(model,development)
 fit=imitation_quality(model,[dict(r,split='validation') for r in training])
 write_json(out/(arm+'_generalization.json'),dict(training=result,development=quality,fit=fit,seconds=time.monotonic()-start))
 torch.save(dict(model=model.state_dict(),format='ffa4'),out/(arm+'.pt'))
 print('GENERALIZATION_DONE',arm,json.dumps(quality),flush=True)

if __name__=='__main__':
 with ProcessPoolExecutor(max_workers=2) as pool:list(pool.map(run,('context_dropout','decision_draws')))
