"""Archive compact results with exact paths/hashes for the full server artifacts."""
import json,pathlib,subprocess
from learning.common import ROOT,read_json,write_json,sha256
import _engine_lite
out=ROOT/'verification/bc_rootcause_20261023_2318'
names=('bottom_up','full_history','empty_history','production_window_sampling','baseline_route','no_value_route',
 'value_detached_route','empty_history_route','extended_480','faster_lr_120','trade_diagnostic','trade_probe',
 'context_dropout_generalization','decision_draws_generalization','diversity_normal','diversity_zeroed',
 'teacher_replay','restore_real_case','state_fix_identity','diversity_plan','tiny_plan')
report={};artifacts={}
for name in names:
 p=out/(name+'.json');r=read_json(p);artifacts[p.name]=dict(path=str(p),sha256=sha256(p),bytes=p.stat().st_size)
 if isinstance(r,dict) and 'trace' in r:
  r=dict(r,trace=[v for v in r['trace'] if 'development' in v] if name=='baseline_route' else r['trace'] if name in ('extended_480','faster_lr_120') else None)
 if isinstance(r,dict):r={k:v for k,v in r.items() if k!='parameter_delta_norm'}
 report[name]=r
fresh=out/'fresh_holdout.json'
if fresh.exists():report['fresh_holdout']=read_json(fresh)
old=read_json(ROOT/'verification/bc_quality_ubuntu_20261023/identity.json')
sources=set(old['source_hashes'])|set(old['training_source_hashes'])|{'learning/adapters.py','tests/v5/test_teacher_state_reuse.py'}
binary=next(pathlib.Path(_engine_lite.__file__).parent.glob('*.so'))
manifest=dict(root=str(ROOT),source_sha256={n:sha256(ROOT/n) for n in sorted(sources)},extension_sha256=sha256(binary),
 rule_sha256=old['rules_sha256'],teacher_sha256=sha256(ROOT/'opponents/gpt6astra.zip'),artifacts=artifacts,
 data={str(p.relative_to(ROOT)):dict(sha256=sha256(p),bytes=p.stat().st_size) for p in sorted((out/'data').glob('*/*.jsonl.gz'))},
 checkpoints={p.name:dict(path=str(p),sha256=sha256(p)) for p in sorted(out.glob('*.pt'))},
 active_training_commands=[s for s in subprocess.check_output(['ps','-eo','pid,ppid,args'],text=True).splitlines() if '-m learning run' in s])
write_json(out/'RESULTS.json',report);write_json(out/'manifest.json',manifest)
print('ARCHIVED',len(report),'scopes; fresh holdout',fresh.exists(),'; formal training',manifest['active_training_commands'],flush=True)
