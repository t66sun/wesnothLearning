"""Separate insufficient optimization from representation failure; dev only."""
import json,math,random,time
from concurrent.futures import ProcessPoolExecutor
import torch
from learning.common import ROOT,write_json
from learning.model import Policy
from learning.sequences import read_shards,training_windows
from learning.train import train,imitation_quality

old=ROOT/'verification/bc_quality_ubuntu_20261023'
out=ROOT/'verification/bc_rootcause_20261023_2318'

def run(arm):
 torch.set_num_threads(1)
 paths=sorted((old/'data/ffa4').glob('*.jsonl.gz'))
 training=read_shards(paths,partition='train',limit=2048,seed=71,format_name='ffa4')
 development=read_shards(paths,partition='validation',limit=1024,seed=71,format_name='ffa4')
 torch.manual_seed(99);random.seed(99);model=Policy('ffa4')
 updates=480 if arm=='extended_480' else 120
 lr=3e-4 if arm=='extended_480' else 1e-3
 optimizer=torch.optim.Adam(model.parameters(),lr=lr);trace=[];start=time.monotonic()
 def progress(cursor):
  if cursor['updates']%40:return
  q=imitation_quality(model,development)
  fit=imitation_quality(model,[dict(r,split='validation') for r in training])
  p=dict(update=cursor['updates'],development=q,training=fit,seconds=time.monotonic()-start);trace.append(p)
  print('REGIME',arm,json.dumps(p),flush=True)
 steps=math.ceil(len(training_windows(training))/4)
 result=train(model,optimizer,training,'bc',epochs=updates//steps,minibatch=256,deadline=time.time()+1500,on_step=progress)
 assert result['updates']==updates and not result['interrupted']
 report=dict(arm=arm,learning_rate=lr,training=result,trace=trace,seconds=time.monotonic()-start,
  acceptance=False,reason='development-only optimization diagnostic; extended arm exceeds original T5 cap')
 write_json(out/(arm+'.json'),report)
 torch.save(dict(model=model.state_dict(),optimizer=optimizer.state_dict(),format='ffa4'),out/(arm+'.pt'))
 print('REGIME_DONE',arm,flush=True)

if __name__=='__main__':
 with ProcessPoolExecutor(max_workers=2) as pool:list(pool.map(run,('extended_480','faster_lr_120')))
