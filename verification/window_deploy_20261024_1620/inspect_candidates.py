import json,torch,time
from pathlib import Path
from learning.common import sha256,read_json
from learning.export import load_model
root=Path.cwd();run=root/'runs/v5_lite_resume_20261024_1420'
parents=[run,Path(read_json(run/'migration.json')['parent'])]
print('TIME',time.strftime('%Y-%m-%d %H:%M:%S %Z'))
for fmt in ['duel','ffa4','team2v2']:
 for base in parents:
  for name in ['latest.pt','best.pt','best_ppo.pt','last_ppo.pt','best_bc.pt','last_bc.pt']:
   p=base/fmt/name
   if not p.exists():continue
   try:
    model,s=load_model(p,fmt);r=s['runner']
    optimizer=torch.optim.Adam(model.parameters(),lr=1e-4);optimizer.load_state_dict(s['optimizer'])
    steps=max(float(v['step']) for v in s['optimizer']['state'].values())
    print('CANDIDATE',json.dumps(dict(path=str(p),sha256=sha256(p),version=r['version'],batch=r['batch'],stage=r['stage'],phase=r.get('phase'),phase_deadline=r.get('phase_deadline'),effective=r.get('effective'),forced_ppo=r.get('forced_ppo'),best_key=r.get('best_key'),ppo_key=r.get('ppo_key'),bc_key=r.get('bc_key'),best_kind=r.get('best_kind'),pending_train=r.get('pending_train'),pending_validation=r.get('pending_validation'),optimizer_step=steps,controller_cursor=r.get('reward_controller',{}).get('cursor'),clock=r['clock'],keys=list(s))),flush=True)
   except Exception as exc:print('UNUSABLE',str(p),repr(exc),flush=True)
  for p in sorted((base/fmt/'validation').glob('v*.json')):
   if '"promotion"' in p.read_text() or p.name in ['v000220.json','v000250.json','v000060.json']:
    print('VALIDATION',fmt,str(p),json.dumps(read_json(p)),flush=True)
  state=read_json(base/fmt/'state.json')
  print('OPERATIONAL_STATE',fmt,str(base),json.dumps({k:state.get(k) for k in ['stage','version','batch','best_key','best_kind','champion','effective','error','counters']}),flush=True)
