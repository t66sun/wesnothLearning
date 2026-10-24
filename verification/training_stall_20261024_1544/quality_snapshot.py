"""Read-only quality snapshot of the running continuation and its parent."""
import json,time,os,subprocess
from pathlib import Path
ROOT=Path.cwd();run=ROOT/'runs/v5_lite_resume_20261024_1420'
def read(path):return json.loads(path.read_text())
def small(value,depth=0):
 if isinstance(value,dict):return {k:small(v,depth+1) for k,v in value.items() if k not in ['entities','spatial','candidates','records']}
 if isinstance(value,list):
  if len(value)>4:return dict(count=len(value),first=small(value[0],depth+1),last=small(value[-1],depth+1))
  return [small(v,depth+1) for v in value]
 return value
parent=Path(read(run/'migration.json')['parent']);print('TIME',time.strftime('%Y-%m-%d %H:%M:%S %Z'))
print('CLOCK',json.dumps(read(run/'clock.json')))
for fmt in ['duel','ffa4','team2v2']:
 state=read(run/fmt/'state.json')
 print('STATE',fmt,json.dumps({k:state.get(k) for k in ['stage','phase','version','batch','effective','error','counters','pending_validation','pending_train','control_metrics_error','best_key','bc_key','ppo_key','best_kind']}))
 history=state.get('history',[])
 ppo=[h for h in history if h.get('method')=='ppo']
 print('HISTORY',fmt,'counts',len(history),len(ppo),'first_ppo',json.dumps(small(ppo[:2])),'recent',json.dumps(small(ppo[-12:])))
 control=run/'control'/f'{fmt}.json'
 if control.exists():print('CONTROL',fmt,json.dumps(small(read(control))))
 for base in [parent,run]:
  path=base/fmt/'bc_gate.json'
  if path.exists():print('BC_GATE',fmt,str(base),json.dumps(small(read(path))))
  validation=base/fmt/'validation'
  paths=sorted(p for p in validation.glob('v*.json'))
  print('VALIDATION_COUNT',fmt,str(base),len(paths))
  for p in paths[-9:]:print('VALIDATION',fmt,str(base.name),p.name,json.dumps(small(read(p))))
  cs=sorted(validation.glob('control-v*.json'))
  for p in cs[-2:]:print('CONTROL_METRICS',fmt,str(base.name),p.name,json.dumps(small(read(p))))
  for p in sorted(validation.glob('control-v*.error.log'))[-2:]:print('CONTROL_ERROR',fmt,p.name,p.read_text()[-2500:])
 rows=[readline for readline in (run/fmt/'jobs.jsonl').read_text().splitlines() if readline]
 recent=[json.loads(s) for s in rows[-20:]]
 print('JOBS',fmt,json.dumps([dict(id=r['id'],status=r['status'],phase=r.get('meta',{}).get('phase'),faults=r.get('result',{}).get('faults'),winner=r.get('result',{}).get('winner'),survivors=r.get('result',{}).get('survivors'),reason=r.get('result',{}).get('reason'),turns=r.get('result',{}).get('turns'),reward_diagnostics=small(r.get('reward_diagnostics'))) for r in recent[-4:]]))
 for p in [run/fmt/'errors.log',run/fmt/'trainer_error.log']:
  if p.exists():print('ERROR',fmt,p.name,p.read_text()[-1500:])
print('CONTROL_EVENTS_TAIL','\n'.join((run/'control/events.jsonl').read_text().splitlines()[-9:]) if (run/'control/events.jsonl').exists() else 'none')
print('WRAPPER_LOG',(run/'continuation.log').read_text()[-2000:])
print('MEMORY',subprocess.check_output(['free','-m'],text=True))
print('SCHEDULER_TAIL','\n'.join((run/'scheduler.jsonl').read_text().splitlines()[-6:]))
