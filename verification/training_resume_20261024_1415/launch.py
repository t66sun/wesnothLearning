import os,subprocess,time,json
from pathlib import Path
from learning.common import ROOT,write_json,read_json
from learning.experiment import run_lock
from learning.coordinator import Experiment
run=ROOT/'runs/v5_lite_resume_20261024_1420'
with run_lock(run):
    exp=Experiment(run,resume=True)
    assert exp.clock['deadline']==1792852200.0
    assert not (run/'continuation_started.json').exists()
    script=run/'continue_run.py'
    assert not script.exists()
    script.write_text('"""Run the authorized PPO continuation, then explicit final evaluation."""\nimport json\nfrom pathlib import Path\nimport subprocess\nimport sys\nimport time\nfrom learning.common import read_json,write_json\nfrom learning.phases import request_phase\n\nRUN=Path(__file__).resolve().parent\n\ndef main():\n    write_json(RUN/\'continuation_started.json\',dict(time=time.time(),pid=__import__(\'os\').getpid()))\n    first=subprocess.run([sys.executable,\'-u\',\'-m\',\'learning\',\'run\',\'--resume\',str(RUN)])\n    assert first.returncode==0,(\'PPO continuation failed\',first.returncode)\n    summary=read_json(RUN/\'summary.json\')\n    assert summary[\'status\']==\'stage_complete\',summary\n    for fmt in read_json(RUN/\'manifest.json\')[\'config\'][\'formats\']:\n        state=read_json(RUN/fmt/\'state.json\')\n        assert state[\'stage\']==\'ppo_complete\' and not state.get(\'error\'),(fmt,state[\'stage\'],state.get(\'error\'))\n    # No new budget: use the migrated clock\'s existing 22:30 total deadline.\n    request_phase(RUN,\'evaluate\',reason=\'Authorized continuation: PPO complete, enter final acceptance within 22:30 deadline\')\n    final=subprocess.run([sys.executable,\'-u\',\'-m\',\'learning\',\'run\',\'--resume\',str(RUN)])\n    write_json(RUN/\'continuation_exit.json\',dict(time=time.time(),returncode=final.returncode))\n    return final.returncode\n\nif __name__==\'__main__\':sys.exit(main())\n',encoding='utf-8')
log=(run/'continuation.log').open('ab',buffering=0)
proc=subprocess.Popen([str(ROOT/'.venv/bin/python'),'-u',str(script)],cwd=ROOT,
                      stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
                      start_new_session=True,env=dict(os.environ))
write_json(run/'launch.json',dict(pid=proc.pid,pgid=os.getpgid(proc.pid),time=time.time(),source_root=str(ROOT),command=proc.args))
time.sleep(3)
assert proc.poll() is None,(proc.returncode,(run/'continuation.log').read_text()[-6000:])
print('LAUNCHED',json.dumps(read_json(run/'launch.json')),flush=True)
print('CLOCK',json.dumps(exp.clock),flush=True)
print('LOG', (run/'continuation.log').read_text()[-5000:],flush=True)
