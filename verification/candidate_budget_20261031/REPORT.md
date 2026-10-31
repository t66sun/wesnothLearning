# Shared candidate selection acceptance

Date: 2026-10-31. Scope: blockers 1-2, balanced 36-action selection plus end-turn in all runtime paths.

## Identities and procedure

- Tested source: `1324878` on `codex/shared-candidate-budget`, shipped with `git archive --format=tar HEAD`, extracted into `/home/tongshu/acceptance/candidate_budget_20261031_v2` on `cpuServer`.
- Baseline source: `f563cade05eabeb6a45f48ce0dc476654cf71ae4`, independently archived into `candidate_budget_20261031_baseline` and `candidate_budget_20261031_revert`.
- Python: `/home/tongshu/venv/bin/python`; existing installed lite extension. Rust source was unchanged. Frozen rules reused read-only via a symlink to `/home/tongshu/myDev/wesnothLearning/WesnothLearning/data/rules`; synthetic rules/rows used by contract suites.
- Candidate identity: `fixed-20000-v4`, schema carries quotas 12/12/12, actionable cap 36 and one end-turn. Old schema checkpoints/exports are not silently resumed. Historical data/evidence were not rewritten.

## Commands and results

From the v2 source directory:

```sh
PYTHONPATH=.:vendor/arena /home/tongshu/venv/bin/python -m unittest \
  tests.test_candidate_budget tests.test_lua_contracts \
  tests.v5.test_candidate_provenance tests.v5.test_learning_core \
  tests.v5.test_checkpoint_export_identity -v
```

55 tests, 54 passed, 1 error; 12.594 seconds. See `checks.log`.

The four affected suites passed all 54 tests: quota preservation, actor/type diversity behavior, deterministic refill/deduplication, sparse candidates, crowded-board combat/recruit retention, end-turn, removal of bot-only prefix truncation, lite provenance, 37-candidate sequence numerical parity and existing 128-candidate/entity and recurrent-memory stress coverage. No lowered numerical tolerance (1e-5), skipped test, retry or production exception handler was introduced.

The extra `test_checkpoint_export_identity` suite errors before reaching export: its mocked train result omits `planned_steps`, read by unchanged `finish_train`. Running its original test alone on the pristine baseline reproduces the identical KeyError (one error, 0.385 seconds; `baseline.log`). This check is FAILED, not accepted or suppressed, and the unrelated fixture/implementation was left unchanged.

```sh
# Pristine baseline directory:
PYTHONPATH=.:vendor/arena /home/tongshu/venv/bin/python -m unittest tests.v5.test_checkpoint_export_identity -v
# Independent baseline directory with only the two current test files copied in:
PYTHONPATH=.:vendor/arena /home/tongshu/venv/bin/python -m unittest \
  tests.test_candidate_budget.CandidateBudgetTests.test_crowded_generator_keeps_combat_and_recruits \
  tests.test_lua_contracts.LuaContractTests.test_deployed_bot_scores_the_shared_pool_without_prefix_truncation -v
```

Both new integration assertions fail with the original generator/bot (two failures, 0.016 seconds; `revert.log`) and pass on the new source. This establishes sensitivity to reverting the behaviors.

The initial `a03f4a8` run had 52 passing tests and one failing audit-boundary test: the old synthetic fixture already contained more than 37 candidates. The test input was corrected to 36, preserving the rejection assertion and adding a successful full-37 audit case. The subsequent v2 result above is the acceptance result.

## Limits

Minimal functional and numerical acceptance only. No formal training, corpus collection, full evaluation or native games were launched. Native full-decision latency with up to 37 candidates is NOT RUN and remains TEST.md C1; old 24-candidate timing evidence does not cover this budget. No strength/convergence or whole-package performance claim. Frozen inputs and prior evidence remain unchanged.
