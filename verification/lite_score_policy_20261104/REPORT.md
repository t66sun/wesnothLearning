# Final student inference on a team validation board

On November 4, 2026, `cpuServer` replayed the preselected v10 team validation game `val000010-team2v2-b0000-self_team-r0` once with each worker. The score-only student used **13.262 seconds** versus **16.314 seconds** previously, an 18.7% wall reduction. The four hashes below match exactly across the runs. Both workers reached the archived fault-free official result. [Raw matched results and tests](comparison.tar.gz)

| Measured quantity | Original | Score-only student |
| --- | ---: | ---: |
| Whole worker CPU seconds | 16.310 | 13.259 |
| Student decision / execution CPU seconds | 4.421 / 3.759 | 3.752 / 1.353 |
| Public observation captures | 720 | 480 |
| Reward captures | 480 (2.266 s) | 0 |
| Opening diagnostic rows constructed | 240 | 0 |
| Student candidate generations | 240 | 240 |
| Neural memory scenes constructed / committed | 437 / 43 | 43 / 43 |

| Complete stream | Matching SHA256 |
| --- | --- |
| 240 policy observations and full ordered candidates | `6c4eab5198f83a36e8839bebd73b454d357e36c84356720d7fbfcb281ffc578c` |
| Actual fp64 tensor logits and values | `ca1f3b9a70ac5b6888e6eab5802ed644f92af8b3bcc583883b3c41bfb0a01f35` |
| 43 committed public turn-memory rows | `446e616f344179d95d6b80989a029ca58810ee1824b19e23db1eece0cf8f2590` |
| 740 actions, commit flags and ordered referee events | `50b5a26517b491dc5833d036e6ecb689b981151c8b767e40c547f04e71b96d82` |

The student still captures each post-action state for visible terrain, last-seen units and village ownership. Its existing recurrent history determines whether execution needs a turn-memory write. If end turn is the first successful action, the host captures that pre-action scene in canonical memory order. Jobs collecting trajectories, opening diagnostics or reward horizon evidence keep their full outputs.

## Scope, inputs and commands

The two policy seats played against two Astra seats on the original Loris River validation map and seed 488635208. Both arms used the same stored `validation-000010.json`, trained tensor, fp64 inference, v6 teacher, public candidate generation and 30-turn cap. The harness removed learner instrumentation, requested score-only Astra, and changed only the isolated output/deadline and the new student option between arms. It timed the same Lua functions and fingerprinted the same policy data in both. This is one validation game, with no formal holdout or multi-worker timing result.

Committed archives were extracted separately under `/home/tongshu/acceptance/lite_score_policy_20261104`. `4303db3020eed4f8c646abbfd83ecb6071ff7843` shipped the harness with unmodified production source `8b45c07`. Its archive SHA256 was `03a34ab9248ef44b578e485248e73dcc5c6ffb3edb2c794aca73e194fcd3d725`. The optimized replay/build used `5bd0dcc443a380ec6d0a602ca73a2b3c5c15726a`, archive SHA256 `9d6e0166aab9114fb2b14796746564971180f5024b6f969848cf9e10eda3ef7f`. Final fixture source was `942ec62e5aee2f691fe92d2f6ef0f04fcbf48792` with identical production bytes, archive SHA256 `cdc11c2d5e59ee144f7207eb9a7c428700c91052d95c60185f8d2ebacc07a60d`.

The baseline and optimized extension digests, schedule, rules, teacher and model digests are in `before/summary.json` and `after/summary.json` in the [raw archive](comparison.tar.gz). The build used `cargo build --release --offline --manifest-path engine_lite/Cargo.toml`. Each arm used its own extension and the frozen filtered rules, with OMP, MKL and OpenBLAS thread counts set to one. Both executed commands exited 0. The baseline omitted `--score-policy` and used `../before`.

```sh
export PYTHONPATH=.extension:.:vendor/arena
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export SOURCE_COMMIT=5bd0dcc443a380ec6d0a602ca73a2b3c5c15726a
timeout --signal=TERM --kill-after=3s 120s /home/tongshu/venv/bin/python -B -u \
  verification/lite_score_policy_20261104/compare.py \
  /home/tongshu/acceptance/bc_v6_readiness_20261103/runs/bc_readiness ../after --score-policy
```

## Regression coverage

The baseline rejected the new score-only call. An initial synthetic fixture selected only end turn and correctly failed its requested move/omission coverage. On the expanded fixture, the full pre-existing candidate generator rejected a hypothetical attack on unknown terrain after moving on a shrouded board. The final test exercises moves and repeated commits on the formal fog/no-shroud settings and separately compares shrouded end-turn observations. It compares every scene and ordered candidate set, visible pre/post outcome, complete teacher ledger, policy-visible memory, resulting referee state and each consumed memory write. It also requires that suppressed reward and diagnostic outputs are absent. Both earlier fixture results are preserved.

```sh
/home/tongshu/venv/bin/python -B -m unittest tests.v5.test_lite_score_policy \
  tests.v5.test_lite_score_astra tests.v5.test_teacher_state_reuse tests.v5.test_record_evidence \
  tests.v5.test_lite_policy_memory \
  tests.v5.test_lite_default.LiteDefaultTests.test_lite_final_evaluation_has_only_astra_controls \
  tests.test_lua_contracts -v
```

The 22 affected checks passed in 2.265 seconds. The raw evidence archive SHA256 is `2fb31d937cac600ad3c4d93a9ad0a1927556ebe3ccd0ead2b903679ac135587e`.
