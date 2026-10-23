"""Read-only error localization on the fixed final FF4 checkpoint; no updates."""
import collections,json
import torch
from learning.common import ROOT,read_json,write_json
from learning.features import schema
from learning.model import Policy,batch
from learning.sequences import read_shards

torch.set_num_threads(1)
out=ROOT/'verification/bc_quality_ubuntu_20261023'
checkpoint=torch.load(out/'ffa4_tactical_inputs.pt',map_location='cpu',weights_only=False)
assert checkpoint['features']==schema() and checkpoint['format']=='ffa4'
model=Policy('ffa4');model.load_state_dict(checkpoint['model']);model.eval()
paths=sorted((out/'data/ffa4').glob('*.jsonl.gz'))
kind=lambda candidate:'attack' if candidate['kind']=='move_attack' else candidate['kind']
summary={}
with torch.no_grad():
 for part,limit in (('train',2048),('validation',1024)):
  rows=read_shards(paths,partition=part,limit=limit,seed=71,format_name='ffa4')
  rows=[r for r in rows if len(r['candidates'])>1]
  counts=collections.Counter();confusion=collections.Counter();movement=collections.Counter();factions={}
  ce=0.
  for offset in range(0,len(rows),64):
   chunk=rows[offset:offset+64];logits,_=model(*batch(chunk))
   target=torch.tensor([r['choice'] for r in chunk]);predicted=logits.argmax(1).tolist()
   ce+=torch.nn.functional.cross_entropy(logits,target,reduction='sum').item()
   for row,index in zip(chunk,predicted):
    truth=row['candidates'][row['choice']];selected=row['candidates'][index]
    expected,actual=kind(truth),kind(selected)
    counts[expected]+=1;counts[expected+'_correct']+=index==row['choice'];counts['all']+=1;counts['all_correct']+=index==row['choice']
    confusion[expected+' -> '+actual]+=1
    if expected=='move':
     f=factions.setdefault(row['faction'],dict(total=0,correct=0));f['total']+=1;f['correct']+=index==row['choice']
     if index==row['choice']:movement['exact']+=1
     elif actual!='move':movement['different_action_kind']+=1
     elif (truth.get('actor') or {}).get('id')!=(selected.get('actor') or {}).get('id'):movement['different_actor']+=1
     else:movement['same_actor_wrong_destination_or_variant']+=1
  summary[part]=dict(counts=dict(counts),cross_entropy=ce/max(1,len(rows)),
                    action_confusion=dict(confusion),move_error=dict(movement),move_by_faction=factions)
assert summary['validation']['counts']['move']==268 and summary['validation']['counts']['move_correct']==80
write_json(out/'ffa4_error_analysis.json',summary)
print('FIXED_FFA4_ERROR_ANALYSIS',json.dumps(summary),flush=True)
