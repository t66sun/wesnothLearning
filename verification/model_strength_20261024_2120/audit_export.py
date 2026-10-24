import json
import hashlib
from pathlib import Path
import torch
from learning.export import load_model, verify_numerics, export
from learning.sequences import read_raw_shards, sequence_key

torch.set_num_threads(1)
root=Path(__file__).resolve().parent
destination=Path('delivery/lite_final_20261024')
models={};versions={};evidence={}
for fmt in ('duel','ffa4','team2v2'):
    checkpoint=root/(fmt+'_selected.pt')
    model,state=load_model(checkpoint,fmt);models[fmt]=model
    rows=read_raw_shards([root/(fmt+'_audit.jsonl.gz')],format_name=fmt)
    first=sequence_key(rows[0]);rows=[r for r in rows if sequence_key(r)==first]
    prefix=[]
    for row in rows:
        prefix.append(row)
        if len({r['turn'] for r in prefix})>=2 and any(len(r['candidates'])==128 for r in prefix):break
    error=verify_numerics(model,prefix)
    versions[fmt]=dict(version=state['runner']['version'],checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest())
    evidence[fmt]=dict(rows=len(prefix),turns=sorted({r['turn'] for r in prefix}),full_candidates=any(len(r['candidates'])==128 for r in prefix),python_lua_max_error=error)
    print('AUDIT',fmt,evidence[fmt],flush=True)
# Local installation uses the existing support export; the SDK submission cap
# belongs to competition archives, not this explicitly requested local add-on.
addon=export(models,destination,name='NeuralArena20261024',version=versions,package=False,
             evaluation={f:'lite final: not_passed; native strength not evaluated' for f in models})
manifest=dict(checkpoints=versions,audits=evidence,addon=str(addon.resolve()),scope='local installation, not SDK submission',evaluation_status='not_passed')
(destination/'installation_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('EXPORTED',addon,flush=True)
