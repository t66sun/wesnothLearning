import json,math,sqlite3,statistics,time
from pathlib import Path
run=Path.cwd()/'runs/v5_lite_resume_20261024_1420'
print('TIME',time.strftime('%Y-%m-%d %H:%M:%S %Z'))
for fmt,restored in [('duel',212),('ffa4',88),('team2v2',50)]:
 state=json.loads((run/fmt/'state.json').read_text());h=[r for r in state['history'][restored:] if r['method']=='ppo']
 db=run/fmt/'data/sequences/sequences.sqlite3'
 with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True,timeout=.5) as connection:
  rows=connection.execute("SELECT game_id,partition,decisions,turns FROM sequences WHERE source='policy' AND game_id LIKE 'rollout-%'").fetchall()
 by_batch={}
 for game,part,decisions,turns in rows:
  batch=int(game.split('-')[1]);bucket=by_batch.setdefault(batch,dict(games=0,train_games=0,train_rows=0,windows=0))
  bucket['games']+=1
  if part=='train':bucket['train_games']+=1;bucket['train_rows']+=decisions;bucket['windows']+=math.ceil(turns/8)
 details=[]
 for row in h:
  info=by_batch.get(row['batch'])
  if not info:continue
  planned=state['clock'] and 4*max(1,math.ceil(info['windows']/4))
  details.append(dict(batch=row['batch'],actual_steps=row['updates'],planned_steps_from_turn_counts=planned,kl_stopped=row.get('kl_stopped'),**info))
 print('PPO_UTILIZATION',fmt,json.dumps(dict(version=state['version'],batches=len(details),actual_steps=sum(r['actual_steps'] for r in details),planned_steps=sum(r['planned_steps_from_turn_counts'] for r in details),train_games=sum(r['train_games'] for r in details),train_rows=sum(r['train_rows'] for r in details),tail=details[-4:])))
 # Aggregate already-recorded behavior only; do not load trajectories or models.
 logs=[json.loads(s) for s in (run/fmt/'jobs.jsonl').read_text().splitlines()]
 diagnostics=[]
 for row in logs:
  if row['id'].startswith('rollout-') and int(row['id'].split('-')[1])>=restored and row['status']=='complete':diagnostics.extend(d for d in row.get('reward_diagnostics',[]) if d.get('complete'))
 fields=['coverage5','coverage10','control','leader_survival','loss']
 agg={key:statistics.mean(d[key] for d in diagnostics if d.get(key) is not None) for key in fields if any(d.get(key) is not None for d in diagnostics)}
 print('RECENT_ROLLOUT_BEHAVIOR',fmt,len(diagnostics),json.dumps(agg))
