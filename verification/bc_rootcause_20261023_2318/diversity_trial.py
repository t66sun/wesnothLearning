"""Predeclared two-family diversity increment, unchanged 120-update budget."""
import copy,hashlib,json,math,random,time
from concurrent.futures import ProcessPoolExecutor
import torch
from learning.common import ROOT,read_json,write_json
from learning.data import split
from learning.features import ACTION,ENTITY,MOVE_FEATURES,schema
from learning.maps import frozen_map
from learning.model import Policy
from learning.sequences import read_shards,training_windows
from learning.train import train,imitation_quality,checkpoint
from verification.bc_quality_ubuntu_20261023 import quality_t5 as collection
import params

out=ROOT/'verification/bc_rootcause_20261023_2318';old=ROOT/'verification/bc_quality_ubuntu_20261023'
collection.OUT=out

def plan():
 result=[]
 for i,name in enumerate(('clash','isars_cross')):
  _,digest=frozen_map(name);rotation=(2,0)[i];factions=[params.FACTIONS[(rotation+j)%6] for j in range(4)]
  for seed in range(202810230,202811230):
   physical=dict(format='ffa4',map=digest,seed=seed,factions=factions,teams=[1,2,3,4])
   family=hashlib.sha256(json.dumps(physical,sort_keys=True,separators=(',',':')).encode()).hexdigest()
   if split(family)=='train':break
  result.append(dict(id=f'extra-ffa4-train-{i}',format='ffa4',game_family=family,split='train',seed=seed,
   factions=factions,teams=[1,2,3,4],map=name,map_sha256=digest,max_turns=12))
 return result

def compare(arm):
 torch.set_num_threads(1)
 paths=sorted((old/'data/ffa4').glob('*.jsonl.gz'))+sorted((out/'data/ffa4').glob('extra*.jsonl.gz'))
 training=read_shards(paths,partition='train',limit=2048,seed=71,format_name='ffa4')
 development=read_shards(paths,partition='validation',limit=1024,seed=71,format_name='ffa4')
 assert len({r['game_family'] for r in training})==4
 masks=[i for i,(n,s) in enumerate(ACTION) if n in {n for n,s in MOVE_FEATURES}]
 phase=next(i for i,(n,s) in enumerate(ENTITY) if n=='next_round')
 class Zeroed(Policy):
  def encode_scene(self,g,o,om,p):
   p=dict(p);p['entities']=p['entities'].clone();p['entities'][...,phase]=0
   return super().encode_scene(g,o,om,p)
  def forward(self,g,o,a,om,am,p):
   a=a.clone();a[...,masks]=0;p=dict(p)
   for key in ('actors','targets'):p[key]=p[key].clone();p[key][...,phase]=0
   return super().forward(g,o,a,om,am,p)
 torch.manual_seed(99);random.seed(99);model=(Zeroed if arm=='zeroed' else Policy)('ffa4')
 optimizer=torch.optim.Adam(model.parameters(),lr=3e-4);steps=math.ceil(len(training_windows(training))/4)
 cursor={};start=time.monotonic()
 class BudgetReached(Exception):pass
 def progress(c):
  cursor.update(c)
  if c['updates']%40==0:print('DIVERSITY',arm,c['updates'],round(time.monotonic()-start,1),flush=True)
  if c['updates']==120:raise BudgetReached
 try:result=train(model,optimizer,training,'bc',epochs=math.ceil(120/steps),minibatch=256,deadline=time.time()+750,on_step=progress)
 except BudgetReached:result=dict(updates=cursor['updates'],decisions_seen=cursor['decisions_seen'],interrupted=False,stop='frozen optimizer cap')
 assert result['updates']==120
 quality=imitation_quality(model,development)
 checkpoint(out/('diversity_'+arm+'.pt'),model,optimizer,diagnostic=True)
 report=dict(arm=arm,training=result,development=quality,families=sorted({r['game_family'] for r in training}),
  training_rows=len(training),factions=sorted({r['faction'] for r in training}),seconds=time.monotonic()-start)
 write_json(out/('diversity_'+arm+'.json'),report)
 print('DIVERSITY_DONE',arm,json.dumps(report),flush=True)

if __name__=='__main__':
 frozen=plan();write_json(out/'diversity_plan.json',dict(additional_train=frozen,updates_per_arm=120,
  lr=3e-4,seed=99,arms=['normal','zeroed'],selection='fixed final update only',fresh_holdout='original predeclared plan, unused unless normal development movement >=35%'))
 print('DIVERSITY_PLAN_FROZEN',json.dumps(frozen),flush=True)
 with ProcessPoolExecutor(max_workers=2) as pool:list(pool.map(collection.play,frozen))
 with ProcessPoolExecutor(max_workers=2) as pool:list(pool.map(compare,('normal','zeroed')))
