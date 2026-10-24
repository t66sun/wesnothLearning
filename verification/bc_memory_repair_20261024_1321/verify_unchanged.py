import hashlib
import json
import os
from pathlib import Path
import subprocess

root=Path.cwd();old=root.parent/'validation_training_repair_20261023_194022'
run=old/'runs/v5_lite18h_20261024_003512'
expected=dict(duel='718b9bb17d078826f7c729e3c557934ec1857e373e0387df6cec766c3cf813ff',
              ffa4='7755cedaea876a201e6816bf166045802c87844c1e47c7bae1fc2e88b4e37c6a',
              team2v2='0a9638c797e3bd648561d15160d2d3b36ca59de9c6fcc5721f34a65b24d01779')
for fmt,digest in expected.items():
 actual=hashlib.sha256((run/fmt/'latest.pt').read_bytes()).hexdigest()
 assert actual==digest
 print('UNCHANGED_CHECKPOINT',fmt,actual)
manifest=json.loads((run/'manifest.json').read_text())
assert manifest['config']['workers']==8 and manifest['config']['bc_games']==dict(duel=300,ffa4=600,team2v2=400)
rules=Path(manifest['rules']['directory'])/'rules.json'
assert hashlib.sha256(rules.read_bytes()).hexdigest()==manifest['rules']['rules_sha256']=='d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca'
assert not Path('/proc/192814').exists()
remaining=[]
for path in Path('/proc').iterdir():
 if not path.name.isdigit() or int(path.name)==os.getpid():continue
 try:
  cwd=os.readlink(path/'cwd');cmd=(path/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
  if cwd in (str(root),str(old)) and 'python' in cmd:remaining.append(dict(pid=path.name,command=cmd))
 except (FileNotFoundError,PermissionError,ProcessLookupError):pass
assert not remaining,remaining
print('REMAINING_TRAINING_OR_TEST_PYTHON',remaining)
logs=subprocess.run(['journalctl','-k','--since','2026-10-24 13:20:00','--no-pager'],capture_output=True,text=True)
assert logs.returncode==0
oom=[line for line in logs.stdout.splitlines() if 'Out of memory:' in line or 'oom-kill:' in line]
assert not oom,oom
print('NEW_KERNEL_OOM',oom)
print('RULES_SHA256',manifest['rules']['rules_sha256'])
print('MANIFEST_SHA256',hashlib.sha256((run/'manifest.json').read_bytes()).hexdigest())
