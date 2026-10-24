"""Deploy only into a new isolated validation directory; retain local outputs."""
import getpass
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time
import zipfile
import paramiko

root=Path.cwd();evidence=Path(__file__).resolve().parent
stage='/home/tongshu/myDev/wesnothLearning/validation_memory_repair_20261024_1321'
old='/home/tongshu/myDev/wesnothLearning/validation_training_repair_20261023_194022'
relative=evidence.relative_to(root).as_posix()
client=paramiko.SSHClient();client.load_system_host_keys();client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.122.118',username='tongshu',password=getpass.getpass('SSH password: '),look_for_keys=False,allow_agent=False,timeout=10)
sftp=client.open_sftp()


def execute(label,command,payload=None):
    log=evidence/f'{label}.ubuntu.txt'
    if log.exists():raise FileExistsError(f'preserve original evidence: {log}')
    si,so,se=client.exec_command(command,timeout=1000)
    if payload is not None:si.write(payload)
    si.channel.shutdown_write();chunks=[]
    while not so.channel.exit_status_ready() or so.channel.recv_ready() or so.channel.recv_stderr_ready():
        for check,receive in ((so.channel.recv_ready,so.channel.recv),(so.channel.recv_stderr_ready,so.channel.recv_stderr)):
            if check():
                part=receive(32768).decode(errors='replace');chunks.append(part);print(part,end='',flush=True)
        time.sleep(.1)
    code=so.channel.recv_exit_status();log.write_text(''.join(chunks)+'\nEXIT '+str(code)+'\n',encoding='utf-8')
    print('EXIT',code,flush=True)


try:
    print('READY deploy / tests / pressure / fault / result / exit',flush=True)
    for line in sys.stdin:
        value=line.strip()
        if value=='exit':break
        if value=='deploy':
            files=subprocess.check_output(['git','ls-files'],text=True).splitlines()
            bundle=evidence/'source_bundle.zip'
            with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as archive:
                for name in files:
                    if name.startswith(('learning/','lua/','engine_lite/','vendor/arena/','tests/')) or ('/' not in name and name.endswith('.py')):
                        archive.write(root/name,name)
                for name in ('test_pool_failure.py','v5/test_collection_memory.py'):
                    if 'tests/'+name not in files:archive.write(root/'tests'/name,'tests/'+name)
                for name in ('stress_probe.py','fault_probe.py'):
                    archive.write(evidence/name,relative+'/'+name)
                archive.writestr(relative+'/legacy_sequences.py',subprocess.check_output(['git','show','5ed7360:learning/sequences.py']))
            sftp.put(str(bundle),'/tmp/wesnoth_memory_repair_20261024_1321.zip')
            payload=f'''from pathlib import Path
import zipfile,os,json
stage=Path({stage!r});stage.mkdir()
with zipfile.ZipFile('/tmp/wesnoth_memory_repair_20261024_1321.zip') as z:z.extractall(stage)
(stage/'data').mkdir(exist_ok=True)
os.symlink({old!r}+'/.venv',stage/'.venv')
os.symlink('/home/tongshu/myDev/wesnothLearning/WesnothLearning/rules',stage/'data/rules')
print('DEPLOYED',str(stage))
'''
            execute('deploy','python3 -u -',payload)
        elif value in ('tests','pressure','fault'):
            prefix='cd '+shlex.quote(stage)+' && PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH='+shlex.quote(stage+':'+stage+'/vendor/arena')+' .venv/bin/python -u '
            if value=='tests':
                target='-m unittest tests.v5.test_collection_memory tests.test_pool_failure tests.v5.test_pipeline_contract.ShardSequenceTests tests.v5.test_lite_policy_memory tests.v5.test_pipeline_contract.LiteJobTests tests.test_experiment.ExperimentTests.test_scheduler_round_robin_and_global_process_limit -v'
            elif value=='pressure':target=relative+'/stress_probe.py '+relative+'/pressure_run'
            else:target=relative+'/fault_probe.py '+relative+'/fault_run'
            execute(value,prefix+target)
        elif value=='result':
            sftp.get(stage+'/'+relative+'/pressure_run/result.json',str(evidence/'stress_result.json'))
            print('FETCHED stress_result.json',flush=True)
        elif value:raise ValueError(value)
finally:sftp.close();client.close()
