import os,json,time
from pathlib import Path
from learning.common import ROOT,read_json
run=ROOT/'runs/v5_lite_resume_20261024_1420';group=read_json(run/'launch.json')['pgid']
def snapshot():
 rows={}
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   if os.getpgid(int(p.name))!=group:continue
   fields=(p/'stat').read_text().split();files=[]
   for f in (p/'fd').iterdir():
    try:
     target=os.readlink(f)
     if '/tmp/' in target and 'deleted' in target:files.append(dict(path=target,bytes=f.stat().st_size))
    except OSError:pass
   rows[p.name]=dict(cpu_ticks=int(fields[13])+int(fields[14]),files=files)
  except OSError:pass
 return rows
a=snapshot();time.sleep(5);b=snapshot()
print('TIME',time.strftime('%Y-%m-%d %H:%M:%S %Z'))
print('LIVE_WORK',{p:dict(cpu_tick_delta=b[p]['cpu_ticks']-a[p]['cpu_ticks'],before=a[p]['files'],after=b[p]['files']) for p in a.keys()&b.keys() if a[p]['files'] or b[p]['files']})
print('RECENT_SCHEDULER','\n'.join((run/'scheduler.jsonl').read_text().splitlines()[-12:]))
