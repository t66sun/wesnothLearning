"""Match tested behavior across the independent, pre-layout publication tree."""
import ast
import hashlib
import json
from pathlib import Path

tested=Path.cwd()
published=Path('C:/Users/Toshu/.codex/worktrees/publish-collector-memory/WesnothLearning')
targets={
 'learning/data.py':['write_shard'],
 'learning/lite_host.py':['play_lite_job'],
 'learning/lite_policy.py':['FrozenPolicies'],
 'learning/reward_metrics.py':['_field'],
 'learning/rowpack.py':['compact_row'],
 'learning/sequences.py':['IndexedSequenceStore.write'],
 'learning/trajectory_buffer.py':['_metric_view','TrajectoryBuffer'],
}


def symbol(path,name):
    node=ast.parse(path.read_text(encoding='utf-8-sig'))
    for part in name.split('.'):
        node=next(item for item in node.body if getattr(item,'name',None)==part)
    return ast.dump(node,include_attributes=False)


result={}
for relative,names in targets.items():
    for name in names:
        left=symbol(tested/relative,name);right=symbol(published/relative,name)
        assert left==right,(relative,name)
        result[relative+':'+name]=hashlib.sha256(left.encode()).hexdigest()
print(json.dumps(result,indent=2))
