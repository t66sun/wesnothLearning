import json
from pathlib import Path
from collections import Counter
import time

run=Path('runs/v5_lite_windowfix_20261024_1630')
print('TIME',time.strftime('%F %T %z'))
for fmt in ('duel','ffa4','team2v2'):
    base=run/fmt
    state=json.loads((base/'state.json').read_text())
    print('STATE',fmt,json.dumps({k:v for k,v in state.items() if k not in ('history','reward_controller','reward_history','bc_metrics')},ensure_ascii=False)[:12000])
    history=state['history'];print('HISTORYFIELDS',fmt,[(r.get('method'),list(r)) for r in history[-2:]])
    ppo=[r for r in history if r.get('method')=='ppo']
    print('PPO',fmt,'batches',len(ppo),'last',json.dumps(ppo[-3:])[:16000])
    print('FILES',fmt,[(str(p.relative_to(base)),p.stat().st_size) for p in base.iterdir() if p.is_file()])
    print('VALIDATION',fmt,[(str(p.relative_to(base)),p.stat().st_size) for p in base.rglob('*.json') if 'validation' in str(p) or 'champion' in str(p)][-35:])
    print('CONTROLLER',fmt,json.dumps(state.get('reward_controller',{}))[:16000])
    jobs=[]
    with (base/'jobs.jsonl').open() as f:
        for line in f:
            row=json.loads(line)
            if row.get('meta',{}).get('phase')=='final':jobs.append(row)
    print('FINALJOB',fmt,json.dumps(jobs[0])[:12000] if jobs else 'NONE')
    print('FINALSTAT',fmt,len(jobs),Counter(r.get('status') for r in jobs))
print('SCHEMA',json.loads((run/'manifest.json').read_text())['config'])
