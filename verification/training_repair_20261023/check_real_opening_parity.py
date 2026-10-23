"""Reuse real current-schema trajectories/weights; six bounded Astra openings."""
import json, pathlib, time, collections, hashlib
import torch
from learning.common import ROOT, read_json, write_json, sha256
from learning.experiment import FormatExperiment, opening_gate
from learning.export import load_model, verify_numerics
from learning.schedule import teacher_jobs
from learning.sample import play_job, opening_map
from learning.sequences import read_raw_shards, sequence_key
from learning.features import schema

torch.set_num_threads(1)
out=ROOT/'verification/training_repair_20261023'
base=out/'stage_outputs_v2'
summary={}
for fmt in ('duel','ffa4','team2v2'):
 saved=out/'opening'/f'{fmt}.json'
 if saved.exists():
  summary[fmt]=read_json(saved)['evidence'];print('REUSE_PASSED_OPENING_PARITY',fmt,flush=True);continue
 root=base/fmt; directory=root/fmt
 model,state=load_model(directory/'selected.pt',fmt)
 paths=sorted((directory/'data').glob('teacher-*.jsonl.gz'))
 rows=read_raw_shards(paths[:1],fmt)
 key=sequence_key(rows[0]); sequence=[r for r in rows if sequence_key(r)==key]
 selected=[]; turns=set()
 for row in sequence:
  selected.append(row);turns.add(row['turn'])
  if len(turns)>=2 and any(len(r['candidates'])==128 for r in selected): break
 error=verify_numerics(model,selected)
 print('REAL_PARITY',fmt,'rows',len(selected),'turns',sorted(turns),'max_error',error,flush=True)
 manifest=read_json(root/'manifest.json');clock=read_json(root/'clock.json')
 runner=FormatExperiment(directory,fmt,manifest,clock,lambda jobs,log:[],resume=True)
 jobs=teacher_jobs(out/'opening'/fmt,runner.teachers,runner.fixed,runner.support,0,
       202610230,time.time()+600,runner.exe,formats=[fmt],count=2)
 results=[]
 for job in jobs:
  focal=job['meta']['seat']
  job['bots']=[runner.teachers[0] if bot=='baseline' else bot for bot in job['bots']]
  if fmt=='team2v2': job['meta']['context']='astra_partner'
  # Exercise the old guarding-leader false negative with Northerners in duel.
  if fmt=='duel': job['factions'][focal-1]='Northerners'
  job.update(engine='lite',rules_dir=runner.config['rules_dir'],allow_approximate=True,max_turns=5,
       map_override=opening_map(len(job['bots'])))
  map_hash=hashlib.sha256(json.dumps(job['map_override'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
  job['meta'].update(map='opening_probe',map_sha256=map_hash)
  family=dict(format=fmt,map=map_hash,seed=job['seed'],factions=job['factions'],teams=job.get('teams'))
  job['game_family']=hashlib.sha256(json.dumps(family,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  result=play_job(job)
  assert result['status']=='complete',result
  results.append(result)
 gate=opening_gate(results)
 ends=[d for r in results for d in r['behavior'] if d.get('side')==r['meta']['seat'] and d.get('end_turn')]
 evidence=dict(parity_error=error,parity_rows=len(selected),parity_turns=sorted(turns),
    checkpoint_sha256=sha256(directory/'selected.pt'),shards=[str(p) for p in paths[:1]],
    opening_gate=gate,learner_end_turns=ends)
 summary[fmt]=evidence
 write_json(out/'opening'/f'{fmt}.json',dict(jobs=jobs,results=results,evidence=evidence))
 print('REAL_OPENING',fmt,json.dumps(dict(gate=gate,end_turns=ends)),flush=True)
 assert gate['passed'],(fmt,gate)
write_json(out/'real_opening_parity.json',dict(features=schema(),formats=summary))
print('REAL_OPENING_PARITY_PASS',flush=True)
