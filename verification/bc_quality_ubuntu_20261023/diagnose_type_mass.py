import collections,json,torch
from learning.common import ROOT,write_json
from learning.model import Policy,batch
from learning.sequences import read_shards
torch.set_num_threads(1)
out=ROOT/'verification/bc_quality_ubuntu_20261023'
state=torch.load(out/'ffa4_tactical_inputs.pt',map_location='cpu',weights_only=False)
model=Policy('ffa4');model.load_state_dict(state['model']);model.eval()
rows=read_shards(sorted((out/'data/ffa4').glob('*.jsonl.gz')),partition='validation',limit=1024,seed=71,format_name='ffa4')
counts=collections.Counter()
with torch.no_grad():
 for start in range(0,len(rows),64):
  chunk=rows[start:start+64];logits,_=model(*batch(chunk))
  for i,row in enumerate(chunk):
   truth=row['candidates'][row['choice']]['kind']
   if truth!='move':continue
   groups=collections.defaultdict(list)
   for j,c in enumerate(row['candidates']):groups['attack' if c['kind']=='move_attack' else c['kind']].append(j)
   scores={kind:torch.logsumexp(logits[i,ids],0).item() for kind,ids in groups.items()}
   chosen=logits[i,:len(row['candidates'])].argmax().item()
   actual=row['candidates'][chosen]['kind'];actual='attack' if actual=='move_attack' else actual
   counts['moves']+=1;counts['kind_mass_move']+=max(scores,key=scores.get)=='move'
   counts['argmax_kind_move']+=actual=='move'
   if actual!='move':counts['wrong_argmax_but_move_mass']+=max(scores,key=scores.get)=='move'
write_json(out/'type_mass_diagnostic.json',dict(counts))
print('TYPE_MASS',dict(counts),flush=True)
