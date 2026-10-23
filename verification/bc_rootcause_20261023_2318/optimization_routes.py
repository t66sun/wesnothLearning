"""Fixed, one-variable diagnostics for BC history/value/window interference."""
import collections,json,math,random,time
from concurrent.futures import ProcessPoolExecutor
from unittest.mock import patch
import torch
from learning.common import ROOT,write_json
from learning.model import Policy,batch
from learning.sequences import read_shards,training_windows
from learning.train import train,imitation_quality

old=ROOT/'verification/bc_quality_ubuntu_20261023'
out=ROOT/'verification/bc_rootcause_20261023_2318'

def run(arm):
 torch.set_num_threads(1)
 paths=sorted((old/'data/ffa4').glob('*.jsonl.gz'))
 training=read_shards(paths,partition='train',limit=2048,seed=71,format_name='ffa4')
 development=read_shards(paths,partition='validation',limit=1024,seed=71,format_name='ffa4')
 if arm=='empty_history':training=[dict(r,_history=[]) for r in training];development=[dict(r,_history=[]) for r in development]
 if arm=='no_value':training=[dict(r,value_valid=False) for r in training]
 torch.manual_seed(99);random.seed(99);model=Policy('ffa4');optimizer=torch.optim.Adam(model.parameters(),lr=3e-4)
 hook=model.value.register_forward_pre_hook(lambda module,inputs:(inputs[0].detach(),)) if arm=='value_detached' else None
 trace=[];step_rows=[];norms=[];original_batch=batch;original_clip=torch.nn.utils.clip_grad_norm_
 def capture_batch(rows,*args,**kwargs):
  step_rows.extend(rows);return original_batch(rows,*args,**kwargs)
 def clip(parameters,*args,**kwargs):
  groups=collections.defaultdict(float)
  for name,p in model.named_parameters():
   if p.grad is not None:groups[name.split('.')[0]]+=float(p.grad.square().sum())
  result=original_clip(parameters,*args,**kwargs);norms.append(dict(norm=float(result),groups={k:math.sqrt(v) for k,v in groups.items()}));return result
 start=time.monotonic()
 def progress(cursor):
  update=cursor['updates'];c=collections.Counter(('valid:' if r.get('value_valid',True) else '')+r['candidates'][r['choice']]['kind'] for r in step_rows)
  record=dict(update=update,loss=cursor['loss_sum']/update,classes=dict(c),unique_rows=len({id(r) for r in step_rows}),decisions=len(step_rows),gradient=norms[-1])
  step_rows.clear()
  if update%20==0:
   q=imitation_quality(model,development);record['development']=q
   print('ROUTE',arm,update,json.dumps(q),flush=True)
  trace.append(record)
 steps=math.ceil(len(training_windows(training))/4)
 with patch('learning.train.batch',capture_batch),patch('torch.nn.utils.clip_grad_norm_',clip):
  result=train(model,optimizer,training,'bc',epochs=120//steps,minibatch=256,deadline=time.time()+900,on_step=progress)
 if hook:hook.remove()
 quality=imitation_quality(model,development)
 train_as_validation=[dict(r,split='validation') for r in training]
 fit=imitation_quality(model,train_as_validation)
 torch.save(dict(model=model.state_dict(),format='ffa4'),out/(arm+'.pt'))
 report=dict(arm=arm,training=result,development=quality,training_quality=fit,trace=trace,seconds=time.monotonic()-start,
  valid_targets=dict(collections.Counter(str(r['reward'])+':'+r['faction'] for r in training if r.get('value_valid',True))))
 write_json(out/(arm+'_route.json'),report)
 print('ROUTE_DONE',arm,json.dumps({k:v for k,v in report.items() if k!='trace'}),flush=True)
 return arm

if __name__=='__main__':
 with ProcessPoolExecutor(max_workers=2) as pool:list(pool.map(run,('baseline','no_value','value_detached','empty_history')))
 print('ROUTES_COMPLETE',flush=True)
