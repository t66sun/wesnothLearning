"""Read-only rank and public combat-economics diagnostics; not acceptance."""
import collections,json,math
import numpy as np
import torch
from learning.common import ROOT,write_json
from learning.features import ACTION,ENTITY,UNIT_TYPES
from learning.model import Policy,batch
from learning.sequences import read_shards
from learning.rules_catalog import resolve_dir

torch.set_num_threads(1)
old=ROOT/'verification/bc_quality_ubuntu_20261023';out=ROOT/'verification/bc_rootcause_20261023_2318'
ix={n:i for i,(n,s) in enumerate(ACTION)};ex={n:i for i,(n,s) in enumerate(ENTITY)}
catalog=json.loads((resolve_dir()/'rules.json').read_text())['units']

def trade(c):
 f=c['features']
 if c['kind'] not in ('attack','move_attack') or not f[ix['combat_predicted']]:return None
 u=c['actor'];e=c['target'];uf=u['features'];ef=e['features']
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
 return score

report={}
m=Policy('ffa4');m.load_state_dict(torch.load(old/'ffa4_tactical_inputs.pt',weights_only=False)['model']);m.eval()
for part in ('train','validation'):
 rows=read_shards(sorted((old/'data/ffa4').glob('*.jsonl.gz')),partition=part,limit=2048,seed=71,format_name='ffa4')
 c=collections.Counter();groups=collections.defaultdict(list)
 with torch.no_grad():
  for start in range(0,len(rows),64):
   chunk=rows[start:start+64];scores,_=m(*batch(chunk))
   for r,s in zip(chunk,scores):
    n=len(r['candidates']);target=r['choice'];truth=r['candidates'][target];p=int(s[:n].argmax());chosen=r['candidates'][p]
    k='attack' if truth['kind']=='move_attack' else truth['kind'];rank=int((s[:n]>s[target]).sum())+1
    c[k+':samples']+=1;c[k+':top1']+=rank<=1;c[k+':top3']+=rank<=3;c[k+':top5']+=rank<=5
    c[k+':random1_sum']+=1/n
    v=trade(truth)
    if v is not None:groups['teacher_attack_trade'].append(v)
    if truth['kind']=='move' and chosen['kind'] in ('attack','move_attack'):
     c['wrong_attack_own_leader']+=bool(chosen['features'][ix['own_leader']])
     v=trade(chosen)
     if v is not None:groups['wrong_attack_trade'].append(v)
 report[part]=dict(counts=dict(c),trade={name:dict(samples=len(v),positive=sum(x>.5 for x in v),
  negative=sum(x<=.5 for x in v),quantiles=np.quantile(v,[0,.25,.5,.75,1]).tolist()) for name,v in groups.items()})
write_json(out/'trade_diagnostic.json',report);print(json.dumps(report),flush=True)
