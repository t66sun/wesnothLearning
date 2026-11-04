"""Compare full rollout-content-v2 identities on a fixed slice of the retained team PPO shard."""
import gzip
import hashlib
import importlib.util
import json
import statistics
import time
from pathlib import Path

from learning.rowpack import compact_row, plain_row, unpack_line
from learning.sequences import attach_histories
from learning.updates import rollout_identity

shard = Path('/home/tongshu/acceptance/bounded_loop_v6_strict_20261104/runs/bounded_loop/team2v2/data/rollout-00002-team2v2-g0.jsonl.gz')
raw = []
eligible = 0
with gzip.open(shard, 'rt') as stream:
    for line in stream:
        row, _ = unpack_line(line)
        if row.get('faults'):
            continue
        raw.append(row)
        eligible += row['split'] == 'train' and row.get('choice', -1) >= 0
        if eligible == 32:
            break
assert eligible == 32
def targets(raw):
    return [r for r in attach_histories(raw) if r['split'] == 'train' and r.get('choice', -1) >= 0]

# Load the unchanged function from the shipped baseline in the same package context.
reference = Path('/home/tongshu/acceptance/rollout_hash_red_20261104/learning/updates.py')
spec = importlib.util.spec_from_file_location('learning.reference_updates', reference)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
original, proposed = module.rollout_identity, rollout_identity

rows = targets(raw)
times = {f: [] for f in ('original', 'proposed')}
identities = {}
for label in ('original', 'proposed', 'proposed', 'original'):
    routine = original if label == 'original' else proposed
    start = time.perf_counter()
    identities[label] = routine(rows)
    times[label].append(time.perf_counter() - start)
assert identities['original'] == identities['proposed']

encoder = json.JSONEncoder(sort_keys=True, separators=(',', ':'), allow_nan=False,
                           default=lambda value: value.tolist())
def check_bytes(payload):
    obj = compact_row(payload)
    old = ''.join(encoder.iterencode(obj)).encode()
    new = encoder.encode(obj).encode()
    assert old == new
    return hashlib.sha256(old).hexdigest(), len(old)

def form_check(records):
    prefixes = {}
    max_bytes = 0
    for row in records:
        for slot in row['_history']:
            if id(slot) not in prefixes:
                prefixes[id(slot)], size = check_bytes(slot)
                max_bytes = max(max_bytes, size)
        record = {k:v for k,v in row.items() if k not in ('_history', '_sequence_complete')}
        record['_history'] = [prefixes[id(slot)] for slot in row['_history']]
        _, size = check_bytes(record)
        max_bytes = max(max_bytes, size)
    old, new = original(records), proposed(records)
    assert old == new
    return dict(rows=len(records), prefix_payloads=len(prefixes), maximum_payload_bytes=max_bytes, identity=old)

legacy = [dict(schema=5, format='team2v2', source='policy', engine_id='lite', game_family='legacy',
               game_id='legacy', side=1, turn=t, decision=0, choice=0, split='train',
               candidates=[dict(features=[-0.0, 1, 0.125])], **{'global':[1e-12, t, 2.0]},
               opponents=[], spatial=dict(entities=[], board=[]), note='\u00e9 \u96ea', optional=None)
          for t in (1, 2)]
legacy_raw = [unpack_line(json.dumps(r, ensure_ascii=False))[0] for r in legacy]
forms = dict(packed=form_check(rows), lists=form_check(targets(plain_row(raw))), legacy_json=form_check(targets(legacy_raw)))
assert forms['packed']['identity'] == forms['lists']['identity']
with shard.open('rb') as file:
    source_hash = hashlib.file_digest(file, 'sha256').hexdigest()
means = {label:statistics.mean(seconds) for label,seconds in times.items()}
print(json.dumps(dict(shard=str(shard), shard_sha256=source_hash, first=[rows[0]['turn'],rows[0].get('decision')],
                      last=[rows[-1]['turn'],rows[-1].get('decision')], trials_seconds=times, means_seconds=means,
                      saved_seconds_per_row=(means['original']-means['proposed'])/len(rows), forms=forms), indent=2))
