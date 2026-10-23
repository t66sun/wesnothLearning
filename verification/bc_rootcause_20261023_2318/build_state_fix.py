import hashlib,json,os,pathlib,subprocess,sys
from learning.common import ROOT,write_json,sha256
out=ROOT/'verification/bc_rootcause_20261023_2318'
before={name:sha256(ROOT/name) for name in ('engine_lite/lua/host.lua','learning/adapters.py')}
for name,artifact in (('engine_lite/lua/host.lua','host_fixed_source.txt'),('learning/adapters.py','adapter_fixed_source.txt')):
 (ROOT/name).write_text((out/artifact).read_text(encoding='utf-8-sig'),encoding='utf-8')
env=dict(os.environ,VIRTUAL_ENV=str(ROOT/'.venv'))
env['PATH']=str(ROOT/'.venv/bin')+':/home/tongshu/.cargo/bin:/home/tongshu/venv/bin:'+env.get('PATH','')
result=subprocess.run(['/home/tongshu/venv/bin/maturin','develop','--release','--manifest-path','engine_lite/Cargo.toml'],cwd=ROOT,env=env)
if result.returncode:raise SystemExit(result.returncode)
import _engine_lite
binary=next(pathlib.Path(_engine_lite.__file__).parent.glob('*.so'))
write_json(out/'state_fix_identity.json',dict(before=before,after={name:sha256(ROOT/name) for name in before},
 extension=str(binary),extension_sha256=sha256(binary)))
result=subprocess.run([sys.executable,'-m','unittest','tests.v5.test_teacher_state_reuse','-v'],cwd=ROOT)
raise SystemExit(result.returncode)
