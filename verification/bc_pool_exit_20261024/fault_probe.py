"""Actual worker death through the real coordinator, without training games."""
from concurrent.futures.process import BrokenProcessPool
import json
import multiprocessing as mp
import os
from pathlib import Path
import subprocess
import sys
import time
from unittest import mock


def fail_worker(job):
    if job['die']:os._exit(71)
    time.sleep(30)
    return dict(id=job['id'],status='complete')


def waiting_trainer(directory,fmt,manifest,clock,requests,replies,resume):
    for batch in range(2):
        requests.put((fmt,[dict(id=f'{fmt}-{batch}',die=fmt=='duel',deadline=time.time()+60)],str(Path(directory)/'jobs.jsonl')))
        replies.get()


def child():
    from learning import coordinator
    original = coordinator.broker
    def broker(*args,**kwargs):return original(*args,**kwargs,play=fail_worker)
    experiment=coordinator.Experiment.__new__(coordinator.Experiment)
    experiment.directory=Path(sys.argv[2]);experiment.directory.mkdir()
    experiment.config=dict(formats=['duel','team2v2'],workers=2)
    experiment.manifest={};experiment.clock={};experiment.resume=False
    with mock.patch.object(coordinator,'trainer_main',waiting_trainer),mock.patch.object(coordinator,'broker',broker):
        try:experiment.run()
        except BrokenProcessPool as exc:print('EXPECTED_POOL_FAILURE',str(exc),flush=True)
        else:raise AssertionError('worker death did not reach coordinator')
    assert not mp.active_children(),[(p.pid,p.is_alive()) for p in mp.active_children()]
    print('FAULT_RESULT',json.dumps(dict(passed=True,children=0)),flush=True)


if __name__=='__main__':
    if sys.argv[1]=='--child':child()
    else:
        process=subprocess.Popen([sys.executable,__file__,'--child',sys.argv[1]],start_new_session=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        try:
            text,_=process.communicate(timeout=45)
        except subprocess.TimeoutExpired:
            import signal
            assert os.getpgid(process.pid)==process.pid
            os.killpg(process.pid,signal.SIGTERM);text,_=process.communicate(timeout=10)
            print(text);raise AssertionError('pool failure left waiting processes')
        print(text)
        assert process.returncode==0 and '"passed": true' in text
