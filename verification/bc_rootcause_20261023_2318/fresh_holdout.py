"""Evaluate frozen diversity checkpoints once on the predeclared fresh families."""
import collections,json
from concurrent.futures import ProcessPoolExecutor
import torch
from learning.common import ROOT,read_json,write_json
from learning.features import ACTION,ENTITY,MOVE_FEATURES
from learning.model import Policy
from learning.sequences import read_shards
from learning.train import imitation_quality
from verification.bc_quality_ubuntu_20261023 import quality_t5 as collection

out=ROOT/'verification/bc_rootcause_20261023_2318'
normal=read_json(out/'diversity_normal.json');zero=read_json(out/'diversity_zeroed.json')
assert normal['training']['updates']==zero['training']['updates']==120
assert normal['training']['decisions_seen']==zero['training']['decisions_seen']
if normal['development']['formats']['ffa4']['kinds']['move']['accuracy']<.35:
 print('FRESH_HOLDOUT_NOT_USED: fixed development candidate failed',flush=True)
 raise SystemExit(0)
plan=[p for p in read_json(ROOT/'verification/bc_quality_fix_20261023/holdout_plan.json') if p['format']=='ffa4']
assert len(plan)==2 and not set(p['game_family'] for p in plan)&set(normal['families'])
collection.OUT=out
if __name__=='__main__':
 with ProcessPoolExecutor(max_workers=2) as pool:list(pool.map(collection.play,plan))
 torch.set_num_threads(1)
 paths=[out/'data/ffa4'/(p['id']+'.jsonl.gz') for p in plan]
 rows=read_shards(paths,partition='validation',limit=2048,seed=71,format_name='ffa4')
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
 report=dict(families=[p['game_family'] for p in plan],factions=sorted({r['faction'] for r in rows}),arms={})
 for arm,cls in (('normal',Policy),('zeroed',Zeroed)):
  model=cls('ffa4');model.load_state_dict(torch.load(out/('diversity_'+arm+'.pt'),weights_only=False)['model'])
  report['arms'][arm]=imitation_quality(model,rows)
 totals=collections.Counter();matched=collections.Counter()
 for p in plan:
  cov=read_json(out/'data/ffa4'/(p['id']+'.result.json'))['coverage']
  totals['all']+=cov['total'];matched['all']+=cov['matched']
  for k in ('move','recruit','attack'):totals[k]+=cov['kinds'][k]['total'];matched[k]+=cov['kinds'][k]['matched']
 report['coverage']={k:dict(total=totals[k],matched=matched[k],ratio=matched[k]/totals[k]) for k in totals}
 n=report['arms']['normal']['formats']['ffa4'];z=report['arms']['zeroed']['formats']['ffa4']
 report['checks']=dict(move_samples=n['kinds']['move']['samples']>=32,
  movement=n['kinds']['move']['accuracy']>=.35,gain=n['kinds']['move']['accuracy']>z['kinds']['move']['accuracy'],
  movement_coverage=report['coverage']['move']['ratio']>=.8,overall_coverage=report['coverage']['all']['ratio']>=.9,
  training_six_factions=len(normal['factions'])==6,two_holdout_families=len(plan)==2)
 report['passed']=all(report['checks'].values())
 write_json(out/'fresh_holdout.json',report)
 print('FRESH_HOLDOUT',json.dumps(report),flush=True)
