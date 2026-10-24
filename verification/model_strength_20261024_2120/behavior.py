import json
import statistics
from pathlib import Path
from collections import Counter,defaultdict

run=Path('runs/v5_lite_windowfix_20261024_1630')
for fmt in ('duel','ffa4','team2v2'):
    base=run/fmt;state=json.loads((base/'state.json').read_text())
    agg={k:Counter() for k in ('policy','astra')};games=Counter();horizons=defaultdict(list);examples={};roll=None
    for line in (base/'jobs.jsonl').open():
        r=json.loads(line)
        if r['id'].startswith('rollout-') and r.get('training_eligible') and r.get('training_shard'):roll=r
        if not r['id'].startswith('final-'):continue
        result=r['result'];games[result['reason']]+=1;games['truncated']+=bool(result.get('truncated'))
        bots=result['bots'];sides={i+1 for i,b in enumerate(bots) if 'FinalSelected' in b}
        for a in r.get('behavior',[]):
            who='policy' if a['side'] in sides else 'astra';c=agg[who];c['decisions']+=1;c['end_turn']+=bool(a.get('end_turn'));c['repeat']+=bool(a.get('repeated_move'))
            c['recruits']+=bool(a.get('recruit_type'));c['village_capture']+=bool(a.get('village_captured'))
            c['usable_end']+=bool(a.get('end_turn') and a.get('usable_moves',0)>0)
            c['end_usable_sum']+=a.get('usable_moves',0) if a.get('end_turn') else 0
            examples.setdefault('action_keys',set()).update(a)
        for side in range(1,len(bots)+1):
            who='policy' if side in sides else 'astra';agg[who]['side_games']+=1
    print('BEHAVIOR',fmt,'games',dict(games),'metrics',{k:dict(v) for k,v in agg.items()},'action_keys',sorted(examples.get('action_keys',set())))
    for p in sorted((base/'validation').glob('control-*.json'))[-2:]:
        x=json.loads(p.read_text())
        print('METRIC',fmt,p.name,json.dumps(x)[:4500])
    path=Path(state['teacher_shards'][0]);print('AUDITSHARD',fmt,str(path),path.stat().st_size)
    print('ROLLOUT',fmt,{k:roll.get(k) for k in ('id','meta','shard')} if roll else None)
    if roll: print('ROLLOUTFILES',fmt,[(p.name,p.stat().st_size) for p in (base/'data').glob(roll['id']+'*')])
