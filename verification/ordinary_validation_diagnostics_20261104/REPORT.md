# Reward horizons on ordinary validation jobs

The ordinary BC and PPO validation producer now tags the policy-versus-control games it schedules with `meta.phase=validation`. The existing collector predicate uses this field to retain policy horizon diagnostics for the reward controller. The Ubuntu regression reproduced the missing field before the fix, and all 18 affected simulated checks passed afterward.

## Observed version-three inputs

Source `7665583e9a57e1d754e6d53bb16bfd02e7d055cf` ran the strict loop at `/home/tongshu/acceptance/bounded_loop_v6_strict_20261104/runs/bounded_loop`. All 18 scheduled `val000003` games lacked the validation phase tag. Every completed ordinary validation result lacked the `reward_diagnostics` field. The reference schedules carried their own `reward_reference` tag. [Original schedules and comparison/control reports](v3-comparisons.tar.gz) · [Filtered job metadata, extraction code and test outputs](checks.tar.gz)

| Format | Completed validation games | Scored blocks | Completed references with diagnostics | Recorded control evidence |
| --- | ---: | ---: | ---: | --- |
| Duel | 6/6 | 3/3 | 12/12 | Six missing policy horizons |
| FFA | 4/4 | 1/1 | 12/12 | Four missing policy horizons |
| Team | 1/8 | 0/1 | 0/12 | Incomplete rotation block |

The controller uses complete horizons, matched rotation blocks and at least four independent reference families for each stratum to decide whether evidence supports an adaptive coefficient change. A missing block or insufficient reference support can legitimately yield an inconclusive control report. Operational panel completion is determined separately from the actual comparison results.

## Ubuntu verification

| Revision | Commit | Archive SHA256 |
| --- | --- | --- |
| Regression on the strict-run source | `0ff54063b79904274d0a6e83b0dd52f89af9d1c1` | `55aa0dafab2711da6716a736d2f474bfcd3fef88f92d739df76ab989c52a746b` |
| Producer fix | `e5739069d8a03f89b2ab3b60474f76f4447cf2e6` | `6fecfd2811daf2f75bca9852090aa222315b42f91b613b27570df72d3f364a50` |

Each revision was shipped with `git archive --format=tar.gz --output=<archive> HEAD -- learning lua engine_lite tests vendor benchmarks`. The local and Ubuntu SHA256 values matched. Fresh directories were `/home/tongshu/acceptance/validation_evidence_red_20261104` and `/home/tongshu/acceptance/validation_evidence_green_20261104`. Both used the existing filtered rule catalog at `/home/tongshu/acceptance/bc_v6_readiness_20261103/data/rules/1.18.8-combat-filtered`, SHA256 `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`, and one thread each for OMP, OpenBLAS and MKL.

```sh
nice -n 19 /home/tongshu/venv/bin/python -m unittest \
  tests.test_validation_cadence.ValidationCadenceTests.test_only_ordinary_validation_jobs_request_reward_diagnostics -v
```

The baseline exited 1 in 0.035 s. Both ordinary validation calls produced `False` under the production collector predicate. The separate nomination and final schedule checks produced the expected `False`.

```sh
nice -n 19 /home/tongshu/venv/bin/python -m unittest \
  tests.test_validation_cadence.ValidationCadenceTests.test_only_ordinary_validation_jobs_request_reward_diagnostics \
  tests.test_validation_cadence.ValidationCadenceTests.test_validation_sizes_paired_contexts_and_no_unready_opening \
  tests.test_validation_cadence.ValidationCadenceTests.test_reduced_team_validation_does_not_weaken_formal_evaluation \
  tests.v5.test_pipeline_contract.RewardMetricsTests tests.v5.test_final_nomination -v
```

The fixed revision exited 0 with 18 checks passing in 3.961 s. The regression observed `True` for ordinary BC and PPO validation and `False` for the separate nomination and final schedules. The checks exercised metadata routing, synthetic horizon consumers, frozen selection reuse and invalid/incomplete evidence handling. This change's verification used zero games and zero optimizer steps. Post-fix horizon completeness under an actual run remains unmeasured.
