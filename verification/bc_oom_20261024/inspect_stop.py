import os,json,time,signal,datetime,subprocess
from pathlib import Path
stage=Path.cwd();run=stage/'runs/v5_lite18h_20261024_003512'
print('TIME',datetime.datetime.now().isoformat(),flush=True)
processes={}
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  status={x.split(':',1)[0]:x.split(':',1)[1].strip() for x in (p/'status').read_text().splitlines() if ':' in x}
  cmd=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace');cwd=os.readlink(p/'cwd')
  processes[int(p.name)]=dict(ppid=int(status['PPid']),cmd=cmd,cwd=cwd,rss=status.get('VmRSS'),state=status['State'])
 except (FileNotFoundError,PermissionError,ProcessLookupError):pass
roots=[pid for pid,d in processes.items() if 'learning run' in d['cmd'] and run.name in d['cmd'] and d['cwd']==str(stage)]
owned=set(roots)
while True:
 expanded=owned|{pid for pid,d in processes.items() if d['ppid'] in owned}
 if expanded==owned:break
 owned=expanded
print('ROOTS',roots,'OWNED',json.dumps({p:processes[p] for p in sorted(owned)}),flush=True)
print('STAGE_PROCESSES',json.dumps({p:d for p,d in processes.items() if d['cwd']==str(stage) and p!=os.getpid()}),flush=True)
for fmt in ('duel','ffa4','team2v2'):
 d=run/fmt
 s=json.loads((d/'state.json').read_text())
 print('STATE',fmt,json.dumps({k:s.get(k) for k in ('stage','version','batch','error','counters','pending_validation')}),flush=True)
 print('PENDING',fmt,json.dumps(s.get('pending_train'))[:1700],flush=True)
 for name in ('latest.pt','last_bc.pt','trainer_error.log','errors.log'):
  p=d/name
  if p.exists():
   print('FILE',fmt,name,p.stat().st_size,datetime.datetime.fromtimestamp(p.stat().st_mtime).isoformat(),flush=True)
   if p.suffix=='.log':print(p.read_text()[-7000:],flush=True)
for p in (stage/'runs/logs').glob('*'+run.name+'*'):
 with p.open('rb') as f:f.seek(max(0,p.stat().st_size-14000));print('MAINLOG',str(p),f.read().decode(errors='replace'),flush=True)
for pid in roots:
 if Path('/proc',str(pid)).exists():
  print('SEND_SIGINT',pid,flush=True);os.kill(pid,signal.SIGINT)
if roots:time.sleep(3)
alive=[]
for pid in sorted(owned):
 p=Path('/proc',str(pid))
 try:
  current=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
  if current and current==processes[pid]['cmd']:
   print('SEND_SIGTERM_REMAINING',pid,flush=True);os.kill(pid,signal.SIGTERM);alive.append(pid)
 except (FileNotFoundError,ProcessLookupError):pass
if alive:time.sleep(2)
print('REMAINING_OWNED',[p for p in owned if Path('/proc',str(p),'cmdline').exists() and Path('/proc',str(p),'cmdline').read_bytes()],flush=True)
print('MEMINFO',Path('/proc/meminfo').read_text(),flush=True)
print('PRESSURE',Path('/proc/pressure/memory').read_text(),flush=True)
print('DMESG',subprocess.run(['dmesg','--ctime','--level=err,warn'],capture_output=True,text=True).stdout[-15000:],flush=True)
print('KERNEL_JOURNAL',subprocess.run(['journalctl','-k','--since','2026-10-24 00:30:00','--no-pager','-n','100'],capture_output=True,text=True).stdout[-16000:],flush=True)
