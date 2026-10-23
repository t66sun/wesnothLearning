import pathlib,json,subprocess,hashlib
import torch
from learning.common import ROOT,read_json,write_json,sha256
out=ROOT/'verification/bc_quality_ubuntu_20261023'
identity=read_json(out/'identity.json')
assert {p:sha256(ROOT/p) for p in identity['source_hashes']}==identity['source_hashes']
identity['training_source_hashes']={p:sha256(ROOT/p) for p in (
    'learning/train.py','learning/model.py','learning/data.py','learning/sequences.py',
    'learning/rowpack.py','learning/lite_policy.py','learning/maps.py','lua/observation.lua',
    'lua/relational.lua','lua/network.lua')}
identity['helper_sha256']=sha256(out/'quality_t5.py')
identity['torch']=torch.__version__
active=subprocess.run(['pgrep','-af',r'python.*learning.*run|wesnoth.*--nogui'],capture_output=True,text=True)
assert active.returncode==1,active.stdout
identity['active_training_after']=active.stdout
write_json(out/'identity.json',identity)
summary=read_json(out/'summary.json')
for fmt,report in summary['formats'].items():
    assert report['arms']['zeroed_inputs']['training']['updates']==report['arms']['tactical_inputs']['training']['updates']==120
    assert report['arms']['zeroed_inputs']['sampling_decision_count_trace_sha256']==report['arms']['tactical_inputs']['sampling_decision_count_trace_sha256']
    print('FINAL_METRICS',json.dumps(dict(format=fmt,status=report['acceptance']['status'],coverage=report['coverage'],
        arms={a:r['quality']['formats'][fmt] for a,r in report['arms'].items()})),flush=True)
print('EVIDENCE_COMPLETE',summary['status'],flush=True)
