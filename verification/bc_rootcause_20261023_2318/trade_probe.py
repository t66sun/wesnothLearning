"""Experimental input substitution: no production schema or data is rewritten."""
import collections,json,math,random,time
from unittest.mock import patch
import torch
from learning.common import ROOT,write_json
from learning.features import ACTION,ENTITY,UNIT_TYPES
from learning.model import Policy,batch
from learning.sequences import read_shards,training_windows
from learning.train import train,imitation_quality
from learning.rules_catalog import resolve_dir

torch.set_num_threads(1)
old=ROOT/'verification/bc_quality_ubuntu_20261023';out=ROOT/'verification/bc_rootcause_20261023_2318'
ix={n:i for i,(n,s) in enumerate(ACTION)};ex={n:i for i,(n,s) in enumerate(ENTITY)}
catalog=json.loads((resolve_dir()/'rules.json').read_text())['units']
cache={}
def encode(rows,*args,**kwargs):
 tensors=batch(rows,*args,**kwargs);actions=tensors[2]
 for i,r in enumerate(rows):
  if id(r) not in cache:
   values=[]
   for c in r['candidates']:
    f=c['features'];v=float(f[ix['gold_cost']])
    if c['kind'] in ('attack','move_attack') and f[ix['combat_predicted']]:
     uf=c['actor']['features'];e=c['target'];ef=e['features']
     uv=float(f[ix['unit_cost']])*50*(1+.35*float(uf[ex['experience']])/max(.01,float(uf[ex['max_experience']])))
     ev=catalog[UNIT_TYPES[e['type_index']]]['cost']*(1+.35*float(ef[ex['experience']])/max(.01,float(ef[ex['max_experience']])))
     dealt=float(f[ix['expected_enemy_damage']])*50;taken=float(f[ix['expected_self_damage']])*50
     kill=float(f[ix['kill_probability']]);death=float(f[ix['death_probability']])
     mhp=float(uf[ex['max_hp']])*100;ehp=float(ef[ex['max_hp']])*100;hp=float(uf[ex['hp']])*100
     risk=float(f[ix['move_risk']])*50
     score=dealt*ev/ehp+kill*ev*.8-taken*uv/mhp-death*uv*1.1
     score-=max(0,risk*.65-(hp-taken)+6)*uv/mhp*1.3
     if f[ix['own_leader']]:score-=death*500+max(0,risk-(hp-taken)+18)*5
     score-=max(0,float(f[ix['move_home_distance']])*50-6)*1.2
     v=max(-4,min(4,score/25))
    values.append(v)
   cache[id(r)]=torch.tensor(values)
  actions[i,:len(r['candidates']),ix['gold_cost']]=cache[id(r)]
 return tensors

paths=sorted((old/'data/ffa4').glob('*.jsonl.gz'))
training=read_shards(paths,partition='train',limit=2048,seed=71,format_name='ffa4')
development=read_shards(paths,partition='validation',limit=1024,seed=71,format_name='ffa4')
torch.manual_seed(99);random.seed(99);model=Policy('ffa4');optimizer=torch.optim.Adam(model.parameters(),lr=3e-4)
start=time.monotonic()
def progress(c):
 if c['updates']%40==0:print('TRADE_PROBE',c['updates'],round(time.monotonic()-start,1),flush=True)
steps=math.ceil(len(training_windows(training))/4)
with patch('learning.train.batch',encode):
 result=train(model,optimizer,training,'bc',epochs=120//steps,minibatch=256,deadline=time.time()+600,on_step=progress)
 quality=imitation_quality(model,development)
 fit=imitation_quality(model,[dict(r,split='validation') for r in training])
write_json(out/'trade_probe.json',dict(training=result,development=quality,fit=fit,seconds=time.monotonic()-start,
 experimental=True,substitution='combat-only unused gold_cost slot; no data/schema claim, no deployment'))
print('TRADE_PROBE_DONE',json.dumps(quality),flush=True)
