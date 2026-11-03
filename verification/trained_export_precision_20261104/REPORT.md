# Frozen inference precision on a trained duel checkpoint

The unchanged absolute export tolerance is `1e-5` for every candidate logit and value. The v6 duel v37 checkpoint (SHA256 `7e6804cbc27eccd243c847075f14cc9f07192a732455193b4e20d1684b108323`) failed the ordinary sequence audit on the complete first retained duel rollout from the item 10 refresh (SHA256 `3135ba1007eb4ccae5976b63c1501805b29a2b873fa140f34e5ec4be746345c3`). There were 133 decisions across 15 turns, 120 decisions had a full candidate set.

The first deviation exceeding tolerance occurred on turn 1, decision 1, candidate index 11. Python float32 returned −22.9473838806 and the deployed Lua implementation returned −22.9473957113. Using the same checkpoint, history, inputs and serialized coefficients, a diagnostic PyTorch float64 forward returned −22.9473957113. Across all 4,753 logits, 58 Python float32 scores missed tolerance. Float64 and Lua agreed to 5.69e-14. [Baseline audit](real-before.log) · [Three-way diagnostic](precision.json)

The fixed tensor policy used for actual Lite rollout/evaluation and the export auditor both use binary64 arithmetic for the frozen float32 weights. BC/PPO optimizer computations and the weight file format retain float32. The exporter still checks every supplied row, action and value through the actual Lua scorer. The same complete real sequence passed the normal entry with maximum error 5.684341886080802e-14. [Actual fixed audit](real-after.log)

## Ubuntu reproduction

Baseline production code matched `613cc97` for all measured modules. Fixed source `7b83580b7b209654163e42c695e9a114a3d91352` was shipped as a git archive containing `learning tests lua engine_lite vendor/arena`, SHA256 `ab214ad5187918b370f37937c799bc32e21c28794478c7a0dd5eb5a1e306840c`. The fresh directory was `/home/tongshu/acceptance/frozen_double_7b83580_20261104`. Python 3.12.3 and torch 2.9.1+cpu used one thread. The catalog and checkpoint inputs were read from the original acceptance locations.

```sh
export PYTHONPATH=.:vendor/arena:/home/tongshu/acceptance/teacher_immunity_checked_20261103/.extension
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
/home/tongshu/venv/bin/python -u loop-export-cost.py
/home/tongshu/venv/bin/python -m unittest tests.v5.test_lite_policy_memory tests.v5.test_window_memory_cost.IncrementalMemoryTests.test_long_rollout_encodes_each_history_row_once tests.v5.test_learning_core.AuditExportTests.test_verify_numerics_requires_full_budget_and_two_turns tests.v5.test_learning_core.AuditExportTests.test_verify_numerics_37_candidates_two_turns tests.v5.test_learning_core.AuditExportTests.test_verify_numerics_memory_overflow_and_128_entities tests.v5.test_replay_optimization -v
```

[Replay command body](replay.py) · [Offline diagnostic command body](precision_probe.py). The diagnostic instrumented the old audit loop to record the difference between precisions. Acceptance used the uninstrumented verifier. The trained-scale regression failed on the baseline (1.81e-5). Eight affected Ubuntu checks passed on the fixed code, including frozen incremental memory, complete-sequence parity and training gradient equivalence. This is a deployment arithmetic result. The timed full loop needs separate evidence. [Regression on baseline](red.log) · [Checks](tests.log)
