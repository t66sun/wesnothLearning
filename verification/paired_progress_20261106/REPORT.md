# Paired BC/selected/latest progress and unified acceptance

Issue #222 now distinguishes BC endpoint, selected, latest complete and pending
updates in final reports. The holdout score belongs only to selected. Independent
`python -m learning.progress plan/run/report` commands provide an explicit-budget
comparison of all three complete policies on matched validation scenarios.

Planning starts no games. It freezes checkpoint identities, Lua and Lite tensor
exports, opponent/rule/source identities, schedules and the declared budget in a
new directory outside the source run. Execution checks those pins and starts no
optimizer or training-data writer. At twelve blocks the three-role game budgets
are 72 duel, 144 FFA and 288 team. Both team contexts receive equal weight.
No automatic training budget, selection or holdout behavior changes.

Reports compare normalized **own** points against BC, with scenario-cluster
paired bootstrap intervals. Faults, missing replies, insufficient scenes and a
complete interval crossing zero remain distinct outcomes. Repeated seeds on one
physical scenario do not increase the independent scenario count. A pending
optimizer update is reported separately and cannot become latest-complete.

## Final acceptance

The final combined Ubuntu suite passes **111 tests in 20.889 seconds** at source
`6fc8d939255621573f7e355d1f77bb24d76694e1`. [final.log](final.log)

The checks cover the actual final-report entry point, explicit planning and
execution orchestration, real `FrozenPolicies` loading and exact tensor equality
for all three exports, immutable source-run files, all formats' normalized
scores, complete/inconclusive/missing/fault cases, repeated-scene clustering,
unmatched seed/opponent and holdout rejection, and frozen schedule tampering.
The match collector is replaced with deterministic replies in the orchestration
fixture; these are not newly played strength games.

The suite also integrates the accepted nomination, trend-budget, PPO scenario
coverage, scenario identity/no-drop, horizon/GAE and resume-counter contracts from
#222, #223 and #224. One existing bounded-runner fixture deliberately prints
`FAIL BC execution or bounded batch/time limit`; the unittest outcome is `OK`.

Independent review before merging #223 reran its 31 Ubuntu checks in 10.129
seconds ([review_223.log](review_223.log)); #224's 16 checks reran in 1.153
seconds ([review_224.log](review_224.log)). Reviewed production/diagnostic bytes
matched their recorded green sources. Recomputing #224's objective summary
produced exactly its recorded SHA-256
`b9fafe66fb5a30ef91a3292fe5b4cd3827dc09c31bce8f5fab13f229f9320fc6`.

## Preserved failures and limits of earlier checks

- Source `e06935dc5b7e5e14bd99c14c6fde125425467554`: the original final-report
  identity assertion fails because the report has no `checkpoint_roles`.
  [identity_red.log](identity_red.log)
- Source `17c391842f351460e83469bd67111414c7ed8b13`: 32 focused checks pass
  ([initial_green.log](initial_green.log)); source
  `f49ac015c627007262812e42e6ffe350c6bad9f2` passes the initial 111-check integration
  ([initial_integration.log](initial_integration.log)). Those fixtures replaced
  the collector and did not yet exercise the real tensor loader.
- Review found the independent planner had exported Lua weights without the
  `model.pt` required by Lite. Source
  `e5dca0fc95487f874d3ecfbf101c4543f6357479` adds the real loader assertion and
  reproduces its missing-file error ([loader_red.log](loader_red.log)). This is
  a genuine implementation fault missed by the earlier limited fixtures.
- Final source `6fc8d939255621573f7e355d1f77bb24d76694e1` freezes minimal inference
  tensors alongside each addon; the complete suite including that boundary
  passes. No prior failure log, assertion or acceptance gate was removed.

## Read-only recomputation of real recorded matches

[recompute_recorded.py](recompute_recorded.py) runs the new paired-report logic
over the previously frozen 120 BC games and their 120 latest-PPO counterparts.
It checks BC/latest checkpoint hashes against the original anchor identities.
Selected has no matched validation replies in this dataset: its empty cells are
explicitly unmeasured, and no final holdout result is substituted.

| Format | Latest minus BC normalized own score | 95% paired interval | Conclusion |
| --- | ---: | --- | --- |
| duel | -0.0833333333 | [-0.3194444444, +0.1527777778] | complete, inconclusive |
| team2v2 | +0.0173611111 | [-0.0659722222, +0.0937500000] | complete, inconclusive |

Both have twelve complete, distinct scenes and zero missing/faulted matches.
The new calculations match the original audit within `1e-12`.
[recomputed.json](recomputed.json), [recomputed.log](recomputed.log).
Output SHA-256: `ad63286ee66e4724bec2b6a7c245a7d6e20b09bc395e2d8dd71745e8632c0c62`.
These unchanged results do not establish PPO improvement or regression.

## Reproduction identities and commands

All execution took place on Ubuntu `cpuServer` using Python 3.12.3. Each source
was committed and shipped as a `git archive` tarball into a fresh directory;
the host has no Git checkout. Existing frozen maps were linked from
`/home/tongshu/myDev/wesnothLearning/WesnothLearning/rules/1.18.8`.

| Stage | Directory under `/home/tongshu/acceptance/` | Archive SHA-256 |
| --- | --- | --- |
| Identity red | `issue222_progress_red_20261106` | `c794a0304cb413cf71f155bb8ae4a18dabbe9b587cc809c803905274d92db8e8` |
| Initial green | `issue222_progress_green_20261106` | `b3bab210dcf5cc747a25eafd9c8118cecfc70851807629e67cd44f88a40123aa` |
| Initial integration | `issue222_progress_integrated_20261106` | `ac1514735b4af7ad9a36bebea8b08aabf91db057e8b6ccffb91a8007847fc81d` |
| Loader red | `issue222_progress_loader_red_20261106` | `40561fd6148ef8464b98ef67f8500081a401d4dada0b81d20e2dd83dac8f52c7` |
| Final accepted | `issue222_progress_final_20261106` | `88776969fefc0c0807590b1d1ad0d94e2dc0815cb57007e3f7676465a87883a3` |

```sh
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PWD:/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension"
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
/home/tongshu/venv/bin/python -m unittest \
  tests.v5.test_progress_report tests.v5.test_trend_budget tests.v5.test_pipeline_schedule \
  tests.test_validation_cadence tests.test_training_revision tests.v5.test_final_nomination \
  tests.v5.test_selection tests.v5.test_evaluation_design tests.v5.test_final_budget \
  tests.v5.test_pipeline_contract.ReportSchemaTests tests.v5.test_ppo_scenario_coverage \
  tests.v5.test_batch_eligibility tests.v5.test_scenario_identity tests.v5.test_training_turn_limit \
  tests.v5.test_ppo_resume_counters tests.test_schedule tests.v5.test_critic_horizon \
  tests.v5.test_reward_row_schema
/home/tongshu/venv/bin/python verification/paired_progress_20261106/recompute_recorded.py \
  /home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/runs/formal_30h_scratch \
  verification/ppo_architecture_audit_20261106/bc_anchor FRESH_recomputed.json
```

No Windows tests, new matches, corpus collection or formal training ran. Synthetic
unit fixtures include bounded optimizer updates from existing resume tests. The
new progress planner's native execution, wall-time cost and strength outcomes
have not been measured. #224's chosen 30-turn training objective is still a
separate production implementation task (#235), not an accepted reward rewrite.
AGENTS.md and all frozen historical inputs/evidence were untouched.
