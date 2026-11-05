import json,pathlib,gzip,collections,time
root=pathlib.Path('/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041');run=root/'source/runs/formal_30h_scratch';d=run/'ffa4'
s=json.loads((d/'state.json').read_text()); groups=collections.defaultdict(lambda:[0,0]); reasons=collections.Counter(); timing=collections.Counter();start=time.monotonic()
def reason(candidates,a):
 kind=a['kind'];same=[c for c in candidates if c['kind']==kind]
 if not same:return 'kind_absent'
 if kind=='recruit':return 'slot_absent' if any(c.get('type')==a.get('type') for c in same) else 'type_absent'
 here=[c for c in same if (c.get('x'),c.get('y'))==(a.get('x'),a.get('y'))]
 if not here:return 'actor_absent'
 dest=lambda c:(c.get('tx',c.get('x')),c.get('ty',c.get('y')))
 there=[c for c in here if dest(c)==dest(a)]
 if not there:return 'destination_absent'
 if kind=='attack':return 'weapon_absent'
 if kind=='move_attack':
  enemy=lambda c:(c.get('ex',c.get('tx')),c.get('ey',c.get('ty')))
  return 'weapon_absent' if any(enemy(c)==enemy(a) for c in there) else 'enemy_absent'
 return 'mode_absent'
for i,name in enumerate(s['teacher_shards']):
 with gzip.open(name,'rb') as f:
  for line in f:
   p=json.loads(line.split(b',"b":',1)[0]+b'}') if line.startswith(b'{"v":') and b',"b":' in line else json.loads(line)
   r=p.get('m',p);ok=r.get('choice',-1)>=0;turn=r['turn'];band='1-5' if turn<=5 else '6-10' if turn<=10 else str((turn-1)//10*10+1)+'-'+str((turn-1)//10*10+10)
   k=r['actual']['kind'];kind='attack' if k=='move_attack' else k
   keys=[('all','all'),('turn',band),('horizon','1-30' if turn<=30 else '31-60'),('map',r['map']),('partition',r['split']),('kind',kind),('map_horizon',r['map']+(' 1-30' if turn<=30 else ' 31-60')),('partition_horizon',r['split']+(' 1-30' if turn<=30 else ' 31-60'))]
   for key in keys:groups[key][0]+=int(ok);groups[key][1]+=1
   if not ok:
    miss=reason(r['candidates'],r['actual']);reasons[(kind,miss)]+=1;reasons[('horizon:'+('1-30' if turn<=30 else '31-60'),miss)]+=1
   t=r.get('timing',{});timing['truncated']+=bool(t.get('truncated'));timing['candidates_37']+=len(r['candidates'])==37
 if (i+1)%200==0:print('PROGRESS',i+1,round(time.monotonic()-start,2),flush=True)
print('COUNTS',json.dumps([{ 'group':k[0], 'value':k[1], 'matched':v[0], 'total':v[1], 'coverage':v[0]/v[1]} for k,v in sorted(groups.items())]))
print('REASONS',json.dumps([{'kind':k[0],'reason':k[1],'count':v} for k,v in sorted(reasons.items())]));print('TIMING',dict(timing),'elapsed',time.monotonic()-start)
