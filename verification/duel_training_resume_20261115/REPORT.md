# Ubuntu duel training and resume acceptance

The 176-test acceptance command passed in 48.241 seconds. The same fixture order includes the broad suite previously recorded with five errors and two failures, plus the BC and PPO resume suites. The red check on the old Lite worker reproduced the extra critic call for an eliminated seat. [Previous results](../workflow_slim_20261115/REPORT.md) · [Passing log](ubuntu-tests.txt) · [Expected revert failure](expected-revert.txt)

- A surviving learner at a short cap keeps the full candidate decision and a required bootstrap. The arithmetic fixture verifies the shaped return, and the real Lite fixture writes the supplied 0.8 value for both duel seats at the round-29 cut. Completing round 30 records the official result without a bootstrap. Lite now applies the same per-seat predicate for inference that the shard writer uses, so an eliminated solo learner makes no critic call when the remaining players hit the cap.
- The sequence check verifies the explicit legacy partition rule, equal plain and packed payloads and equal records with their raw prefixes after reopening SQLite. A changed raw row under the same sequence identity still fails. The task and rule checks bind the finite task to the scheduled reward and restore the test process's original rule context after exercising a historical manifest.
- The default duel PPO fixture opens a checkpoint after its first Adam step and rereads the pending shard. The resumed and uninterrupted runs match in model digest, exact Adam state, counters, cursor, loss and sampling RNG. Changing the pending target or its raw prefix is rejected before updating. Separate fixtures exercise the BC cancel boundary and the frozen-BC anchor through the resume constructor.

## Reproduction

Tested source `10260cc5b61ec73a22f7bd69b6ca18e24957bb74` was extracted into `/home/tongshu/acceptance/duel-resume-20261115-PHX3gu/source` on `cpuServer`. Source archive SHA-256 is `f6c1bb10bb9dfba1ec11a223c8e56c4ffd9d2dd9293d3f126bb8bfa7851970e2`. The Lite extension SHA-256 is `3c3549abac29b940c7a32615432f35babfbd8c8e8f7d87fd8bbc442ef2265a51`. The embedded host and Rust sources matched the previously built extension tree byte for byte. Production rules SHA-256 is `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`. Fixtures that exercise historical manifests link to the existing `1.18.8` and `1.18.8-training` catalogs under `/home/tongshu/myDev/wesnothLearning/WesnothLearning/rules`.

```sh
root=/home/tongshu/acceptance/duel-resume-20261115-PHX3gu
cd "$root/source"
export PYTHONPATH="$root/.extension:$PWD"
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export WESNOTH_EXE=/home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth
/home/tongshu/venv/bin/python -m unittest -v \
  tests.test_experiment \
  tests.test_schedule \
  tests.test_training_revision \
  tests.test_validation_cadence \
  tests.test_lua_contracts \
  tests.v5.test_checkpoint_export_identity \
  tests.v5.test_finite_score_identity \
  tests.v5.test_final_nomination \
  tests.v5.test_lite_default \
  tests.v5.test_lite_score_astra \
  tests.v5.test_lite_score_policy \
  tests.v5.test_pipeline_schedule \
  tests.v5.test_record_evidence \
  tests.v5.test_teacher_strength_acceptance \
  tests.v5.test_training_failure_fixes \
  tests.v5.test_training_turn_limit \
  tests.v5.test_collection_memory \
  tests.v5.test_finite_score \
  tests.v5.test_lite_combat_choice \
  tests.v5.test_bc_cancel_rng \
  tests.v5.test_ppo_plan \
  tests.v5.test_ppo_rollout_read_once \
  tests.v5.test_frozen_bc_anchor \
  tests.v5.test_ppo_resume_counters
```

The accepted scope is fixture-backed training and resume. The remaining formal strength and critic-calibration claims are recorded in the [acceptance plan](../../docs/TEST.md).
