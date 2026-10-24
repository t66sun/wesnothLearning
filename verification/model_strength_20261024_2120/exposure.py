import json
import math
import sqlite3
import statistics
from pathlib import Path

run=Path('runs/v5_lite_windowfix_20261024_1630')
for fmt in ('duel','ffa4','team2v2'):
    base=run/fmt;state=json.loads((base/'state.json').read_text())
    index=base/'data/sequences/sequences.sqlite3'
    db=sqlite3.connect(index.resolve().as_uri()+'?mode=ro',uri=True)
    expected=actual=0;pairs=[]
    for r in state['history']:
        if r['method']!='ppo' or r['elapsed_hours']<=15.93:continue
        pattern=f"rollout-{r['batch']:05}-{fmt}-g%"
        items=db.execute("SELECT turns FROM sequences WHERE source='policy' AND partition='train' AND game_id LIKE ?",(pattern,)).fetchall()
        windows=sum(math.ceil(turns/8) for (turns,) in items)
        steps=4*math.ceil(windows/4)
        if not steps:print('NOINDEX',fmt,r['batch']);continue
        expected+=steps;actual+=r['updates'];pairs.append((r['batch'],r['updates'],steps))
    print('EXPOSURE',fmt,'batches',len(pairs),'actual',actual,'planned_estimate',expected,'fraction',actual/expected,'last',pairs[-4:])
    db.close()
