"""Bounded bottom-up diagnostics on existing T5 data; no new collection."""
import collections,copy,hashlib,json,math,random,time
import numpy as np
import torch
from learning.common import ROOT,read_json,write_json
from learning.features import ACTION,ENTITY
from learning.model import Policy,batch
from learning.sequences import read_shards,training_windows
from learning.train import auxiliary_loss,train

torch.set_num_threads(1)
old=ROOT/'verification/bc_quality_ubuntu_20261023'
out=ROOT/'verification/bc_rootcause_20261023_2318';out.mkdir(parents=True,exist_ok=True)
kind=lambda c:'attack' if c['kind']=='move_attack' else c['kind']

def identity(r):return dict(game=r['game_id'],side=r['side'],turn=r['turn'],decision=r.get('decision'),choice=r['choice'])

def quality(model,rows):
 c=collections.Counter();loss=0.
 with torch.no_grad():
  for offset in range(0,len(rows),32):
   chunk=rows[offset:offset+32];scores,_=model(*batch(chunk))
   labels=torch.tensor([r['choice'] for r in chunk]);pred=scores.argmax(1).tolist()
   loss+=torch.nn.functional.cross_entropy(scores,labels,reduction='sum').item()
   for r,p in zip(chunk,pred):
    k=kind(r['candidates'][r['choice']]);c[k]+=1;c[k+'_correct']+=p==r['choice'];c['all']+=1;c['correct']+=p==r['choice']
 return dict(counts=dict(c),ce=loss/len(rows),accuracy=c['correct']/len(rows))

def digest(parts):
 h=hashlib.sha256()
 for part in parts:h.update(np.asarray(part,dtype=np.float32).tobytes())
 return h.hexdigest()

data={}
report={}
for fmt in ('ffa4','team2v2'):
 paths=sorted((old/'data'/fmt).glob('*.jsonl.gz'))
 data[fmt]={part:read_shards(paths,partition=part,limit=2048,seed=71,format_name=fmt)
            for part in ('train','validation')}
 for part,rows in data[fmt].items():
  c=collections.Counter();clipped=collections.Counter();values=collections.defaultdict(list);duplicates=0;truth_collisions=0
  for r in rows:
   t=r['candidates'][r['choice']];c[kind(t)]+=1;c['candidate_total']+=len(r['candidates'])
   c['history_turns']+=len(r['_history']);c['value_valid']+=r.get('value_valid',True)
   seen=collections.defaultdict(list)
   for j,a in enumerate(r['candidates']):
    expected=next(n for n,_ in ACTION[:5] if a['features'][[n for n,_ in ACTION].index(n)]==1)
    assert expected==a['kind'],(expected,a['kind'])
    parts=[a['features'],a['geometry'],a['local']]
    for key in ('actor','target'):
     e=a.get(key);parts.extend(([e['type_index']],e['features']) if e else ([-1],[]))
    seen[digest(parts)].append(j)
   duplicates+=sum(len(v)-1 for v in seen.values())
   truth_collisions+=any(r['choice'] in v and len(v)>1 for v in seen.values())
   for n,v in zip((n for n,_ in ACTION),t['features']):
    if n!='unit_type_index':clipped[n]+=abs(float(v))>=3.999;values[n].append(float(v))
  report[fmt+'_'+part]=dict(rows=len(rows),counts=dict(c),duplicate_candidate_inputs=duplicates,
   ambiguous_teacher_input_rows=truth_collisions,
   clipped_chosen_features={n:x for n,x in clipped.items() if x},
   chosen_feature_ranges={n:[min(v),max(v)] for n,v in values.items()},
   class_by_turn=dict(collections.Counter(str(r['turn'])+':'+kind(r['candidates'][r['choice']]) for r in rows)))

m=Policy('ffa4');m.load_state_dict(torch.load(old/'ffa4_tactical_inputs.pt',weights_only=False)['model']);m.eval()
development=[r for r in data['ffa4']['validation'] if len(r['candidates'])>1]
baseline=quality(m,development);assert baseline['counts']['move_correct']==80,baseline
report['baseline_reproduced']=baseline

# Same rows, different surrounding batch, candidate order and entity order.
chosen=random.Random(23).sample(development,8);invariance=[]
for r in chosen:
 with torch.no_grad():single,_=m(*batch([r]));mixed,_=m(*batch([r]+chosen))
 perm=list(reversed(range(len(r['candidates']))));rr=dict(r,candidates=[r['candidates'][i] for i in perm])
 with torch.no_grad():reordered,_=m(*batch([rr]))
 inverse=torch.argsort(torch.tensor(perm));delta_candidate=(single[0]-reordered[0,inverse]).abs().max().item()
 rr=dict(r,spatial=dict(r['spatial'],entities=list(reversed(r['spatial']['entities']))))
 with torch.no_grad():entities,_=m(*batch([rr]))
 m.train();with_grad,_=m(*batch([r]));m.eval()
 invariance.append(dict(row=identity(r),batch_delta=(single[0]-mixed[0,:single.shape[1]]).abs().max().item(),
   candidate_permutation_delta=delta_candidate,entity_permutation_delta=(single-entities).abs().max().item(),
   grad_mode_delta=(single-with_grad.detach()).abs().max().item()))
report['invariance']=invariance
write_json(out/'bottom_up.json',report)
print('BOTTOM_UP',json.dumps({k:v for k,v in report.items() if k=='baseline_reproduced' or k=='invariance' or k.endswith('_train')}),flush=True)

# Freeze exactly 16 rows per collapsed class, preserving each complete prefix.
rng=random.Random(23);buckets=collections.defaultdict(list)
for r in data['ffa4']['train']:
 if len(r['candidates'])>1:buckets[kind(r['candidates'][r['choice']])].append(r)
tiny=[]
for k in ('move','recruit','attack','end_turn'):
 assert len(buckets[k])>=16,(k,len(buckets[k]));tiny+=rng.sample(buckets[k],16)
tiny.sort(key=lambda r:(r['game_id'],r['side'],r['turn'],r.get('decision',0)))
write_json(out/'tiny_plan.json',dict(seed=23,rows=[identity(r) for r in tiny],classes={k:16 for k in buckets},
 optimizer_updates=120,learning_rate=3e-4,clip=.5,objective='production exact CE + .1 auxiliary; value validity counted separately'))

for arm in ('full_history','empty_history','production_window_sampling'):
 torch.manual_seed(99);random.seed(99);model=Policy('ffa4');optimizer=torch.optim.Adam(model.parameters(),lr=3e-4)
 initial={n:p.detach().clone() for n,p in model.named_parameters()};trace=[]
 rows=[dict(r,_history=[]) for r in tiny] if arm=='empty_history' else tiny
 start=time.monotonic()
 if arm=='production_window_sampling':
  steps=math.ceil(len(training_windows(rows))/4)
  result=train(model,optimizer,rows,'bc',epochs=120//steps,minibatch=256,deadline=time.time()+600)
  trace.append(dict(update=result['updates'],**quality(model,rows)))
 else:
  for step in range(120):
   optimizer.zero_grad();loss_value=0.
   for begin in (0,32):
    chunk=rows[begin:begin+32];scores,v=model(*batch(chunk));labels=torch.tensor([r['choice'] for r in chunk])
    loss=torch.nn.functional.cross_entropy(scores,labels)+.1*auxiliary_loss(scores,chunk)
    valid=torch.tensor([r.get('value_valid',True) for r in chunk],dtype=torch.bool)
    if valid.any():loss=loss+.5*(v[valid]-torch.tensor([r.get('reward',0) or 0 for r in chunk])[valid]).square().mean()
    (loss/2).backward();loss_value+=float(loss.detach())/2
   grad=float(torch.nn.utils.clip_grad_norm_(model.parameters(),.5));optimizer.step()
   if (step+1)%30==0:
    point=dict(update=step+1,loss=loss_value,gradient_norm_before_clip=grad,**quality(model,rows));trace.append(point)
    print('TINY',arm,json.dumps(point),flush=True)
  result=dict(updates=120)
 changes={n:float((p.detach()-initial[n]).norm()) for n,p in model.named_parameters()}
 record=dict(arm=arm,training=result,trace=trace,final=quality(model,rows),parameter_delta_norm=changes,seconds=time.monotonic()-start)
 write_json(out/(arm+'.json'),record)
 print('TINY_DONE',arm,json.dumps({k:v for k,v in record.items() if k!='parameter_delta_norm'}),flush=True)
print('DIAGNOSTIC_COMPLETE',flush=True)
