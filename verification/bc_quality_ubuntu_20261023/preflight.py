import pathlib,json,subprocess,hashlib
from learning.common import ROOT
from learning.features import schema
import _engine_lite
out=ROOT/'verification/bc_quality_ubuntu_20261023';out.mkdir(parents=True,exist_ok=True)
expected=json.loads((ROOT/'verification/training_repair_20261023/final_identity.json').read_text())
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
actual={p:sha(ROOT/p) for p in expected['source_hashes']}
assert actual==expected['source_hashes'],'accepted source changed'
active=subprocess.run(['pgrep','-af',r'python.*learning.*run|wesnoth.*--nogui'],capture_output=True,text=True)
assert active.returncode==1,active.stdout
binary=next(pathlib.Path(_engine_lite.__file__).parent.glob('*.so'))
assert sha(binary)==expected['extension_sha256'],'accepted extension changed'
identity=dict(root=str(ROOT),features_version=schema()['version'],rules_sha256=schema()['rules_sha256'],
 source_hashes=actual,extension=str(binary),extension_sha256=sha(binary),
 teacher_sha256=sha(ROOT/'opponents/gpt6astra.zip'),active_training=active.stdout)
(out/'identity.json').write_text(json.dumps(identity,indent=2))
print('PREFLIGHT_PASS',json.dumps({k:v for k,v in identity.items() if k!='source_hashes'}),flush=True)
