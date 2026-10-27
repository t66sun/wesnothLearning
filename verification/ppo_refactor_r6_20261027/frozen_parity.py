"""Read-only GAE parity on all 421 rows of the frozen duel v99 batch."""
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import struct
import types

from learning.data import advantages
from learning.rewards import row_transition
from learning.rowpack import unpack_line


root=Path('/home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source/runs/v5_lite30h_20261025/duel/data')
paths=[root/f'rollout-00099-duel-g{game}.jsonl.gz' for game in range(4)]
def hashes():
    return {str(path):hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
before=hashes()
records=[]
for path in paths:
    with gzip.open(path,'rt',encoding='utf-8') as stream:
        records.extend(unpack_line(line)[0] for line in stream)
assert len(records)==421
assert {row['schema'] for row in records}=={5}
baseline=Path('baseline_data.py').read_bytes()
reference=types.ModuleType('learning._r6_reference')
reference.__package__='learning'
exec(compile(baseline,'baseline_data.py','exec'),reference.__dict__)
expected=reference.advantages(records)
converted=[dict(row,schema=6,terminal_reward=row['reward']) for row in records]
groups=defaultdict(list)
for index,row in enumerate(records):groups[(row['game_id'],row['side'])].append(index)
for indices in groups.values():
    indices.sort(key=lambda index:(records[index]['turn'],records[index].get('decision',index)))
    for offset,index in enumerate(indices):
        following=records[indices[offset+1]] if offset+1<len(indices) else None
        converted[index]['reward_step']=row_transition(records[index],following)[0]
        converted[index].pop('reward')
for label,rows in [('legacy5',records),('derived6',converted)]:
    actual=advantages(rows)
    for old,new in zip(expected,actual):
        assert struct.pack(f'{len(old)}d',*old)==struct.pack(f'{len(new)}d',*new),label
assert before==hashes()
print(json.dumps(dict(rows=len(records),baseline_sha256=hashlib.sha256(baseline).hexdigest(),
    gae_float64_bit_equal=True,returns_float64_bit_equal=True,inputs_unchanged=True,
    input_sha256=before),indent=2))
