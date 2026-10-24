"""Local analysis of captured state; no server work and no training."""
import copy,json,statistics
from pathlib import Path
from learning.control import RewardController
from learning.rewards import RewardConfig
root=Path(__file__).resolve().parent
out={}
for fmt,restored in [('duel',212),('ffa4',88),('team2v2',50)]:
 state=json.loads((root/f'{fmt}_state.json').read_text())
 h=[r for r in state['history'][restored:] if r['method']=='ppo']
 values=[r['updates'] for r in h]
 c=json.loads((root/f'{fmt}_control.json').read_text())
 obj=object.__new__(RewardController)
 obj.__dict__.update(copy.deepcopy(c));obj.config=RewardConfig(**c['config'])
 before=copy.deepcopy(obj.windows);pending=len(obj.blocks)
 changes,reason=obj._decision({})
 latest=RewardController._window(c['blocks'][-12:]) if len(c['blocks'])>=12 else None
 out[fmt]=dict(version=state['version'],since_restore=dict(batches=len(h),optimizer_steps=sum(values),mean_steps=statistics.mean(values) if values else None,median_steps=statistics.median(values) if values else None,min_steps=min(values) if values else None,max_steps=max(values) if values else None,kl_stopped=sum(bool(r.get('kl_stopped')) for r in h),zero_step=sum(v==0 for v in values),missing_decisions_metric=sum('decisions_seen' not in r for r in h),last_kl=[r.get('approx_kl') for r in h[-5:]]),reward_config=c['config'],controller=dict(pending_blocks=pending,windows=len(c['windows']),blocks_after_decision=len(obj.blocks),windows_unchanged=before==obj.windows,decision=changes,reason=reason,frozen_windows=c['windows'],latest_12_block_window=latest,pending_labels=[b.get('label') for b in c['blocks']]))
print(json.dumps(out,indent=2))
(root/'analysis.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
# Red-capable check: once three windows exist, twelve new complete blocks
# must still enter the rolling window instead of leaving it permanently frozen.
assert out['duel']['controller']['pending_blocks']>=12
assert out['duel']['controller']['windows']==3
assert not out['duel']['controller']['windows_unchanged'], 'Adaptive rolling window is frozen at three windows despite newer complete blocks'
