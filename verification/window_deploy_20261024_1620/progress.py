"""Read-only live continuation verification."""
import json,os,sys,time,subprocess
from pathlib import Path
root=Path('/home/tongshu/myDev/wesnothLearning/validation_window_fix_20261024_1630')
sys.path.insert(0,str(root));sys.path.insert(1,str(root/'vendor/arena'))
import torch
from learning.common import read_json,sha256
from learning.manifest import verify_frozen
run=root/'runs/v5_lite_windowfix_20261024_1630';manifest=read_json(run/'manifest.json');verify_frozen(manifest)
launch=read_json(run/'launch.json');print('TIME',time.strftime('%Y-%m-%d %H:%M:%S %Z'))
print('LAUNCH',json.dumps(launch));print('CLOCK',json.dumps(read_json(run/'clock.json')))
for fmt,step0 in [('duel',1780),('ffa4',1820),('team2v2',746)]:
 saved=torch.load(run/fmt/'latest.pt',map_location='cpu',weights_only=False);state=saved['runner']
 assert saved['manifest_sha256']==sha256(run/'manifest.json')
 step=max(float(v['step']) for v in saved['optimizer']['state'].values())
 print('STATE',fmt,json.dumps(dict(stage=state['stage'],version=state['version'],batch=state['batch'],optimizer_step=step,advanced=step>step0,effective=state['effective'],error=state.get('error'),pending_cursor=(state.get('pending_train') or {}).get('cursor'),pending_validation=state.get('pending_validation'),phase=state.get('phase'),phase_deadline=state.get('phase_deadline'))))
 control=read_json(run/'control'/f'{fmt}.json');print('CONTROL',fmt,json.dumps(dict(config=control['config'],windows=len(control['windows']),pending_blocks=len(control['blocks']))))
 initial=read_json(run/'migration.json')['checkpoints'][fmt]['batch']
 rows=[json.loads(s) for s in (run/fmt/'jobs.jsonl').read_text().splitlines()]
 fresh=[r for r in rows if r['id'].startswith('rollout-') and int(r['id'].split('-')[1])>=initial]
 print('NEW_RESULTS',fmt,json.dumps([dict(id=r['id'],status=r['status'],error=r.get('error'),eligible=r.get('training_eligible')) for r in fresh][-12:]))
 for name in ['errors.log','trainer_error.log']:
  p=run/fmt/name
  if p.exists():print('NEW_ERROR',fmt,name,p.read_text()[-2000:])
pss=0;group=[]
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  if os.getpgid(int(p.name))!=launch['pgid']:continue
  stat=(p/'stat').read_text().split()
  if stat[2]=='Z':continue
  group.append(int(p.name));pss+=next(int(s.split()[1]) for s in (p/'smaps_rollup').read_text().splitlines() if s.startswith('Pss:'))
 except (OSError,StopIteration):pass
print('GROUP',group,'PSS_GIB',pss/1024**2)
print('MEMORY',subprocess.check_output(['free','-m'],text=True))
print('SCHEDULER','\n'.join((run/'scheduler.jsonl').read_text().splitlines()[-10:]) if (run/'scheduler.jsonl').exists() else 'not yet')
print('WRAPPER_LOG',(run/'continuation.log').read_text()[-2000:])
print('EXIT_FILE',(run/'continuation_exit.json').exists())
parent=Path(read_json(run/'migration.json')['parent'])
print('PARENT_UNCHANGED',sha256(parent/'manifest.json')==read_json(run/'migration.json')['parent_manifest_sha256'])
for fmt,lineage in read_json(run/'migration.json')['checkpoints'].items():
 assert sha256(parent/fmt/'latest.pt')==lineage['parent_latest_sha256']
print('PARENT_LATEST_HASHES_UNCHANGED',True)
