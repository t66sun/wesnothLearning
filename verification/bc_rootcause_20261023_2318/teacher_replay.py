"""Replay recorded public intents; measure teacher time/scan stability only."""
import collections,copy,gzip,json,time
from unittest.mock import patch
from learning.common import ROOT,read_json,write_json
from learning.lite_host import LiteHost,teacher_candidate
from learning.lite_policy import game_spec
from learning.rowpack import unpack_line
from learning.rules_catalog import resolve_dir

old=ROOT/'verification/bc_quality_ubuntu_20261023'
out=ROOT/'verification/bc_rootcause_20261023_2318'
rules=json.loads((resolve_dir()/'rules.json').read_text())
results=[]
for shard in sorted((old/'data/ffa4').glob('*validation*.jsonl.gz')):
 job=read_json(shard.with_name(shard.name.replace('.jsonl.gz','.job.json')))
 host=LiteHost(game_spec(job,rules),resolve_dir())
 # Collection records initial observations for every seat before actions.
 for side in range(1,5):host.decision(side,generate_candidates=False)
 probe=host.modules['astra/four.lua']
 probe=probe.replace('local sims=0','local sims=0; __bc_scan={sims=0,cut="none"}')
 probe=probe.replace('sims=sims+1','sims=sims+1;__bc_scan.sims=sims')
 probe=probe.replace('if sims>=240 or wesnoth.ms_since_init()-start>350 then return best end',
   'if sims>=240 or wesnoth.ms_since_init()-start>350 then __bc_scan.cut=sims>=240 and "sim_cap" or "wall_time";return best end')
 probe=probe.replace('data.plan=a','if a then a._scan=__bc_scan end;data.plan=a')
 # Diagnostic-only workaround for the independently reproduced restore/copy
 # bug: JSON arrays can have a protected (boolean) metatable. Production is
 # untouched; repeated ordinary decisions below do not restore snapshots.
 probe='do local old=getmetatable;function getmetatable(t) local m=old(t);return type(m)=="table" and m or nil end end\n'+probe
 raw=[]
 with gzip.open(shard,'rt') as stream:
  for line in stream:
   r,_=unpack_line(line);raw.append(r)
 raw.sort(key=lambda r:r['decision'])
 count=0
 for r in raw:
  side=r['side'];current=host.decision(side,generate_candidates=False)
  assert current['turn']==r['turn'],(r['decision'],current['turn'],r['turn'])
  actual=r.get('actual')
  if not actual:raise RuntimeError(('missing original intent',r['decision'],r.keys()))
  # Six later movement decisions per family sample attack rejection in contact.
  if actual['kind']=='move' and r['turn']>=5 and count<6:
   snapshot=host.snapshot();repeated=[]
   for repetition in range(3):
    start=time.monotonic();decision=host.decision(side,teacher=True,generate_candidates=False)
    repeated.append(dict(action=teacher_candidate(decision['teacher_action']),seconds=time.monotonic()-start))
   # A separate diagnostic host with instrumentation only; no collected actor rows.
   modules=dict(host.modules);modules['astra/four.lua']=probe
   with patch('learning.lite_host.host_modules',return_value=modules):
    instrumented=LiteHost(game_spec(job,rules),resolve_dir())
   instrumented.restore(snapshot);decision=instrumented.decision(side,teacher=True,generate_candidates=False)
   record=dict(game=job['id'],side=side,turn=r['turn'],decision=r['decision'],original=actual,
     repeated=repeated,diagnostic_plan=decision['teacher_action'])
   results.append(record);count+=1
   print('TEACHER_REPLAY',json.dumps(record),flush=True)
   host.decision(side,generate_candidates=False)
   instrumented.adapter.close()
  result=host.execute(actual)
  assert result.get('committed',result.get('execution',{}).get('changed',False)),(r['decision'],result)
  if count>=6:break
 host.adapter.close()
write_json(out/'teacher_replay.json',results)
print('TEACHER_REPLAY_DONE',len(results),flush=True)
