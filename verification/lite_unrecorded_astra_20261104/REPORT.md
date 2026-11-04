# Fixed Astra opponents in mixed Lite jobs

On November 4, 2026, `cpuServer` replayed one ordinary team validation game using the v10 frozen student and three fixed Astra seats. The game took **44.948 seconds** with full opponent observations and **23.875 seconds** with compact unrecorded opponents, a 46.9% wall reduction. CPU time was 44.937 and 23.870 seconds respectively. Both complete job result objects were equal, including official outcome, fault status, truncation, coverage, every reward statistic and both horizon records. [Raw results and comparison](comparison.tar.gz)

| Seat / stream | Original | Compact opponents |
| --- | ---: | ---: |
| Student seat 1, full decision or observation calls | 130 | 130 |
| Astra seats 2 / 3 / 4, full calls | 148 / 288 / 467 | 0 / 0 / 0 |
| Astra seats 2 / 3 / 4, compact calls | 0 / 0 / 0 | 148 / 288 / 467 |
| Learner rows / policy inputs including bootstrap / accepted memory writes | 128 / 129 / 30 | 128 / 129 / 30 |
| Actions and referee event sequences | 1,031 | 1,031 |

Six stream hashes matched: all learner rows and their reward/observation/outcome fields, all actor inputs including the truncation bootstrap, all recorded predictions, all accepted history writes, the initial metric snapshot, and all action identities, commit flags and ordered referee events. The row comparison removed only elapsed `timing.ms`; decision-work counters, candidate identities and the rest of each row were compared. Turn 5 and 10 both had complete entity evidence, coverage of 0.6864 and 0.7920 and control of 0.5371052613 and 0.4786982203 respectively. The original archived official result also matched.

The worker writes trajectories and DAgger corrections for declared learner seats. It takes initial, elimination and terminal horizon snapshots for those same seats. The Lite reward ledger is scoped per side. An opening probe is the exception that consumes every seat's per-action diagnostics. The worker now uses the existing public Astra planner and shared executor for the other fixed seats in teacher, PPO, DAgger refresh, ordinary validation and reward-reference phases. Learner teachers, DAgger queries, truncation bootstrap, horizon snapshots and opening probes continue to obtain the full data they consume.

## Identity and command

The preselected game was `val000010-team2v2-b0000-astra_partner-r0`, Loris River validation map, seed 2791729219, 30-turn limit. It used the original policy, factions and seats from the [v6 BC validation schedule](../bc_ordinary_v6_20261103/REPORT.md). The archived schedule predates the ordinary validation phase tag. Both arms set `meta.phase=validation` exactly as the current producer does and retained its original `learning.sides={'1': ...}` configuration. Each arm redirected output and deadline to fresh paths. This paired replay had no output shard, optimizer or holdout game.

| Purpose | Shipped commit | Archive SHA256 |
| --- | --- | --- |
| Full opponent baseline | `686f3f5b855760a31d3116b9a0e0d1bfc0242d75` | `3842dda9d0c09a5ebb0995f2c43d1022d38470061190c9e5bad9b37244fe76b1` |
| Failing mixed-seat assertions | `eb3881f9fd204c3df3c4fe5648e57de10deb922d` | `8a318cdc1516dcc3ce69f22fa914888ae54d63674549e597f0caf55ee69b5cd4` |
| Compact mixed opponent replay | `ba7b962a8d1bee8b199e1269b71f8d4093519433` | `91e0a1ae2f8ffd52d8d8f072c49b5bf9064e3140972fe3f01fe52e0cebcde27c` |
| Final test fixtures, identical worker | `b59ecfec8fbe206437e31e81199033383d49cbe9` | `3805d5e21b7bede9c67bd54f2157606e15fa6346e6bca751a58405f93e151efa` |

All committed archives were extracted in fresh directories under `/home/tongshu/acceptance/lite_unrecorded_astra_20261104`. The same release extension `47585b18f33dc3a52e518e8fa90acc0fdf791086267492df6a617aecfdfdb241` was used by both source versions. Each JSON summary records the matched rule, teacher, model and source schedule hashes. With `.extension`, the repo and `vendor/arena` on `PYTHONPATH`, the filtered rules bound through `WESNOTH_RULES_DIR`, and numeric thread limits of one, each arm ran the following command once and exited 0. The baseline wrote to `../before` and each arm set `SOURCE_COMMIT` to its shipped commit.

```sh
timeout --signal=TERM --kill-after=3s 120s /home/tongshu/venv/bin/python -B -u \
  verification/lite_unrecorded_astra_20261104/compare.py \
  /home/tongshu/acceptance/bc_v6_readiness_20261103/runs/bc_readiness ../after
```

## Regression coverage

Both new seat-routing assertions failed on the old worker because every fixed seat took the full path. A pre-existing DAgger test separately failed on both worker versions because its hard-coded v3 candidate budget had been superseded by `work-12000-v8`. Its bootstrap, query, retained-candidate, source-row and DAgger-row checks moved to the focused seat-routing suite and now verify the candidate identity declared by the live schema. The grandfathered pipeline suite shrank by 38 lines.

```sh
/home/tongshu/venv/bin/python -B -m unittest tests.v5.test_lite_score_astra \
  tests.v5.test_lite_score_policy tests.v5.test_record_evidence tests.v5.test_teacher_state_reuse \
  tests.v5.test_pipeline_contract.LiteJobTests.test_uncollected_seats_skip_candidate_generation \
  tests.test_validation_cadence -v
```

The final 15 affected checks passed in 2.907 seconds on Ubuntu. The [evidence archive](comparison.tar.gz) has SHA256 `8c59b6fe447f57b1db1712470bf46903a3c354caa7a219834a13495330b76f3b`. This single-game result does not establish that a complete three-format PPO phase and its validation fit the 432-second budget.
