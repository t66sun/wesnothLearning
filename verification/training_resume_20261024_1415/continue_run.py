"""Run the authorized PPO continuation, then explicit final evaluation."""
import json
from pathlib import Path
import subprocess
import sys
import time
from learning.common import read_json,write_json
from learning.phases import request_phase

RUN=Path(__file__).resolve().parent

def main():
    write_json(RUN/'continuation_started.json',dict(time=time.time(),pid=__import__('os').getpid()))
    first=subprocess.run([sys.executable,'-u','-m','learning','run','--resume',str(RUN)])
    assert first.returncode==0,('PPO continuation failed',first.returncode)
    summary=read_json(RUN/'summary.json')
    assert summary['status']=='stage_complete',summary
    for fmt in read_json(RUN/'manifest.json')['config']['formats']:
        state=read_json(RUN/fmt/'state.json')
        assert state['stage']=='ppo_complete' and not state.get('error'),(fmt,state['stage'],state.get('error'))
    # No new budget: use the migrated clock's existing 22:30 total deadline.
    request_phase(RUN,'evaluate',reason='Authorized continuation: PPO complete, enter final acceptance within 22:30 deadline')
    final=subprocess.run([sys.executable,'-u','-m','learning','run','--resume',str(RUN)])
    write_json(RUN/'continuation_exit.json',dict(time=time.time(),returncode=final.returncode))
    return final.returncode

if __name__=='__main__':sys.exit(main())
