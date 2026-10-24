import json,os,subprocess,time
from pathlib import Path
from learning.common import ROOT,read_json
run=ROOT/'runs/v5_lite_resume_20261024_1420'
launch=read_json(run/'launch.json');pgid=launch['pgid']
processes=[];pss=0
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  if os.getpgid(int(p.name))!=pgid:continue
  status=(p/'status').read_text();row=dict(pid=int(p.name),cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode())
  row['rss_kib']=next((int(s.split()[1]) for s in status.splitlines() if s.startswith('VmRSS:')),0)
  try:row['pss_kib']=next(int(s.split()[1]) for s in (p/'smaps_rollup').read_text().splitlines() if s.startswith('Pss:'));pss+=row['pss_kib']
  except OSError:pass
  processes.append(row)
 except (ProcessLookupError,FileNotFoundError,PermissionError):pass
print('NOW',subprocess.check_output(['date','-Is'],text=True).strip())
print('PROCESSES',json.dumps(processes))
print('GROUP_PSS_GIB',pss/1024**2)
print('MEMORY',subprocess.check_output(['free','-m'],text=True))
for fmt in ['duel','ffa4','team2v2']:
 state=read_json(run/fmt/'state.json')
 print('STATE',fmt,json.dumps({k:state.get(k) for k in ['stage','failed_stage','phase','phase_deadline','version','batch','effective','error','pending_train','counters']}))
 rows=[json.loads(s) for s in (run/fmt/'jobs.jsonl').read_text().splitlines()]
 new=[r for r in rows if r['id'].startswith('rollout-') and int(r['id'].split('-')[1])>=dict(duel=213,ffa4=88,team2v2=50)[fmt]]
 print('NEW_RESULTS',fmt,json.dumps([{k:r.get(k) for k in ['id','status','error','training_eligible','training_shard']} for r in new][-12:]))
 if (run/fmt/'errors.log').exists():print('ERROR',fmt,(run/fmt/'errors.log').read_text()[-3000:])
if (run/'scheduler.jsonl').exists():print('SCHEDULER_LAST','\n'.join((run/'scheduler.jsonl').read_text().splitlines()[-16:]))
print('WRAPPER_LOG',(run/'continuation.log').read_text()[-4000:])
print('FINISHED',(run/'continuation_exit.json').exists())
journal=subprocess.run(['journalctl','-k','--since','2026-10-24 14:15:00','--no-pager'],capture_output=True,text=True)
print('KERNEL_OOM',[s for s in journal.stdout.splitlines() if any(v in s.lower() for v in ['out of memory','killed process','oom-kill'])], 'journal_returncode',journal.returncode,'stderr',journal.stderr)
