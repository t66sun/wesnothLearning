"""One fixed FF4 development trial; original T5 holdout is now development only."""
import collections,copy,hashlib,json,math,random,time
from unittest.mock import patch
import torch
from learning.common import ROOT,read_json,write_json
from learning.model import Policy
from learning.sequences import read_shards,training_windows
from learning.train import train,imitation_quality,auxiliary_loss
from learning.data import split
from learning.maps import frozen_map
from learning.formats import TEAM2V2
import params

torch.set_num_threads(1)
old=ROOT/'verification/bc_quality_ubuntu_20261023'
out=ROOT/'verification/bc_quality_fix_20261023';out.mkdir(parents=True,exist_ok=True)
# Freeze independent future holdout families before any new optimizer step.
plan=[]
for fmt in ('ffa4','team2v2'):
 for index,name in enumerate(('clash','isars_cross')):
  _,digest=frozen_map(name);rotation=(4,2)[index]
  factions=[params.FACTIONS[(rotation+i)%6] for i in range(4)]
  teams=list(TEAM2V2) if fmt=='team2v2' else [1,2,3,4]
  for seed in range(202710230,202711230):
   physical=dict(format=fmt,map=digest,seed=seed,factions=factions,teams=teams)
   family=hashlib.sha256(json.dumps(physical,sort_keys=True,separators=(',',':')).encode()).hexdigest()
   if split(family)=='validation':break
  plan.append(dict(id=f'fix-{fmt}-validation-{index}',format=fmt,split='validation',map=name,map_sha256=digest,
    factions=factions,teams=teams,seed=seed,game_family=family,max_turns=12))
path=out/'holdout_plan.json'
if path.exists():assert read_json(path)==plan
else:write_json(path,plan)
print('FROZEN_NEW_HOLDOUT',json.dumps(plan),flush=True)

paths=sorted((old/'data/ffa4').glob('*.jsonl.gz'))
training=read_shards(paths,partition='train',limit=2048,seed=71,format_name='ffa4')
development=read_shards(paths,partition='validation',limit=1024,seed=71,format_name='ffa4')
steps=math.ceil(len(training_windows(training))/4);assert 120%steps==0
torch.manual_seed(99);random.seed(99);model=Policy('ffa4');optimizer=torch.optim.Adam(model.parameters(),lr=3e-4)
def objective(logits,rows):
 losses=[]
 for i,row in enumerate(rows):
  chosen=row['candidates'][row['choice']]['kind']
  indices=[j for j,c in enumerate(row['candidates']) if c['kind']==chosen]
  losses.append(torch.logsumexp(logits[i,:len(row['candidates'])],0)-torch.logsumexp(logits[i,indices],0))
 # The unchanged train loop scales auxiliary_loss by .1. Retain actor and
 # destination weights and lift just the kind term from 1/30 to 1.
 return auxiliary_loss(logits,rows)+(10-1/3)*torch.stack(losses).mean()
start=time.monotonic()
def progress(cursor):
 if cursor['updates']%20==0:print('KIND_TRIAL',cursor['updates'],round(time.monotonic()-start,1),flush=True)
with patch('learning.train.auxiliary_loss',objective):
 result=train(model,optimizer,training,'bc',epochs=120//steps,minibatch=256,deadline=time.time()+1800,on_step=progress)
assert result['updates']==120 and not result['interrupted']
quality=imitation_quality(model,development)
torch.save(dict(model=model.state_dict(),format='ffa4'),out/'ffa4_trial.pt')
write_json(out/'development_result.json',dict(training=result,development_quality=quality,
 objective='exact CE + kind CE + (actor CE + destination CE)/30',seconds=time.monotonic()-start))
print('KIND_TRIAL_RESULT',json.dumps(quality),flush=True)
