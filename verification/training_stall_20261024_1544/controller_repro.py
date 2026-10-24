"""Read-only Ubuntu reproduction of stale adaptive windows; expected assertion failure."""
import copy,hashlib,json
from pathlib import Path
from learning.control import RewardController
from learning.rewards import RewardConfig
root=Path.cwd();run=root/'runs/v5_lite_resume_20261024_1420'
manifest=json.loads((run/'manifest.json').read_text())
for name in ['control.py','train.py','rewards.py','experiment.py']:
 digest=hashlib.sha256((root/'learning'/name).read_bytes()).hexdigest()
 print('SOURCE',name,digest,'matches_frozen',digest==manifest['source']['learning'][name],flush=True)
c=json.loads((run/'control/duel.json').read_text());obj=object.__new__(RewardController)
obj.__dict__.update(copy.deepcopy(c));obj.config=RewardConfig(**c['config'])
count=len(obj.blocks);windows=copy.deepcopy(obj.windows)
result=obj._decision({})
print('OBSERVED',json.dumps(dict(blocks_before=count,blocks_after=len(obj.blocks),windows_before=len(windows),windows_after=len(obj.windows),windows_unchanged=windows==obj.windows,decision=result,newest_pending_label=c['blocks'][-1]['label'])),flush=True)
assert count>=12 and len(windows)==3
assert len(obj.blocks)<count, 'three-window controller ignores newly accumulated complete validation blocks'
