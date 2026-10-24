"""Stop only the previously recorded continuation process group, preserving checkpoints."""
import json,os,signal,time
from pathlib import Path
root=Path.cwd();run=root/'runs/v5_lite_resume_20261024_1420'
launch=json.loads((run/'launch.json').read_text());pgid=launch['pgid'];wrapper=launch['pid']
def members():
 rows=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   pid=int(p.name)
   if os.getpgid(pid)!=pgid:continue
   stat=(p/'stat').read_text().split();cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode()
   if stat[2]=='Z':continue
   rows.append(dict(pid=pid,cmd=cmd,state=stat[2]))
  except (FileNotFoundError,ProcessLookupError):pass
 return rows
initial=members();print('BEFORE',json.dumps(initial),flush=True)
assert wrapper==pgid and wrapper!=os.getpid()
if initial:
 w=next((r for r in initial if r['pid']==wrapper),None)
 assert w and str(run/'continue_run.py') in w['cmd'], 'wrapper identity differs'
 os.kill(wrapper,signal.SIGSTOP)
 for row in initial:
  if row['pid']!=wrapper:
   try:os.kill(row['pid'],signal.SIGINT)
   except ProcessLookupError:pass
 end=time.monotonic()+20
 while time.monotonic()<end and any(r['pid']!=wrapper and 'resource_tracker' not in r['cmd'] for r in members()):time.sleep(.2)
 remaining=members();print('AFTER_INTERRUPT',json.dumps(remaining),flush=True)
 for row in remaining:
  try:os.kill(row['pid'],signal.SIGKILL if row['pid']==wrapper else signal.SIGTERM)
  except ProcessLookupError:pass
 time.sleep(1)
 for row in members():
  try:os.kill(row['pid'],signal.SIGKILL)
  except ProcessLookupError:pass
 time.sleep(.5)
assert not members(),members()
print('STOPPED',time.strftime('%Y-%m-%d %H:%M:%S %Z'),'remaining=[]',flush=True)
for fmt in ['duel','ffa4','team2v2']:
 state=json.loads((run/fmt/'state.json').read_text())
 print('STATE',fmt,json.dumps({k:state.get(k) for k in ['stage','version','batch','effective','pending_train','pending_validation','counters','error']}),flush=True)
