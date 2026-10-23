import collections,json,torch
from learning.common import ROOT,read_json,write_json
from learning.features import ACTION
from learning.model import Policy,batch
from learning.sequences import read_shards
out=ROOT/'verification/bc_quality_ubuntu_20261023'
torch.set_num_threads(1)
m=Policy('ffa4');m.load_state_dict(torch.load(out/'ffa4_tactical_inputs.pt',weights_only=False)['model']);m.eval()
rows=read_shards(sorted((out/'data/ffa4').glob('*.jsonl.gz')),partition='validation',limit=1024,seed=71,format_name='ffa4')
ix={n:i for i,(n,s) in enumerate(ACTION)};sc={n:s for n,s in ACTION}
c=collections.Counter();examples=[]
with torch.no_grad():
 for start in range(0,len(rows),64):
  chunk=rows[start:start+64];logits,_=m(*batch(chunk))
  for r,p in zip(chunk,logits.argmax(1).tolist()):
   t=r['candidates'][r['choice']];a=r['candidates'][p]
   if t['kind']!='move':continue
   key=a['kind'];c[key]+=1
   if a['kind'] in ('attack','move_attack'):
    c[key+'_predicted_'+str(a['features'][ix['combat_predicted']])]+=1
   if a['kind']!=t['kind'] and len(examples)<24:
    def view(x):return {k:x.get(k) for k in ('kind','x','y','tx','ty')}|{'f':{n:round(float(x['features'][ix[n]]*sc[n]),3) for n in ('move_tactical','move_gain','move_risk','move_risk_delta','move_primary','expected_enemy_damage','expected_self_damage','kill_probability','death_probability','combat_predicted','visible_threat','own_leader')}}
    examples.append({'turn':r['turn'],'side':r['side'],'truth':view(t),'chosen':view(a)})
write_json(out/'missing_input_diagnostic.json',dict(counts=dict(c),examples=examples))
print(json.dumps(dict(counts=dict(c),examples=examples[:5])),flush=True)
