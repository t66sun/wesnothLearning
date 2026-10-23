"""One-off Ubuntu maintenance: verify archives before removing old run trees."""
import datetime,hashlib,json,os,pathlib,shutil,subprocess,time

PROJECT=pathlib.Path('/home/tongshu/myDev/wesnothLearning/WesnothLearning').resolve(strict=True)
BASE=PROJECT.parent
KEEP=('v5_lite20h_20261022_210712','v5_lite6000_replay_20261022_012336')
ARCHIVE=BASE/'training_archives'/datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y%m%d_%H%M%S')
SOURCES=[
 ('v5_20261021_203930','runs/v5_20261021_203930'),
 ('v5_20261022_000850','runs/v5_20261022_000850'),
 ('v5_lite6000_replay_20261022_011309','runs/v5_lite6000_replay_20261022_011309'),
 ('loopback_20261021_232345','runs/loopback_20261021_232345'),
 ('bc_v4_cpu_72h_20261019','releases/bc_v4_20261018/runs/bc_v4_cpu_72h_20261019'),
 ('bc_v4_cpu_72h_w8_20261019','releases/bc_v4_20261018/runs/bc_v4_cpu_72h_w8_20261019'),
]

def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as stream:
  for block in iter(lambda:stream.read(4*1024*1024),b''):h.update(block)
 return h.hexdigest()

def run(*args):
 r=subprocess.run(args,capture_output=True,text=True)
 if r.returncode:raise RuntimeError(dict(command=args,code=r.returncode,stdout=r.stdout,stderr=r.stderr))
 return r.stdout

def critical():
 files=[]
 for name in KEEP:
  root=PROJECT/'runs'/name
  files.extend(p for p in (root/'manifest.json',root/'clock.json',root/'summary.json') if p.is_file())
  for fmt in ('duel','ffa4','team2v2'):
   for pattern in ('*.pt','state.json','bc_gate.json'):
    files.extend((root/fmt).glob(pattern))
 return {str(p.relative_to(PROJECT)):sha(p) for p in sorted(set(files)) if p.is_file()}

def inactive():
 # No process may have a cwd, command or open file inside a source selected for removal.
 blockers=[]
 for proc in pathlib.Path('/proc').iterdir():
  if not proc.name.isdigit() or int(proc.name)==os.getpid():continue
  try:
   cmd=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
   cwd=str((proc/'cwd').resolve())
   if any(str(PROJECT/rel) in cmd or cwd==str(PROJECT/rel) or cwd.startswith(str(PROJECT/rel)+'/') for _,rel in SOURCES):
    blockers.append(dict(pid=proc.name,cwd=cwd,command=cmd));continue
   for fd in (proc/'fd').iterdir():
    try:target=os.readlink(fd)
    except OSError:continue
    if any(target==str(PROJECT/rel) or target.startswith(str(PROJECT/rel)+'/') for _,rel in SOURCES):
     blockers.append(dict(pid=proc.name,file=target));break
  except (FileNotFoundError,PermissionError,ProcessLookupError):continue
 if blockers:raise RuntimeError(dict(active_source_users=blockers))
 active=subprocess.run(['pgrep','-af',r'python.*learning.*run|wesnoth.*--nogui'],capture_output=True,text=True)
 if active.returncode==0:raise RuntimeError(dict(active_training=active.stdout))

# Select by frozen start clock, never by a directory changed during a later probe.
runs=[]
for parent in (PROJECT/'runs',PROJECT/'releases/bc_v4_20261018/runs'):
 for root in parent.iterdir():
  if (root/'manifest.json').is_file() and (root/'clock.json').is_file():
   runs.append((json.loads((root/'clock.json').read_text())['started'],root.name))
assert tuple(n for _,n in sorted(runs,reverse=True)[:2])==KEEP,runs
inactive()
before=critical();free_before=shutil.disk_usage(PROJECT).free
ARCHIVE.mkdir(parents=True,exist_ok=False)
state=dict(created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),project=str(PROJECT),archive_dir=str(ARCHIVE),
 retained=list(KEEP),retained_critical_sha256=before,free_bytes_before=free_before,archives=[],status='archiving')
def save():
 tmp=ARCHIVE/'index.json.tmp';tmp.write_text(json.dumps(state,ensure_ascii=False,indent=2));tmp.replace(ARCHIVE/'index.json')
save()
for name,rel in SOURCES:
 root=PROJECT/rel
 # Exact named tree, inside the intended runs parent; never follow a root symlink.
 assert not root.is_symlink() and root.resolve(strict=True)==root
 assert root.parent in (PROJECT/'runs',PROJECT/'releases/bc_v4_20261018/runs')
 assert root.name not in KEEP and root.is_dir()
 members=[rel]
 log=PROJECT/'runs/logs'/f'{name}.log'
 if log.is_file():members.append(str(log.relative_to(PROJECT)))
 ops=PROJECT/'releases/bc_v4_20261018/.ops'
 if name.startswith('bc_v4_'):
  members.extend(str(p.relative_to(PROJECT)) for p in sorted(ops.glob(name+'.*')) if p.is_file())
 archive=ARCHIVE/(name+'.tar.zst');temporary=archive.with_suffix('.zst.partial')
 allocated=int(run('du','-B1','-s','--',str(root)).split()[0])
 print('ARCHIVE_START',name,'allocated_bytes',allocated,'members',members,flush=True)
 started=time.time()
 run('tar','--sparse','-I','zstd -T2 -3','-cf',str(temporary),'-C',str(PROJECT),'--',*members)
 # GNU tar compares every archived file's content and metadata to the source.
 run('tar','--zstd','--compare','--file',str(temporary),'--directory',str(PROJECT))
 digest=sha(temporary);temporary.replace(archive)
 entry=dict(name=name,members=members,archive=str(archive),sha256=digest,bytes=archive.stat().st_size,
    source_allocated_bytes=allocated,tar_compare_exit=0,source_removed=False,seconds=round(time.time()-started,2))
 state['archives'].append(entry);save()
 inactive()
 assert critical()==before,'retained run changed; do not remove old source'
 for member in members:
  target=PROJECT/member
  assert not target.is_symlink() and target.resolve(strict=True)==target
  assert target==root or target.parent in (PROJECT/'runs/logs',ops)
  assert ARCHIVE.is_dir() and archive.is_file() and entry['tar_compare_exit']==0
  if target.is_dir():shutil.rmtree(target)
  else:target.unlink()
 entry['source_removed']=True;save()
 print('ARCHIVE_DONE',json.dumps(entry),flush=True)

remaining=[p.name for p in (PROJECT/'runs').iterdir() if p.is_dir() and (p/'manifest.json').is_file()]
assert set(remaining)==set(KEEP),remaining
assert not list((PROJECT/'releases/bc_v4_20261018/runs').iterdir())
assert set(p.name for p in (PROJECT/'runs/logs').iterdir())=={n+'.log' for n in KEEP}
assert critical()==before
inactive()
state.update(status='complete',free_bytes_after=shutil.disk_usage(PROJECT).free,retained_unchanged=True,
 net_free_bytes=shutil.disk_usage(PROJECT).free-free_before,remaining_main_runs=remaining)
save()
(ARCHIVE/'SHA256SUMS').write_text(''.join(a['sha256']+'  '+pathlib.Path(a['archive']).name+'\n' for a in state['archives']))
(ARCHIVE/'README.md').write_text('# Training archive — 2026-10-23\n\nOriginal run dates, configuration, frozen source, data, weights and file timestamps are retained inside each archive. index.json records exact source paths and SHA-256 values.\n\nVerify: `sha256sum -c SHA256SUMS`\n\nRestore one archive from its original project root (do not overwrite a newer run):\n\n`tar --zstd -xf /absolute/path/to/NAME.tar.zst -C '+str(PROJECT)+'`\n')
print('ARCHIVE_RESULT',json.dumps(state,ensure_ascii=False),flush=True)
