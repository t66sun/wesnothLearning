# R2 batch-eligibility acceptance — 2026-10-27

Scope: issue #54, parent #48; implementation `3a924362ce4ad833889439950b2ae3dc6eb61b15`, based on R1 main `2b9fafe729759f826d67c1e46fd0561e66b6d761`.

## Result

PPO schedules deterministically select eligible training scenarios before freezing, and repeat that selection after effective engine/rules overrides. Requested/selected map and faction indices are recorded. Game roles, seeds, quotas and RNG consumption are preserved. PPO rejects any non-training row before identity commitment and in `prepare`, rather than filtering it. Successful results report eligible decisions and zero excluded games/decisions. BC explicitly retains its existing train/validation partition handling. The manifest freezes `scenario-v2/no-drop-v1`; older runs require their original frozen source and cannot resume through this contract.

## Local reference

The 18 affected eligibility/counter/schedule/BC-RNG/opponent checks passed (7.651 s); two content-identity checks passed (2.716 s). The added FFA4/2v2 update test initially failed because its synthetic fixture omitted reward/value fields; after supplying complete trajectories and matching history-based behavior predictions, that one test passed (2.994 s). No production gate was changed to accommodate the fixture.

Both environments lack pytest. The specified unittest-based files run through `python -m unittest`, with the same assertions, without installing dependencies.

## Ubuntu acceptance

Main isolated directory: `/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r2_20261027_3a92436`. Shared dependencies: `/home/tongshu/venv`; read-only data input: the frozen `training_lite30h_20261025/source/data`. Linux 7.0.0-38-generic, Python 3.12.3, torch 2.9.1+cpu. Rule SHA-256: `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`; see [environment](ubuntu/environment.log).

Source archive: 2,037,760 bytes; SHA-256 `9c7bbdc26d572654bb507d8dcaf5123a7da505d3f1b3ebf7c9a493c931a37c8d`. It contains tracked source and a baseline updates module for the revert probe; excludes data, runs and dependencies.

```powershell
scp tmp/refactor_r2_20261027/source.tar cpuServer:/tmp/wesnoth-r2-3a92436.tar
scp verification/ppo_refactor_r2_20261027/run_ubuntu.sh cpuServer:/tmp/wesnoth-r2-3a92436.sh
ssh cpuServer "bash /tmp/wesnoth-r2-3a92436.sh 9c7bbdc26d572654bb507d8dcaf5123a7da505d3f1b3ebf7c9a493c931a37c8d"
scp tests/v5/test_batch_eligibility.py cpuServer:/tmp/wesnoth-r2-supplement-test.py
scp verification/ppo_refactor_r2_20261027/run_supplement.sh cpuServer:/tmp/wesnoth-r2-supplement.sh
ssh cpuServer "bash /tmp/wesnoth-r2-supplement.sh"
```

Exact test commands are in [main script](run_ubuntu.sh) and [supplement script](run_supplement.sh).

| Check | Observed | Evidence |
| --- | --- | --- |
| Eligibility, resume counters, schedules, BC cancellation RNG, opponent identity, rollout content | 20 PASS, 7.414 s | [targeted](ubuntu/targeted.log) |
| Restore baseline silent filtering; run `test_validation_row_in_batch_raises` | FAIL as required: `ValueError not raised` | [reverted](ubuntu/reverted.log) |
| Restore repaired code; repeat that assertion | PASS | [restored](ubuntu/restored.log) |
| Compared production/test source before and after revert probe | Identical | [before](ubuntu/source_before.sha256), [after](ubuntu/source_after.sha256), [status](ubuntu/status.log) |
| Additional FFA4/2v2 synthetic optimizer updates | 1 PASS with two subcases, 1.264 s | [supplement](ubuntu/supplement.log), [test hash](ubuntu/supplement.sha256) |

The supplement uses a separate directory `acceptance_ppo_r2_20261027_supplement`, imports the already accepted production source, and does not overwrite its source or logs. The final test-file SHA-256 is `b4b85a9525cf645f3146ef4c3db5d659afe88b4c686b9bddb3313ac77211cf10`. Original 20-test evidence is reused; the full group was not repeated for this test-only addition.

## Limits and remaining work

These checks establish scheduling/update wiring and accounting, including 20 scheduled batches across all three formats and actual tiny updates for all formats. They do not prove convergence, strength, native semantics or a complete training run. No real games, collection, corpus re-encoding or formal training were started. The frozen historical rollout is not passed through a synthetic repartition: its old identity remains read-only and the new manifest guard intentionally rejects legacy resume. Existing R1 evidence is reused. R3–R10 are not implemented or accepted by this report. Native N1 and numerical/package failures remain open under their original gates.
