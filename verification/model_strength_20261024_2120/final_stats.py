import json
from pathlib import Path
from collections import Counter,defaultdict

run=Path('runs/v5_lite_windowfix_20261024_1630')
for fmt in ('duel','ffa4','team2v2'):
    base=run/fmt;by_context=defaultdict(Counter);by_faction=defaultdict(Counter)
    plans=json.loads((base/'schedules/final.json').read_text());lookup={j['id']:j for j in plans}
    for line in (base/'jobs.jsonl').open():
        row=json.loads(line)
        if row['id'] not in lookup:continue
        meta=lookup[row['id']]['meta'];res=row['result'];sides=set(meta['policy_sides'])
        c=by_context[meta['context']];c['games']+=1;c['truncated']+=bool(res['truncated'])
        if fmt!='ffa4':
            won=(res.get('winner') in sides) if fmt=='duel' else bool(res.get('winning_team') and res['teams'][min(sides)-1]==res['winning_team'])
            c['wins']+=won;c['draws']+=not bool(res.get('winning_team',res.get('winner')))
        for a in row.get('behavior',[]):
            if a['side'] not in sides:continue
            v=by_faction[res['factions'][a['side']-1]];v['actions']+=1;v['repeated_move']+=bool(a.get('repeated_move'))
            v['end_turn']+=bool(a.get('end_turn'));v['usable_end']+=bool(a.get('end_turn') and a.get('usable_moves',0)>0)
            c['end_turn']+=bool(a.get('end_turn'));c['usable_end']+=bool(a.get('end_turn') and a.get('usable_moves',0)>0)
            c['repeated_move']+=bool(a.get('repeated_move'));c['actions']+=1
    print('FINALSTATS',fmt,json.dumps({k:dict(v) for k,v in by_context.items()}))
    print('FACTIONSTATS',fmt,json.dumps({k:dict(v) for k,v in by_faction.items()}))
    state=json.loads((base/'state.json').read_text());controller=state['reward_controller']
    print('REWARD',fmt,controller['config'],'windows',len(controller['windows']),'pending',len(controller['blocks']))
