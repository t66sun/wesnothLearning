# R4 scenario floors reachable by the frozen roster — 2026-10-28

Issue #58, parent #48. Implementation `dfdf1e4` (`e240707` roster, `67d5ba7` probes, `dfdf1e4` stale fixture) on top of `ee8c2e2` (R10 merged). This closes the limitation the [first R4 acceptance](../ppo_refactor_r4_20261027/REPORT.md) recorded: the declared floors were arithmetically unreachable, so every panel and the BC gate had to end `insufficient_design`.

## Behaviour

`learning/schedule.py` now enumerates every distinct starting faction assignment the six frozen factions allow and uses it for the scored panels and for teacher collection:

- `starting_factions(players, format_name)` — duel 15 unordered pairs, FFA4 15 four-faction groups, team2v2 15 two-versus-two partitions written into the fixed `[1,2,1,2]` team layout.
- `evaluation_jobs` default roster becomes maps × faction designs instead of maps × three rotating blocks, so a final panel (30 blocks) reaches duel 30 / FFA4 15 / team2v2 15 distinct `scenario_family` values and a 12-block promotion panel reaches 12 in every format. Block counts and game counts are unchanged (60/120/240 final, 24/48/96 promotion), as is `min_blocks`, the `interval[0] > 0` pass rule and every floor in `min_distinct`.
- `calibration_jobs` passes an explicit legacy roster, so reward-reference games keep their original three-block faction rotation byte for byte.
- `scenario_factions(index, players, format_name)` cycles the same designs for `teacher_jobs` and `stock_teacher_jobs`. Teacher collection previously derived factions from `factions(index, players)`, which yields three assignments for duel/FFA4/team2v2 and capped a collected corpus at 6/9/9 families; a 12-game collection now spans 12 families in every format, so the BC gate's floor is reachable from planned games.
- `base_job` takes an optional explicit faction list; training rollouts, their `training_scenario` eligibility swap and the frozen training split are untouched.

## Revert proof

Both defects are pinned by checks that fail when the old code returns (Ubuntu, same extracted tree, `revert_ubuntu.sh`):

| Revert | Result |
| --- | --- |
| panel roster back to `faction_block` blocks | `tests.v5.test_evaluation_design…test_frozen_floors_and_existing_schedule_capacity` FAILED (6/3/3 versus the new 30/15/15) and `design_probe.py` FAILED with `failed: final-*` and `val000100-*` for all three formats |
| teacher roster without `scenario_factions` | `…test_teacher_games_reach_the_bc_scenario_floor` FAILED |
| both restored | `tests.v5.test_evaluation_design` 10 PASS |

Logs: [revert_panel](ubuntu/revert_panel.log), [revert_probe](ubuntu/revert_probe.log), [revert_probe.json](ubuntu/revert_design_probe.json), [revert_teacher](ubuntu/revert_teacher.log), [restored](ubuntu/restored.log).

## Ubuntu acceptance

Ubuntu 24.04 (`7.0.0-38-generic`), Python 3.12.3, torch 2.9.1+cpu; acceptance root `/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r4_20261029b`; frozen data reused read-only through a symlink ([environment](ubuntu/environment.log)).

- Source-only archive built with `git archive dfdf1e4`, `data/` removed and `SOURCE_REVISION` written: 7,799,296 bytes, SHA-256 `f4b2210b85bd90a4e8c3c810997a9d3e10bb894748bbae90f97ddd75d5831166`.
- `rerun_ubuntu.sh` verifies the archive hash, refuses an existing root, runs the affected groups and then `design_probe.py`.

| Check | Observed | Evidence |
| --- | --- | --- |
| evaluation design, cadence, schedule, selection, nomination, budget and teacher-protocol checks | 37 PASS, 2.995 s | [targeted](ubuntu/targeted.log) |
| planned final panels, 30 blocks | duel 60 games / 30 distinct, FFA4 120 / 15, team2v2 240 / 15 | [design probe](ubuntu/design_probe.json) |
| planned promotion panels, 12 blocks | 12 distinct in every format (24/48/96 games) | [design probe](ubuntu/design_probe.json) |
| planned teacher collection, 12 games | 12 distinct families in every format, gate `passed` | [design probe](ubuntu/design_probe.json) |

`design_probe.py` supplies synthetic wins so the comparator reaches its design branch; the probe asserts the planned scenario identities and the floor arithmetic, and its `comparison: passed` values are that arithmetic, not strength, corpus or convergence evidence. `src`/`game_family`/`split_rule` semantics are unchanged.

## Not run / not accepted

No game was played, no corpus was collected or rewritten, no optimizer step ran, no full suite ran and no strength or scenario-coverage acceptance is inferred. The BC gate is reachable by planned collection but still `insufficient_design` for any existing historical corpus, which R4 does not rewrite. The frozen 1.18.8 holdout maps stay the only final boards, so duel's 30 families are 2 boards × 15 faction pairs. Floors, `bc_aux` and the R5 qualified-rehearsal requirement are untouched; R5 remains data-blocked because the repository has no human or policy row shards distinct from the evaluation control.
