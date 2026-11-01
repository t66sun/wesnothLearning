# Acceptance plan

> Language: English | [中文](TEST_zh.md)

Updated 2026-11-01. This file holds only acceptance work that is still open. Accepted items leave it as a whole and stay as dated evidence under `verification/`; `docs/architecture.md` describes the current implementation, not its acceptance history.

Every item states what is open, the smallest Ubuntu procedure that would close it, the pass criteria and the evidence path. Status vocabulary: **PASS**, **FAIL**, **NOT RUN**, **REUSED** (existing evidence with matching identities). A check that cannot run is NOT RUN, never a skipped pass. Bounded smoke results label themselves inconclusive for strength, and no item here authorizes collection, formal training or tuning.

## Boundaries and shared inputs

- Ubuntu accepts; Windows provides reference only. Work in an isolated directory or temporary run. Frozen inputs, manifests, evidence and installed models remain read-only.
- Activate only cases whose owner changed. Every changed behavior needs an assertion that fails when reverted; missing fixtures or runtime mean NOT RUN.
- Reuse accepted evidence instead of duplicating it. No full faction/rules/worker/seed matrix, new corpus, long convergence run or repeated pressure test merely because code moved.
- Derived fixtures are prepared once with parent hashes and without editing historical evidence. A small chain proves wiring, not quality, promotion, convergence or strength.

## L1 — Reduced full-loop run

**Status:** FAIL on the Ubuntu host 2026-10-31, re-entered on the restored Astra route (`master` `5ac67d9`). Panel, PPO updates, stop/resume, the selection/export record and the same-future clause passed; final evaluation still scored no game. Measured: 40/40 duel Astra teacher games completed (4,139 eligible rows), 5 BC batches (268 updates) below the imitation gate (accuracy 0.401, cross-entropy 2.300 vs uniform 4.388), PPO forced with a recorded reason, 7 batches with 6–8 applied updates; SIGINT ignored, SIGKILL at `applied=3` (version 8, batch 8 pending) resumed and finished `ppo_complete` at version 12 without recomputing batches 0–7. The uninterrupted twin applied the same 7 batches and batches 8–11 matched exactly, so the same-future clause is verifiable and passes. All 120 final games faulted with `watchdog_timeout` at `turns 1`: one exported-policy decision cost ≈1.9 s while `vendor/arena/params.py:8` freezes `ACTION_TIMEOUT = 1.0`; the selection fell back to `last_ppo.pt` v12 and its export was recorded. That cause is fixed — the exported add-on carries `score_limit=24` and the scorer hoists its candidate-independent input, so eight duel games against an exported policy finished without a fault at most 234 ms per decision (`verification/action_budget_20261031/REPORT.md`) — so the item's remaining step is the evaluation re-run, which is NOT RUN and needs an explicit instruction.

**Procedure:** on an isolated source tree, freeze one lite configuration with the smallest panel that reaches BC, at least two applied PPO updates, one stop/resume from a committed-batch checkpoint and the final-evaluation entry. Record counts, seed, manifest and checkpoint identities before launch. Poll status/log every 30 minutes and retain anomalies; do not raise game counts, lower gates or edit frozen evidence during the run.

**Pass:** the run reaches final evaluation; both PPO updates commit; resuming from the saved boundary reproduces the uninterrupted future exactly where identities match; the selected checkpoint and its export are recorded; every stop reason is reported rather than hidden. Reduced-panel limits stay inconclusive for strength, and a failure remains a failure.

**Evidence:** `verification/acceptance_20261031_astra/REPORT.md` with identities, the stop/resume boundary, the same-future comparison of batches 8–11, the selection and export record, the native-budget faults and their clearing (`verification/action_budget_20261031/REPORT.md`); `verification/acceptance_20261031/L1/REPORT.md` remains the record of the earlier pre-restoration run.

## L2 — Ordinary gated all-format bounded loop

**Status:** ordinary readiness and the complete loop remain unaccepted. The previous all-format BC run passed coverage but failed imitation (`verification/bc_root_20261101/readiness/`). The family-reader and team-faction exposure defects are now repaired and verified (`verification/bc_admission_20261102/REPORT.md`, `verification/team_teacher_factions_20261102/REPORT.md`); the stale phase-runner fixture is also corrected with five passing checks, reusing 42 unaffected passes (`verification/phase_runner_fixture_20261102/REPORT.md`).

A fresh team-only ordinary BC experiment on source `cb4f03e`, seed 20261101, eight workers and 2048/1024 row limits exits naturally after about 21m08s under the predeclared 20-minute phase / 22-minute external cap. Thirty games complete, two are budget-interrupted, thirteen completed games are turn-truncated, and zero faults are recorded. Three batches commit 120 updates; the last model/gate covers 24/48 required games. Coverage passes at 92.59%, with every class above 80%, but imitation still fails: recruit 18.64%, move 52.91%, attack 13.89%. All six factions reach the exact training batch. Training recruit/attack accuracy is only 24.49%/25.37%, so the remaining problem includes training-set fitting, not only missing factions or generalization. No forced PPO, deadline extension, later stage or all-format pass is claimed. Evidence: `verification/team_bc_readiness_20261102/REPORT.md`. Full teacher strength is separately R3.

The frozen-batch original-loss curve now completes 600 additional updates in 671.2 s: train recruit/attack 71.43%/77.58%, validation 40.68%/37.04%. Recruitment still fails 60%; validation movement and CE deteriorate despite better training fit. This identifies initial underoptimization and remaining generalization loss, not ordinary readiness. A discarded full preflight read separately costs 11.90 s before the actual 11.57 s training read. Evidence: `verification/bc_learning_curve_20261102/REPORT.md`.

The redundant BC preflight read is now removed, with 29 passing affected Ubuntu checks and a failing-before/passing-after read-count regression. Resume reconstructs and validates the batch; no full-run speedup is claimed (`verification/bc_preflight_read_20261102/REPORT.md`).

The recruit-label audit reproduces all selected type/placement preferences (98 train, 59 validation); the full corpus has 348 recruits but the baseline batch retains 98. Matching validation type-count/boost contexts increase from 7/59 selected to 25/59 full-corpus. Target-row retention dominated the measured reader charge. Early fair allocation now releases unused targets: the same frozen 2048-row read retains 16 rather than 12 families, with about 25.4% lower process peak RSS, but takes 16.62 rather than 11.80 seconds and retains 91 rather than 98 recruits. All 65 affected cases have passing Ubuntu evidence, reusing 62 unchanged checks (`verification/bc_retained_targets_20261102/REPORT.md`). No post-change fitting pass is claimed. The label audit itself is read-only diagnosis (`verification/recruit_labels_20261102/REPORT.md`).

**Current rule boundary:** new lite runs use `expected_damage_v2` contextual retaliation. Old BC evidence remains tied to v1 source/corpus; no v2 ordinary readiness or teacher-strength pass exists. The versioned rule checks and six-case comparison are in `verification/retaliation_20261102/REPORT.md`.

**Recruit diagnosis:** the frozen v1 checkpoint has 33/59 inferior-type predictions versus only four tied-placement errors, with no indistinguishable label candidate. A fixed-family/2048-row probe retains 230 recruits instead of 98 and completes 598 updates, but held-out exact/type matches reach only 28/59 and 33/59. Overall accuracy is unchanged from the original 600-update control and imitation still fails; no production sampler change is adopted (`verification/recruit_ranking_20261102/REPORT.md`).

**Procedure:** recruit type generalization remains open; preserve every gate. The manual turn-limit wiring is now accepted with 50 passing Ubuntu checks (`verification/training_turn_limit_20261102/REPORT.md`). Thirteen deterministic Ubuntu checks cover the bounded runner's per-format PPO progress and completed final panels before export (`verification/bounded_final_20261102/REPORT.md`); actual post-BC execution remains unverified. A future complete-loop run must freeze source, formats, seed, workers, row/game/time limits and unchanged panel requirements. Reuse valid candidate/regression evidence.

**Pass:** all declared formats pass ordinary BC, commit at least two PPO updates, resume without repeating committed work, complete the required final panel and pass audited export. Record model/input identities, complete/faulted/truncated counts and stage durations. No forced PPO or automatic budget extension. Native strength remains outside this smoke.

**Evidence:** the current team diagnostic above does not replace the failed all-format run. Candidate generation/retention diagnosis is in `verification/bc_root_20261101/REPORT.md`; prior matched fitting probes remain `verification/bc_fit_20261102/REPORT.md`. Historical failures are retained in `verification/bounded_loop_20261101/REPORT.md` and `verification/teacher_coverage_20261101/`. No new post-BC or same-future acceptance is claimed.

## R3 — Adapted teacher strength evidence

**Status:** the adaptation itself is implemented, six value-level positions were checked, and a bounded smoke ran on the Ubuntu host 2026-10-31: 14 games, all `complete`, `truncated=0`, adapted versus frozen Astra differed by −1.5 rank points in duel, +0.2083 in ffa4 and −1.125 in team2v2, one block and one distinct scenario per format, therefore inconclusive for strength. Full legal-board teacher query/ranking and the complete 12-block comparison are NOT RUN, including the current expected_damage_v2 profile. Tactical evidence and strength evidence stay separate.

**Procedure:** compare frozen unadapted versus adapted Astra under the same rules, with paired initial maps, factions and roles, using one complete existing rotation block per format as a bounded smoke (predeclare games and turn cap). Reuse matching new-rule games where roles and schedules align. Truncated or underfilled results stay inconclusive. Claiming maintained or improved strength requires the unchanged complete 12-block validation/champion contract on a frozen hold-out validation schedule, never tuned on.

**Pass:** the smoke detects obvious tactical or runtime deterioration without claiming statistical non-regression; a full-strength claim requires the complete matching panel with the hold-out reserve untouched. Otherwise the status stays unverified and hypotheses are revised instead of adding seeds until a win.

**Evidence:** `verification/acceptance_20261031/R3/` holds the smoke schedule, identities and results labelled `r3-smoke`; the full panel needs its own dated directory.

## Execution and report

1. Identify the changed owner, the activated item and reused evidence. Predeclare maximum rows/windows/steps/games and numeric tolerances; implement only needed assertions or helpers; record real commands before running.
2. Run affected local deterministic checks, then the relevant Ubuntu checks. Actual games start only when the item is activated and separately authorized.
3. Stop once affected checks pass; after a fix rerun failed cases and changed dependents only.

One dated `verification/acceptance_<date>/REPORT.md`, with artifact subdirectories only when used:

```text
Scope: behavior/commit; activated items; exclusions and reasons
Identity: source/extension build, Ubuntu/Python/torch, catalog/profile/teacher/schema,
          input/model/optimizer hashes, seed/plan/cursor when relevant
Commands: executable, cwd, arguments, exit code, duration
Results: case | PASS / FAIL / NOT RUN / REUSED | assertion/counts | artifact
Reuse: original report + identity match; reuse is not a new run
Failure: first differing input/step, expected/actual, reproduction
Resources: rows/windows/families/decodes/steps/children; peak RSS/PSS if relevant
Gate: ready for named next phase / blocked; reduced panels inconclusive
Limits: unwritten tests, missing inputs/runtime, unproved quality/strength
```

No credentials in evidence. A failure, a missing required observation, a silent skip or an identity mismatch blocks the affected acceptance. Documentation-only changes run document, link and diff checks only. This plan has no runtime result.
