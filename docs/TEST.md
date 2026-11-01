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

**Status:** FAIL at BC on Ubuntu 2026-11-01. Source `5f86804` ran `tests/bounded_training_loop.py` for 558.33 s until duel reached the predeclared five-batch cap. Committed BC batches: 5/1/1; recorded complete games: 24/16/13, all turn-truncated, zero recorded faults. Duel reached its corpus/scenario targets but failed coverage and imitation (31.33% overall accuracy). Other formats last gated eight games each. PPO, resume, selection, final evaluation and audited export are NOT RUN. This is a training blocker; the full loop is not accepted. The candidate contract is now `work-12000-v7`, which postdates this run; a normal gated run under it is NOT RUN pending explicit authorization.

**Procedure:** diagnose coverage and held-out per-kind imitation using existing rows first. After repair and explicit execution instruction, ship a committed archive into a fresh Ubuntu directory; freeze three formats, seed, workers, row/game/batch/time caps and unchanged panel/gate thresholds. The existing runner records the limits and stops at the first incomplete stage. Later runner branches have not yet been exercised.

**Pass:** all declared formats pass ordinary BC, commit at least two PPO updates, resume without repeating committed work, complete the required final panel and pass audited export; record model/input identities, complete/faulted/truncated counts and each stage duration. No forced PPO or automatic budget extension. Native strength remains outside this smoke.

**Evidence:** `verification/bounded_loop_20261101/REPORT.md`, with raw plan, states, gates, jobs and checkpoint hashes, and the two replays `verification/teacher_coverage_20261101/REPORT.md` and `REPORT_v7.md`, which replay the frozen bounded-loop schedules on the exact committed decisions. The replay separates the two failures: label retention is counted by reason code per kind, and held-out fit is reported per kind as exact, same-kind, same-actor, same-destination and label-rank buckets. Retention over the same decisions rose from duel 1888/2602 to 2303/2602 (recruit 151/398 → 349/398, move 1043/1187 → 1076/1187, attack 364/687 → 548/687), ffa4 1399/2423 → 1754/2423 and team2v2 1802/3203 → 2035/3203, with replay determinism `ok` on all three. That is a measured retention gain, not acceptance: the gate's 0.90 overall and 0.80 per-class thresholds are still missed (duel 0.8851 overall, attack 0.7977; ffa4 0.7239; team2v2 0.6353), and no threshold, teacher, seed or training schedule was changed. The residual duel and team2v2 attack loss is moving attack — attack-own loses 6 of 377 and 1 of 272 intents — while the two larger formats remain generation-bound. No fresh same-future or post-BC evidence was obtained; L1's historical result does not accept this run.

## R3 — Adapted teacher strength evidence

**Status:** the adaptation itself is implemented, six value-level positions were checked, and a bounded smoke ran on the Ubuntu host 2026-10-31: 14 games, all `complete`, `truncated=0`, adapted versus frozen Astra differed by −1.5 rank points in duel, +0.2083 in ffa4 and −1.125 in team2v2, one block and one distinct scenario per format, therefore inconclusive for strength. Full legal-board teacher query/ranking and the complete 12-block comparison are NOT RUN. Tactical evidence and strength evidence stay separate.

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
