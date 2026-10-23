"""Retest only the real restore/query failure, without the diagnostic workaround."""
import gzip,json
from learning.common import ROOT,read_json,write_json
from learning.lite_host import LiteHost,teacher_candidate
from learning.lite_policy import game_spec
from learning.rowpack import unpack_line
from learning.rules_catalog import resolve_dir

out=ROOT/'verification/bc_rootcause_20261023_2318'
old=ROOT/'verification/bc_quality_ubuntu_20261023/data/ffa4'
job=read_json(old/'t5-ffa4-validation-0.job.json')
rules=json.loads((resolve_dir()/'rules.json').read_text())
host=LiteHost(game_spec(job,rules),resolve_dir())
for side in range(1,5):host.decision(side,generate_candidates=False)
rows=[]
with gzip.open(old/'t5-ffa4-validation-0.jsonl.gz','rt') as stream:
 for line in stream:rows.append(unpack_line(line)[0])
for r in sorted(rows,key=lambda r:r['decision']):
 host.decision(r['side'],generate_candidates=False)
 if r['turn']>=5 and r['actual']['kind']=='move':
  saved=host.snapshot();host.restore(saved)
  query=host.decision(r['side'],teacher=True,generate_candidates=False)
  assert teacher_candidate(query['teacher_action'])==r['actual']
  assert host.snapshot()['game']==saved['game']
  record=dict(game=job['id'],decision=r['decision'],side=r['side'],turn=r['turn'],
   expected=r['actual'],restored=teacher_candidate(query['teacher_action']),game_unchanged=True,workaround=False)
  write_json(out/'restore_real_case.json',record);print('REAL_RESTORE_PASS',json.dumps(record),flush=True);break
 assert host.execute(r['actual'])['committed']
else:raise AssertionError('no matching replay case')
host.adapter.close()
