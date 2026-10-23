import json, pathlib, subprocess, sys
p=pathlib.Path.cwd()
run=p/'verification/training_repair_20261023/cli_bc_boundary'
command=[sys.executable,'-m','learning','run','--run-dir',str(run),'--phase','bc',
         '--hours','0.000001','--formats','duel','--workers','1',
         '--wesnoth',str(p/'.runtime/install/bin/wesnoth')]
print('COMMAND',command,flush=True)
r=subprocess.run(command,text=True,capture_output=True,timeout=120)
print(r.stdout,r.stderr,flush=True)
assert r.returncode==0,r.returncode
summary=json.loads((run/'summary.json').read_text())
assert summary['status']=='stage_complete',summary
assert summary['formats']['duel']['phase']=='bc'
assert not (run/'duel/selected.pt').exists()
r=subprocess.run([sys.executable,'-m','learning','phase','show','--run-dir',str(run)],text=True,capture_output=True,timeout=30)
print(r.stdout,r.stderr,flush=True)
assert r.returncode==0
assert json.loads(r.stdout)['duel']['stage']=='bc_complete'
print('CLI_COORDINATOR_BOUNDARY_PASS',flush=True)
