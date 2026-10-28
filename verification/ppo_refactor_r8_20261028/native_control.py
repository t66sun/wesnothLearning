"""Final bounded control: repeat the uninstrumented duel once, no retries."""
from pathlib import Path
import json
import sys
import time
from learning.common import write_json
from learning.sample import play_job

parent=Path(sys.argv[1]); output=Path(sys.argv[2]); output.mkdir()
job=dict(id='baseline_repeat',output=str(output/'baseline_repeat.json'),
         bots=['baseline','baseline'],seed=20261028,factions=['Loyalists','Rebels'],
         max_turns=5,timeout=30,first_timeout=30,engine='native',wesnoth=sys.argv[3],
         deadline=time.time()+300,learning=dict(support=str(parent/'support'),sides={}))
result=play_job(job)
assert result['status']=='complete' and not result['result']['faults'],result
write_json(output/'summary.json',result)
before=json.loads((parent/'capture_off.json').read_text())['frames']
after=json.loads((output/'baseline_repeat.json').read_text())['frames']
comparison=dict(same_seed=20261028,baseline_snapshots_equal=before==after,
                snapshots_before=len(before),snapshots_after=len(after),
                conclusion='measurement only; does not waive FX1 noninterference gate',
                total_authorised_games_used=3,max_turns=5)
write_json(output/'comparison.json',comparison)
print(json.dumps(comparison,indent=2))
