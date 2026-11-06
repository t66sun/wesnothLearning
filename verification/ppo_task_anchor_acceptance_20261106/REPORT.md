# Finite-task and frozen-BC integration acceptance

Issues [#235](https://github.com/t66sun/wesnothLearning/issues/235), [#239](https://github.com/t66sun/wesnothLearning/issues/239) and the accepted [#240](https://github.com/t66sun/wesnothLearning/issues/240). Date: 2026-11-06.

## Result

**88 Ubuntu checks passed in 27.134 seconds**, exit 0. The finite official-score task, optional frozen BC target and complete single-read rollout path work together in the exercised runner, checkpoint, branch and data paths. [Complete output](checks.log).

The integration preserves both task validation and `prepared_ppo` reuse. A same-task qualifying BC parent supplies its pinned endpoint to either auxiliary mode. BC restart and weights-only initialization copy neither the old anchor nor the old qualifying BC endpoint. Their assertions exercise the actual branch copy function. A legacy three-format actor can initialize a fresh duel task without inheriting its corpus, value head, optimizer or passed gates.

The real-runner two-target test uses finite-task rowpack shards. It verifies the batch-frozen coefficient, independent anchor identity, distinct parameter updates for historical CE versus frozen KL, and exact interrupted/resumed results. Replacing only forward KL with historical CE makes its final parameter-inequality assertion fail. The unmodified test passed in the combined suite.

## Source and environment

| Item | Identity |
| --- | --- |
| Tested integration commit | `65b15bf9faed231dcb8955fa81f32cf14374cdef` |
| Integrated finite-task implementation | `a9695403d9a18b79e4cab824c49bc1056028a18a` |
| Frozen BC standalone passing implementation | `0616abd60557ad5f4f0f7dad9a477fdf7ac3e378` |
| Accepted single-read master | `ad7256e838fa941d76d92bf5d56a4683f75b37cd` |
| Archive SHA-256 | `2650d96d1bed75caf0aed136ba1770df92454ae5f5ac29ca838457dc9719e981` |
| Ubuntu extraction | `/home/tongshu/acceptance/ppo_task_anchor_20261106_65b15bf/source` |
| Python / Torch | `/home/tongshu/venv/bin/python`, 3.12.3 / 2.9.1+cpu |
| Rules SHA-256 | `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17` |
| Existing extension | `/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension` |

The commit was shipped with `git archive` and extracted into a new directory; its archive hash was verified before execution. Neither Rust nor the embedded Lite host changed. Map inputs were linked from `/home/tongshu/myDev/wesnothLearning/WesnothLearning/rules/1.18.8`. The first setup command stopped before any tests because the archive excludes `data/`; creating `data/rules` and its map link completed provisioning. No test was bypassed or retried after a failure. No Windows tests ran.

The later integration of #235's final documentation/evidence changes does not change runtime or test source relative to the tested commit. The line scan found only the two untouched grandfathered files: `tests/v5/test_pipeline_contract.py` (1504) and `tests/smoke_training_lite_8worker.py` (1050). [Source checks](source_checks.txt).

## Reproduction

From a fresh archive extraction on Ubuntu, provision the existing rules, extension and map link, then run:

```bash
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PWD:/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension"
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
/home/tongshu/venv/bin/python -m unittest \
  tests.v5.test_finite_score tests.v5.test_finite_score_identity \
  tests.v5.test_frozen_bc_loss tests.v5.test_frozen_bc_anchor \
  tests.v5.test_ppo_rollout_read_once tests.v5.test_rehearsal_source \
  tests.v5.test_ppo_plan tests.v5.test_ppo_resume_counters \
  tests.v5.test_ppo_phase_boundary tests.v5.test_branch_restart_bc \
  tests.v5.test_branch_teacher_evidence tests.v5.test_bc_preflight_read \
  tests.v5.test_rollout_content_identity tests.v5.test_training_turn_limit -v
```

The 88 tests include 27 finite-task/identity, 43 frozen-target and affected caller, 7 single-read, 5 BC-read/content-identity and 6 turn-limit checks. These overlap the prior standalone evidence; they are not 88 additional independent scientific observations. The bounded-loop fixture emits its expected `FAIL BC execution or bounded batch/time limit` diagnostic and the enclosing unittest passes.

For the loss reversion, use the same environment and the in-process wrapper documented in the [standalone frozen-BC report](../frozen_bc_anchor_20261106/REPORT.md#target-reversion-assertion). Run `FrozenBcAnchorTests.test_real_runner_compares_targets_and_uses_pending_coefficient` with `learning.ppo.forward_kl` replaced by cross-entropy against candidate zero. Both arms then produce `143106dbf17efbdb70eab6518c404546ca4bd731906db7ca3bd11351fdc9505b`; `assertNotEqual` fails in 2.149 seconds. The wrapper requires that exact assertion failure and no errors. [Observed output](target_reversion.log). Production files remain unchanged.

## Acceptance limits

The combined checks use bounded synthetic states and transient optimizer updates. They do not establish trained-policy BC readiness, critic calibration, retention, convergence or playing-strength gains. Full native games and a formal training run were not executed. The separate [116 finite-task checks](../finite_score_20261106/REPORT.md), [43 frozen-target checks](../frozen_bc_anchor_20261106/REPORT.md) and [six frozen read-cost comparisons](../rollout_read_once_20261106/REPORT.md) retain their original source identities and limits.

The implemented boundary items are accepted and removed from `docs/TEST.md`; the finite-task training/calibration item remains. The bounded duel experiment in #227 must use a newly qualified finite-task BC endpoint and its own frozen protocol. Existing inputs, runs, manifests and previous evidence were not edited.
