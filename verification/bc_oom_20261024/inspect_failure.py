import json,subprocess,datetime,hashlib
from pathlib import Path
stage=Path.cwd();run=stage/'runs/v5_lite18h_20261024_003512'
j=subprocess.run(['journalctl','-k','--since','2026-10-24 09:55:00','--until','2026-10-24 10:10:00','--no-pager'],capture_output=True,text=True)
lines=j.stdout.splitlines()
print('KERNEL_LOG',j.returncode,'lines',len(lines))
for line in lines:
 if any(x in line for x in ('oom','Out of memory','Mem-Info','active_anon','inactive_anon','Node 0','pages RAM','pages reserved','pages HighMem','Free swap','Total swap','python','invoked','pagecache','unreclaimable','balloon')):print(line)
for fmt in ('duel','ffa4','team2v2'):
 d=run/fmt;s=json.loads((d/'state.json').read_text())
 print('STATE_META',fmt,json.dumps({k:s.get(k) for k in ('stage','failed_stage','phase','phase_history','forced_ppo','effective','version','batch','bc_quality_best','bc_plateau')}))
 print('HISTORY_TAIL',fmt,json.dumps(s['history'][-3:]))
 p=d/'jobs.jsonl';rows=[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
 bad=[r for r in rows if r.get('status')!='complete']
 print('JOBS_COUNTS',fmt,len(rows),'bad',len(bad))
 for r in bad[-8:]:print('BAD_JOB',fmt,json.dumps(r)[:8000])
 print('LAST_IDS',fmt,[(r.get('id'),r.get('status'),r.get('result',{}).get('reason')) for r in rows[-8:]])
 for p in sorted((d/'schedules').glob('*.json'))[-2:]:
  data=json.loads(p.read_text());print('SCHEDULE',fmt,p.name,json.dumps(data)[:2500])
for name in ('trainer_exit.log','scheduler.jsonl'):
 p=run/name
 if p.exists():
  with p.open('rb') as f:f.seek(max(0,p.stat().st_size-18000));print('TAIL',name,f.read().decode(errors='replace')[-16000:])
print('POST_STOP_PROCESSES',subprocess.check_output(['ps','-p','192814,192821,192822,192823,192824,192834','-o','pid,ppid,stat,args'],text=True) if Path('/proc/192814').exists() else 'main PID absent')
print('FROZEN',json.dumps({k:v for k,v in json.loads((run/'manifest.json').read_text()).items() if k in ('config','rules','parameters')}))
for rel,start,end in [('learning/coordinator.py',30,114),('learning/lite_host.py',100,135),('learning/lite_host.py',220,420)]:
 lines=(stage/rel).read_text().splitlines();print('SERVER_SOURCE',rel,'\n'+'\n'.join(f'{i+1}: {x}' for i,x in enumerate(lines) if start<=i+1<=end))
import torch
torch.set_num_threads(1)
for fmt in ('duel','ffa4','team2v2'):
 p=run/fmt/'latest.pt'
 ck=torch.load(p,map_location='cpu',weights_only=False)
 print('CHECKPOINT_LOAD',fmt,json.dumps(dict(version=ck['runner']['version'],stage=ck['runner']['stage'],features=ck['features']['version'],optimizer_entries=len(ck['optimizer']['state']),model_tensors=len(ck['model']),sha256=hashlib.sha256(p.read_bytes()).hexdigest())))
 del ck
