from pathlib import Path
from time import monotonic
from resource import getrusage, RUSAGE_SELF
import json
from learning.export import load_model, verify_numerics
from learning.sequences import read_raw_shards

run = Path('/home/tongshu/acceptance/bc_v6_readiness_20261103/runs/bc_readiness/duel')
shard = run / 'data/rollout-00036-duel-g0.jsonl.gz'
start = monotonic()
model, _ = load_model(run / 'latest.pt', 'duel')
rows = read_raw_shards([shard], format_name='duel')
loaded = monotonic()
print(json.dumps(dict(shard=str(shard), rows=len(rows), turns=len(set(row['turn'] for row in rows)), full=sum(len(row['candidates'])>=37 for row in rows), load_seconds=loaded-start)), flush=True)
error = verify_numerics(model, rows)
print(json.dumps(dict(max_error=error, audit_seconds=monotonic()-loaded, max_rss_kib=getrusage(RUSAGE_SELF).ru_maxrss)), flush=True)
