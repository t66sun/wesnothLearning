from pathlib import Path
import hashlib,json
root=Path('/home/tongshu/acceptance/bounded_loop_20261101')
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
plan=root/'verification/bounded_loop_observed/plan.json'
result=dict(plan_path=str(plan),plan_sha256=sha(plan),declared_turn_limit=json.loads(plan.read_text())['turn_limit'],schedules=[])
for fmt in ('duel','ffa4','team2v2'):
    path=root/'runs/bounded_loop'/fmt/'schedules/bc-batch-000000.json'
    jobs=json.loads(path.read_text())
    result['schedules'].append(dict(format=fmt,path=str(path),sha256=sha(path),turn_limits=sorted({job['max_turns'] for job in jobs}),games=len(jobs)))
checkpoint=Path('/home/tongshu/acceptance/team_bc_readiness_20261102/runs/team_bc/team2v2/last_bc.pt')
result['checkpoint_after_sha256']=sha(checkpoint)
assert result['checkpoint_after_sha256']=='ffb554ca152ac93e3602bd45c98841238ef7ee59640b5bf7fb4ba64ba8148a97'
Path('/home/tongshu/acceptance/recruit_retention_fit_20261102/turn_limit_audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
