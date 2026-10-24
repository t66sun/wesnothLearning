import json,os,time,subprocess
from pathlib import Path
import torch
from learning.common import ROOT,read_json,sha256
from learning.manifest import verify_frozen
run=ROOT/'runs/v5_lite_resume_20261024_1420'
manifest=read_json(run/'manifest.json');verify_frozen(manifest)
print('TIME',time.strftime('%Y-%m-%d %H:%M:%S %Z'))
start=read_json(run/'launch.json');print('LAUNCH',json.dumps(start))
rows=[]
for fmt in manifest['config']['formats']:
 p=run/fmt/'latest.pt';saved=torch.load(p,map_location='cpu',weights_only=False);r=saved['runner']
 assert saved['manifest_sha256']==sha256(run/'manifest.json')
 step=max(float(s['step']) for s in saved['optimizer']['state'].values())
 info={k:r.get(k) for k in ['stage','phase','phase_deadline','version','batch','effective','error','counters']}
 info.update(format=fmt,optimizer_max_step=step,checkpoint_mtime=p.stat().st_mtime,pending_cursor=(r.get('pending_train') or {}).get('cursor'))
 history=[json.loads(s) for s in (run/fmt/'jobs.jsonl').read_text().splitlines()]
 info['new_results']=[dict(id=h['id'],status=h['status'],error=h.get('error')) for h in history if h['id'].startswith('rollout-') and int(h['id'].split('-')[1])>=dict(duel=213,ffa4=88,team2v2=50)[fmt]]
 info['new_errors_file']=(run/fmt/'errors.log').exists()
 rows.append(info)
print('CHECKPOINTS',json.dumps(rows,indent=2))
pgid=start['pgid'];group=[];pss=0
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  if os.getpgid(int(p.name))!=pgid:continue
  group.append(int(p.name));pss+=next(int(s.split()[1]) for s in (p/'smaps_rollup').read_text().splitlines() if s.startswith('Pss:'))
 except (OSError,StopIteration):pass
print('GROUP',group,'PSS_GIB',pss/1024**2)
print('MEMORY',subprocess.check_output(['free','-m'],text=True))
print('SCHEDULER_TAIL','\n'.join((run/'scheduler.jsonl').read_text().splitlines()[-8:]))
print('WRAPPER_LOG',(run/'continuation.log').read_text()[-3000:])
print('EXIT_FILE',(run/'continuation_exit.json').exists())
print('ORIGINAL_CHECKPOINT_HASHES',{fmt:sha256(Path(read_json(run/'migration.json')['parent'])/fmt/'latest.pt') for fmt in manifest['config']['formats']})
