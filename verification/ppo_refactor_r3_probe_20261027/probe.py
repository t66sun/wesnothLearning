"""Repeat the rejected step with exactly the frozen inputs required by R3."""
import json
import random

import torch

from learning import ppo
from learning.data import split
from learning.updates import setup, rollout_identity
from tests.v5 import helpers
from tests.v5.test_ppo_plan import _bc, _records


families = [f'probe-{i}' for i in range(30) if split(f'probe-{i}') == 'train'][:5]
records = _records([(family, 1, 0.) for family in families])
model = helpers.model(seed=41)
optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
_, windows, per_step, _, steps = setup(model, records, 2)
assert steps == 2
order = ppo._epoch_order(5, 0, len(windows))
for index in order[per_step:]:
    for row in windows[index]:
        row['log_probability'] -= 1.
identity = rollout_identity(records)
random.seed(13)
torch.manual_seed(0)
progress = None
results = []
for call in range(3):
    result = ppo.update(model, optimizer, records, bc_records=_bc(), epochs=1,
                        minibatch=2, progress=progress, plan_seed=5)
    assert result['exit'] == 'kl_stop'
    assert result['updates'] == 1
    assert result['cursor']['step'] == 1
    assert rollout_identity(records) == identity
    if call:
        assert result['policy_sha256_before'] == result['policy_sha256_after']
        assert result['approx_kl'] == results[0]['approx_kl']
    results.append({key: result[key] for key in (
        'updates', 'exit', 'approx_kl', 'committed_decisions',
        'policy_sha256_before', 'policy_sha256_after')})
    progress = result['cursor']
print(json.dumps(dict(source='f0646246887d805adc88897082a3a4e6e34a02e0',
                     threshold=ppo.KL_LIMIT, planned_steps=steps,
                     identity=identity, calls=results), indent=2))
