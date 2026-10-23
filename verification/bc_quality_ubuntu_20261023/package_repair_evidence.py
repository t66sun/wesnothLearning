"""Preserve rejected trials separately from the original frozen T5 evidence."""
import hashlib,json,shutil,subprocess
from learning.common import ROOT,read_json,write_json,sha256
old=ROOT/'verification/bc_quality_ubuntu_20261023'
source=ROOT/'verification/bc_quality_fix_20261023'
dest=old/'repair_trials';dest.mkdir(exist_ok=True)
names=('holdout_plan.json','development_result.json','pool_development_result.json','rank_development_result.json')
for name in names:
 assert (source/name).is_file(),name
 shutil.copyfile(source/name,dest/name)
identity=read_json(old/'identity.json')
for key in ('source_hashes','training_source_hashes'):
 for name,digest in identity[key].items():assert sha256(ROOT/name)==digest,name
write_json(dest/'artifacts.json',dict(
 stage=str(ROOT),production_sources_unchanged=True,
 checkpoints={p.name:dict(path=str(p),sha256=sha256(p),bytes=p.stat().st_size)
              for p in sorted(source.glob('*.pt'))},
 data={str(p.relative_to(ROOT)):dict(sha256=sha256(p),bytes=p.stat().st_size)
       for p in sorted((old/'data').glob('*/*.jsonl.gz'))},
 fresh_holdout_collected=any(source.glob('data/**/*.jsonl.gz')),
 active_training_commands=[line for line in subprocess.check_output(['ps','-eo','pid,ppid,args'],text=True).splitlines()
                           if '-m learning run' in line]))
print('REPAIR_EVIDENCE_PACKAGED',json.dumps(dict(files=list(names),production_sources_unchanged=True,
 fresh_holdout_collected=any(source.glob('data/**/*.jsonl.gz')))),flush=True)
