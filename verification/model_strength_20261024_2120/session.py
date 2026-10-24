"""Continue isolated validation with individually preserved command outputs."""
import getpass
from pathlib import Path
import shlex
import sys
import time
import paramiko

root=Path.cwd();out=Path(__file__).resolve().parent
stage='/home/tongshu/myDev/wesnothLearning/validation_window_fix_20261024_1630'
client=paramiko.SSHClient();client.load_system_host_keys();client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.122.118',username='tongshu',password=getpass.getpass('SSH password: '),look_for_keys=False,allow_agent=False,timeout=10)
sftp=client.open_sftp();print('READY label command / fetch remote-relative local-name / exit',flush=True)
try:
 for line in sys.stdin:
  value=line.strip()
  if value=='exit':break
  if not value:continue
  if value.startswith('fetch '):
   _,remote,name=value.split();sftp.get(stage+'/'+remote,str(out/name));print('FETCHED',name,flush=True);continue
  label,command=value.split(' ',1);log=out/(label+'.ubuntu.txt')
  if log.exists():raise FileExistsError(log)
  payload=None
  if command.startswith('<'):
   payload=(root/command[1:]).read_text(encoding='utf-8-sig');command='.venv/bin/python -u -'
  prefix='cd '+shlex.quote(stage)+' && PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONPATH='+shlex.quote(stage+':'+stage+'/vendor/arena')+' '
  si,so,se=client.exec_command(prefix+command,timeout=1200)
  if payload is not None:si.write(payload)
  si.channel.shutdown_write();chunks=[]
  while not so.channel.exit_status_ready() or so.channel.recv_ready() or so.channel.recv_stderr_ready():
   for check,read in ((so.channel.recv_ready,so.channel.recv),(so.channel.recv_stderr_ready,so.channel.recv_stderr)):
    if check():
     text=read(32768).decode(errors='replace');chunks.append(text);print(text,end='',flush=True)
   time.sleep(.1)
  code=so.channel.recv_exit_status();log.write_text(''.join(chunks)+'\nEXIT '+str(code)+'\n',encoding='utf-8');print('EXIT',code,flush=True)
finally:sftp.close();client.close()

