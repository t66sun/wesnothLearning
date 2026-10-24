import json
import statistics
import hashlib
from pathlib import Path
from collections import Counter, defaultdict

run=Path('runs/v5_lite_windowfix_20261024_1630')
for fmt in ('duel','ffa4','team2v2'):
    base=run/fmt; state=json.loads((base/'state.json').read_text())
    print('STATE',fmt,{k:state.get(k) for k in ('stage','phase','version','effective','best_kind','best_key','counters','pending_train','error')})
    ppo=[r for r in state['history'] if r['method']=='ppo']; fresh=[r for r in ppo if r['elapsed_hours']>15.93]
    print('UPDATES',fmt,'all',len(ppo),'fresh',len(fresh),'steps',sum(r['updates'] for r in fresh),'zero',sum(r['updates']==0 for r in fresh),'kl_stop',sum(r.get('kl_stopped',False) for r in fresh),'median',statistics.median(r['updates'] for r in fresh))
    print('READS',fmt,{k:statistics.median(r['reads']['bc'][k] for r in fresh) for k in ('rows','families','selected')})
    print('MODEL',fmt,'selected',hashlib.sha256((base/'selected.pt').read_bytes()).hexdigest())
    print('PROMOTIONS',fmt)
    for p in sorted((base/'validation').glob('*.json')):
        if p.name.startswith('control'):continue
        x=json.loads(p.read_text());c=x.get('comparison',x).get(fmt,{})
        print(p.name,{k:c.get(k) for k in ('status','difference','interval95','blocks')})
    jobs=[];sources=Counter(); examples={}
    finals=[]
    with (base/'jobs.jsonl').open() as f:
        for line in f:
            r=json.loads(line);sources[r.get('meta',{}).get('phase')]+=1
            if r['id'].startswith('final-'):finals.append(r)
            if 'rollout' in r['id']:examples['rollout']=r
            if r.get('trajectory'): examples['trajectory']=r
    print('SOURCES',fmt,sources)
    print('JOBEXAMPLE',fmt,json.dumps(examples)[:6500])
    print('FINALEXAMPLE',fmt,json.dumps(finals[0])[:10000] if finals else 'NONE')
    print('FINAL',fmt,'count',len(finals),'statuses',Counter(r.get('status') for r in finals))
    if finals:
        print('RESULTKEYS',fmt,list(finals[0].get('result',{})))
    print('DATAFILES',fmt,[(p.name,p.stat().st_size) for p in sorted((base/'data').glob('*'))[-8:]])
