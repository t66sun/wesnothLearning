"""Apply the locally checked second repair to this task's validation sources."""
import getpass
import hashlib
import json
from pathlib import Path
import zipfile
import paramiko

root=Path.cwd();out=Path(__file__).resolve().parent
stage='/home/tongshu/myDev/wesnothLearning/validation_memory_repair_20261024_1321'
relative=out.relative_to(root).as_posix()
original=out/'pressure.ubuntu.txt'
baseline=next(json.loads(line[5:]) for line in original.read_text().splitlines() if line.startswith('DONE '))
assert baseline['rows']==1621
reference=dict(source='pressure.ubuntu.txt',source_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),result=baseline)
(out/'baseline_reference.json').write_text(json.dumps(reference,indent=2))
files=['learning/data.py','learning/lite_host.py','learning/sequences.py','learning/trajectory_buffer.py',
       'learning/reward_metrics.py','tests/v5/test_collection_memory.py',relative+'/stress_probe_v2.py',relative+'/baseline_reference.json']
identity={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in files}
with zipfile.ZipFile(out/'source_v2.zip','w',zipfile.ZIP_DEFLATED) as z:
 for name in files:z.write(root/name,name)
client=paramiko.SSHClient();client.load_system_host_keys();client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect('192.168.122.118',username='tongshu',password=getpass.getpass('SSH password: '),look_for_keys=False,allow_agent=False,timeout=10)
try:
 with client.open_sftp() as sftp:
  for name in files:sftp.put(str(root/name),stage+'/'+name)
 (out/'source_v2_identity.json').write_text(json.dumps(identity,indent=2))
 print('UPGRADED_VALIDATION_ONLY',stage)
 print('SOURCE_SHA256',json.dumps(identity))
finally:client.close()
