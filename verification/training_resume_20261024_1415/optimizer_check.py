import json,time
from pathlib import Path
import torch
from learning.common import ROOT,read_json
run=ROOT/'runs/v5_lite_resume_20261024_1420'
summary={}
for fmt,minimum in [('duel',2173),('ffa4',1772),('team2v2',695)]:
 s=torch.load(run/fmt/'latest.pt',map_location='cpu',weights_only=False);r=s['runner']
 step=max(float(v['step']) for v in s['optimizer']['state'].values())
 summary[fmt]=dict(stage=r['stage'],error=r.get('error'),version=r['version'],optimizer_step=step,advanced=step>minimum,pending_cursor=(r.get('pending_train') or {}).get('cursor'))
print(time.strftime('%Y-%m-%d %H:%M:%S %Z'),json.dumps(summary),flush=True)
print('WRAPPER_EXIT',(run/'continuation_exit.json').exists(),'NEW_ERRORS',list(run.glob('*/errors.log')),flush=True)
