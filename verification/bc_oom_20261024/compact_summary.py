import json,re,subprocess,datetime
from pathlib import Path
stage=Path.cwd();run=stage/'runs/v5_lite18h_20261024_003512'
raw=subprocess.run(['journalctl','-k','--since','2026-10-24 10:07:00','--until','2026-10-24 10:09:00','--no-pager'],capture_output=True,text=True).stdout
tasks=[];first=None
for line in raw.splitlines():
 if 'invoked oom-killer' in line:
  if first is not None:break
  first=line
 match=re.search(r'\[\s*(\d+)\]\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(-?\d+)\s+(\S+)',line)
 if match:
  fields=match.groups();tasks.append(dict(pid=int(fields[0]),name=fields[-1],rss_mib=int(fields[4])*4096/2**20,swap_mib=int(fields[9])*4096/2**20))
python=[x for x in tasks if x['name']=='python']
print('FIRST_OOM',first)
print('OOM_PYTHON',json.dumps(python))
print('OOM_TOTAL',json.dumps(dict(python_count=len(python),python_rss_mib=sum(x['rss_mib'] for x in python),python_swap_mib=sum(x['swap_mib'] for x in python),all_rss_mib=sum(x['rss_mib'] for x in tasks),all_swap_mib=sum(x['swap_mib'] for x in tasks))))
print('KILLED_PYTHON',[x for x in raw.splitlines() if 'Killed process' in x and '(python)' in x])
for fmt in ('duel','ffa4','team2v2'):
 d=run/fmt;largest=[]
 with (d/'jobs.jsonl').open() as f:
  for line in f:
   r=json.loads(line)
   if r.get('status')!='complete':continue
   count=r.get('training_shard') or {}
   largest.append(dict(id=r['id'],rows=count.get('raw_records',r.get('coverage',{}).get('total',0)),turns=r.get('result',{}).get('turns'),reason=r.get('result',{}).get('reason')))
 print('LARGEST_COMPLETED',fmt,json.dumps(sorted(largest,key=lambda x:x['rows'],reverse=True)[:4]))
events=[json.loads(x) for x in (run/'scheduler.jsonl').read_text().splitlines()]
active={}
for x in events:
 if x['time']>datetime.datetime(2026,10,24,10,7,18).timestamp():break
 if x['event']=='start':active[(x['format'],x['id'])]=x
 elif x['event']=='finish':active.pop((x['format'],x['id']),None)
print('OOM_ACTIVE',json.dumps(list(active.values())))
print('SCHEDULER_LAST',json.dumps(events[-10:]))
for rel in ('learning/lite_host.py','learning/lite_policy.py','learning/sequences.py','learning/data.py','learning/coordinator.py'):
 print('SOURCE_LENGTH',rel,len((stage/rel).read_text().splitlines()))
print('LIVE_STAGE',subprocess.check_output(['ps','-eo','pid,ppid,args'],text=True).count('v5_lite18h_20261024_003512'))
