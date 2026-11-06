# Frozen BC distribution rehearsal implementation checks

Implementation evidence for [#239](https://github.com/t66sun/wesnothLearning/issues/239).
The optional `frozen_bc_kl` target and historical-action baseline pass the 43
affected Ubuntu checks below. These exercise temporary synthetic policies and
state fixtures, not a training run or strength experiment. Integration with
#235's new task remains a separate combined acceptance step.

## Source and environment

- Baseline: `09d038cf6fec05ebd46cf11d1e8afbe79135098d`.
- Passing source: `0616abd60557ad5f4f0f7dad9a477fdf7ac3e378`, branch
  `codex/issue239-frozen-bc`.
- Git archive SHA-256:
  `c25f2cdd3699159f93ae9151e32d28aba4c6891e2499f06b6a327697d6fb799f`.
- Fresh Ubuntu extraction:
  `/home/tongshu/acceptance/frozen_bc_anchor_20261106_0616abd/source`.
- Python 3.12.3, Torch 2.9.1+cpu, one OMP/MKL/OpenBLAS thread.
- Compiled rules:
  `/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered`,
  `rules.json` SHA-256
  `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`.
- Existing extension:
  `/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension`.
- `data/rules/1.18.8` links to the existing maps at
  `/home/tongshu/myDev/wesnothLearning/WesnothLearning/rules/1.18.8`.
- [Exact environment](environment.txt). No Windows tests were run.

## Results

**43 checks passed in 14.269 seconds**, exit 0: [checks.log](checks.log).

The new suites cover:

- Forward `KL(stop_gradient(pi_BC) || pi_current)`, numerical zero loss/gradient
  at BC, nonzero hard-action CE, asymmetric direction, finite padding, frozen
  target and no value-head target.
- Control implementation/hash exclusion, policy/train-only admission before
  sampling, empty-pool failure and rejection of source-renamed Astra labels.
- Independent current/anchor caches and each model's own replay of all 11 raw
  history turns, including context older than the differentiable eight-turn
  window; unchanged logical-window/microbatch weighting.
- Real `FormatExperiment` construction, complete checkpoint save/load,
  endpoint file/parameter/lineage pins and unchanged manifest bytes; internal
  Lua export plus `model.pt` and the `FrozenPolicies` tensor consumer.
- First PPO entry pins before export/collection; unqualified/unfinished BC and
  forced PPO without BC fail.
- Both targets through the real runner and disk rowpack/sequence shards.
  Pending `reward_config.bc_aux=0.1` remains effective after the controller changes
  to 0.2. The targets produce different updated model hashes.
- Interruption after one optimizer step resumes to the exact uninterrupted
  model hash and counters, preserving restored Python/Torch RNG.
- Missing/replaced anchors, missing identity/lineage and changed mode/format
  fail before updates. An empty PPO boundary cannot recreate a lost pin.
- Same-task BC-parent branches start both modes from identical weights and pin
  the parent BC endpoint; BC restart does not inherit the old fixed anchor.
- Existing rehearsal-source, no-drop, PPO plan/KL stopping, pending-update
  settlement, phase-batch stopping and BC branch/ancestor evidence contracts.

The first attempt used source `40fa94475a7be1d9458263ca213c4ec362ae0cbe` in
`/home/tongshu/acceptance/frozen_bc_anchor_20261106_40fa944/source`. The same 43
checks ran in 13.838 seconds: 41 passed, one failed and one errored.
[Original log](checks_initial.log). Both defects were in new fixtures:
the directional KL example used symmetric/permuted distributions, and distinct
policy fixtures reused a sequence identity, forming an out-of-order history.
The passing commit changes only those logits and the counterexample's game ID.
Production code is identical across both attempts.

## Target-reversion assertion

The real-runner two-target test ran once with an in-process patch replacing only
the frozen KL objective by old sampled-action CE (every fixture choice is zero).
The final `assertNotEqual` failed as required: both targets produced
`143106dbf17efbdb70eab6518c404546ca4bd731906db7ca3bd11351fdc9505b`.
One test, 2.039 seconds. The wrapper required exactly that assertion failure and
no errors; production files were not modified. [target_reversion.log](target_reversion.log).

## Reproduction

The branch was committed locally, shipped with `git archive`/`scp` and extracted
into the fresh source directory identified above. From that directory:

```bash
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PWD:/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension"
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
python=/home/tongshu/venv/bin/python
"$python" -m unittest \
  tests.v5.test_frozen_bc_loss tests.v5.test_frozen_bc_anchor \
  tests.v5.test_rehearsal_source tests.v5.test_ppo_plan \
  tests.v5.test_ppo_resume_counters tests.v5.test_ppo_phase_boundary \
  tests.v5.test_branch_restart_bc tests.v5.test_branch_teacher_evidence -v
```

The target-reversion check uses the same environment:

```bash
"$python" - <<'PY'
import unittest
from unittest.mock import patch
import torch
from tests.v5.test_frozen_bc_anchor import FrozenBcAnchorTests

def historical_action(anchor, current, mask):
    choices = torch.zeros(current.shape[0], dtype=torch.long, device=current.device)
    return torch.nn.functional.cross_entropy(current, choices, reduction='none')

suite = unittest.TestSuite([FrozenBcAnchorTests(
    'test_real_runner_compares_targets_and_uses_pending_coefficient')])
with patch('learning.ppo.forward_kl', side_effect=historical_action):
    result = unittest.TextTestRunner(verbosity=2).run(suite)
assert len(result.failures) == 1 and not result.errors
assert 'assertNotEqual' in result.failures[0][1]
print('Expected target-reversion failure observed; production files were not modified.')
PY
```

| Artifact | SHA-256 |
| --- | --- |
| `checks_initial.log` | `9118d690e77b9fb28b70d5e409b404c18452b9c5c6bb72eac5aaeba15b45ba76` |
| `checks.log` | `d3254283f7f2176490a59bb8c555e1b9d313d2b79a0ba5a8b0bc9a6f2a5cab39` |
| `target_reversion.log` | `8e4eb3bc6d338fb1a481a283ced3528048cb36e06ce95ff8c6071dba69c8e7a7` |
| `environment.txt` | `fa55e4043679c806f8bddea0217806063388926da24a91a289b1ac714c70f4fa` |

## Scope

These checks prove objective and checkpoint/runner wiring on the pre-#235
baseline. They do not establish convergence, distribution retention, strength,
native parity or the extra model's inference cost. Actual comparison must use
#235's official 30-turn own-points task after integration acceptance and separately
authorized qualifying BC/training. No training run, new match or corpus collection
was started. Frozen data, old runs/manifests and previous evidence were not edited.
The two untouched grandfathered source files remain 1,504 and 1,050 lines; all
files added or changed here remain below 1,000 lines.
