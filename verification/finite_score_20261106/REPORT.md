# Finite official-score task acceptance

Issue: [#235](https://github.com/t66sun/wesnothLearning/issues/235).

## Result and scope

New runs use `official-score-30-v1`: complete round 30 is the scored task terminal. Duel/team own official points `3/1/0` map to `+1/-1/3/-1`; FFA's official normalized rank score maps through `2*score-1`. Gamma is 1, exploration reward is zero, and economy/control remain potential differences. Natural and scored terminals clear endpoint potential and bootstrap, including a previously eliminated teammate. A genuinely earlier external cut retains bootstrap.

BC, DAgger and PPO carry the same task identity. Known complete BC targets are `z-phi(row)`, matching complete PPO/MC returns. Legacy configuration deserialization stays legacy. Training, data mixing and resume reject old task identities; old checkpoints remain loadable for read-only inference. Explicit weights-only initialization starts a new BC run with a reset value head, optimizer, gates, controller and corpus. A duel subset of an old three-format parent is supported only for that initializer.

**116 Ubuntu checks passed**: 27 finite-score/identity checks, 7 single-read PPO integration checks and 82 affected regressions. A controlled restoration of the old zero-draw reward failed a numeric return assertion. No collection, formal training or new evaluation panel was run. Existing no-drop, physical scenario partitioning, hidden-referee separation, control exclusion and KL settlement contracts are unchanged.

## Source and environment

| Item | Identity |
| --- | --- |
| Tested source | `a9695403d9a18b79e4cab824c49bc1056028a18a` |
| Integrated master | `ad7256e838fa941d76d92bf5d56a4683f75b37cd` (#240) |
| Archive SHA-256 | `f581da9b9582f7815390fe553d4d4125066a662326f67cef6c5d7de158761d6b` |
| Acceptance source | `/home/tongshu/acceptance/finite_score_20261106_a969540/source` |
| Python | `/home/tongshu/venv/bin/python`, 3.12.3 |
| PyTorch | `2.9.1+cpu` |
| Rules SHA-256 | `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17` |
| Extension SHA-256 | `56dd77140411db987377d6de4ffbf562da4d0e5c76bc16d34780da67e60e5ae4` |

The archive was produced with `git archive --format=tar HEAD`, uploaded, and extracted to the fresh directory above. `SOURCE_COMMIT` records its commit. No Rust or embedded `engine_lite/lua/host.lua` change is part of this behavior, so the provisioned extension was reused; changed Python/Lua modules were loaded from the archive. Full environment identities are in [identities.log](identities.log). Later documentation/evidence commits do not alter tested runtime or tests.

From the extracted source, every test invocation used:

```bash
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PWD:/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension"
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
```

`data/rules/1.18.8` links to `/home/tongshu/myDev/wesnothLearning/WesnothLearning/rules/1.18.8`. The historical formal run and frozen data/evidence were not modified. Tests used synthetic rules/boards where declared by their fixtures. No Windows tests were run.

## Checks

| Invocation | Observed result | Evidence |
| --- | --- | --- |
| Finite-score + identity + single-read suites | 34 tests, 12.234 s, OK | [final-tests.log](final-tests.log) |
| Affected regression suites/classes | 82 tests, 13.545 s, OK | [final-regression-tests.log](final-regression-tests.log) |
| Restore old zero-draw reward for one completed-return test | 1 test, expected failure, exit 1 | [reverted-terminal-tests.log](reverted-terminal-tests.log) |
| Source line scan | Only the two unchanged grandfathered test files exceed 1000 | [identities.log](identities.log) |

Commands:

```bash
/home/tongshu/venv/bin/python -m unittest -v \
  tests.v5.test_finite_score \
  tests.v5.test_finite_score_identity \
  tests.v5.test_ppo_rollout_read_once

/home/tongshu/venv/bin/python -m unittest -v \
  tests.v5.test_reward_row_schema \
  tests.v5.test_critic_horizon \
  tests.v5.test_training_turn_limit \
  tests.v5.test_branch_restart_bc \
  tests.v5.test_checkpoint_ops \
  tests.v5.test_checkpoint_export_identity \
  tests.v5.test_scenario_identity \
  tests.v5.test_ppo_scenario_coverage \
  tests.v5.test_teacher_control_compatibility \
  tests.v5.test_record_evidence \
  tests.v5.test_pipeline_contract.RewardMetricsTests \
  tests.v5.test_pipeline_contract.ControlQueueTests \
  tests.v5.test_pipeline_contract.BoundaryTests \
  tests.v5.test_pipeline_contract.PackageManifestTests.test_freeze_writes_hashed_manifest_and_verifies
```

The finite suite covers natural wins/losses, complete round 30, a real Lite cut after round 29 (reported turn 30), shared team outcomes after early elimination, gamma/lambda own-turn gaps, telescope sums, BC optimization, DAgger validity, raw rowpack metadata, task-incompatible data/checkpoints/resume and actor-only initialization. Native coverage executes the actual Lua finish hook and feeds native events through the ingestion path; it does not launch a full Wesnoth process. The single-read suite checks one complete fresh read, preserved raw prefixes/tails, resume rereads and identity, matching losses/gradients/RNG, and unchanged KL-stop cursor settlement.

The line scan found only `tests/v5/test_pipeline_contract.py` (1504) and `tests/smoke_training_lite_8worker.py` (1050). Both files are byte-unchanged by this PR. Local `git diff --check` passed.

## Assertion under controlled restoration

The following was run in a separate process without editing source files:

```python
import sys
import unittest
from unittest.mock import patch
from learning import rewards
from learning.tasks import LEGACY_TASK
original = rewards.terminal_rewards
suite = unittest.defaultTestLoader.loadTestsFromName(
    'tests.v5.test_finite_score.FiniteScoreArithmeticTests.'
    'test_completed_draw_telescopes_and_bc_matches_mc_and_ppo')
with patch.object(rewards, 'terminal_rewards',
                  side_effect=lambda result, task_id=LEGACY_TASK: original(result, LEGACY_TASK)):
    result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(not result.wasSuccessful())
```

It fails at `sum(row['reward_step']) == -1/3-.06`: the restored formula produces `-0.06000000000000001`, instead of `-0.3933333333333333`. The unmodified test passed in the 34-test suite. This is a mathematical regression assertion, not an import or missing-module failure.

## Preserved first attempts

- Source `c241f6366a2b0f30e8eea7761fa543931e4f01e6`, archive SHA-256 `14948333f3282a4440933e0c2675725d4ce605d5e5765204fdcecb3017cd224c`, under `/home/tongshu/acceptance/finite_score_20261106_c241f63`: 26 finite/identity tests, 25 passed and one fixture failed ([initial-tests.log](initial-tests.log)); the 82 affected regressions passed ([regression-tests.log](regression-tests.log)).
- The initial BC optimizer fixture used output bias `.75`, whose one-step target displacement activated the unchanged `.5` gradient clip. It observed `.2500004172` instead of `-.3933333333`. Commit `18b4e07f09b6226273b750708a18ce0bbffb15f6` changed only that fixture's initial bias to `-.2`; the target assertion and production clipping were unchanged. The corrected test passed on the final source.
- The first environment-report script imported `load` from `learning.rules` instead of `learning.rules_catalog`; [identities-failed.log](identities-failed.log) preserves that report-only import error. The corrected identity capture succeeded. It was separate from both passing test suites and the controlled reward restoration.
- Regression output includes the bounded-loop fixture's expected `FAIL BC execution or bounded batch/time limit` diagnostic. Its enclosing unittest reports `ok`; both complete regression invocations end with `OK`.

## Next finite-task BC entry and limits

For a separately authorized duel run initialized from the old BC actor, the narrow entry is:

```bash
python -m learning run --run-dir NEW_CHILD --branch-from OLD_PARENT \
  --branch-weights-only --branch-checkpoint last_bc --phase bc --formats duel \
  --engine lite --device cpu --rules-dir RULES_DIRECTORY \
  --human-data EMPTY_OR_TASK_COMPATIBLE_DIRECTORY --hours AUTHORIZED_HOURS --seed SEED
```

Use the parent's engine/rules and the authorized sampling/worker/budget settings. The new run defaults to the fixed 30-round task, imports no parent corpus, records the exact old checkpoint hash and must pass fresh BC gates. Omitting `--branch-checkpoint` selects `latest`. Ordinary same-task branches preserve their inheritance contract and complete format set. A subsequent comparison should branch from the newly qualified finite-task BC endpoint, not treat the old actor initializer as qualified finite-task BC.

Task identity does not enter the physical scenario-family hash. The preexisting cap field does, so old 60-turn and new 30-turn internal BC partitions may differ. Old actor exposure must be audited separately when selecting independent validation/holdout map groups; a changed task label is not evidence of unseen physical layouts.

This acceptance establishes target/boundary/identity wiring. It does not establish finite-task BC readiness, critic calibration on a trained policy, PPO benefit, convergence, or native full-game equivalence. Those remain in `docs/TEST.md` pending their separately authorized work. No old data or checkpoint was relabelled and no historical report was rewritten.
