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

**Status:** FAIL at ordinary BC; all-format readiness and the complete loop remain unaccepted. The current v2 team-only branch (`bdecbbd`, seed 20261101, eight workers, 30 turns, 2048/1024 rows) reuses 40 parent games and completes the missing eight, all turn-limit truncated with zero recorded gameplay faults. Five additional batches commit 272 updates, reaching v10 at the declared batch cap after 631.25 s. Corpus 48/48 and coverage 94.21% pass; imitation fails at recruit 34/85 (40.00%), move 426/667 (63.87%) and attack 56/141 (39.72%). No pending training or runner error remains, but the v10 periodic validation has eight submitted tasks without final results and remains pending. PPO, final evaluation and export are NOT RUN. This is a partial team diagnosis, not full-loop acceptance.

**Fitting evidence:** the final exact 2048-row training read retains 37 families / 54 windows; train recruit/attack accuracy is only 54/126 (42.86%) / 162/361 (44.88%). Held-out recruit-type/slot matches are 48/85 and 60/85. Of 141 attacks, 56 predictions choose movement; restricting the winner to attack candidates yields only 82 exact matches, so both action-kind competition and within-kind ranking remain. Earlier fixed-batch original-loss and matched context probes establish incomplete fitting and generalization; the two context inputs remain rejected. No production optimizer, sampler or feature change is adopted. Evidence: `verification/team_bc_branch_20261102/REPORT.md`, `verification/team_bc_v2_20261102/REPORT.md`, `verification/recruit_context_v2_20261102/REPORT.md`.

**Current boundary:** native/lite transfer and teacher strength remain separate R3 concerns. The v2 experiments do not migrate historical v1 evidence or establish convergence. Compatible branch evidence reuse has 30 passing Ubuntu checks and now avoids recollecting the 40 inherited games (`verification/branch_teacher_evidence_20261102/REPORT.md`). Reader/faction fixes, redundant-read removal and validation-history reuse remain accepted; earlier controls are not matched runtime comparisons with this corpus/checkpoint. Historical evidence stays at its original paths.

**Procedure:** address held-out recruit-type and attack ranking without lowering any gate. Use the frozen v2 batch for bounded, matched diagnostics before collecting another corpus or adopting tuning. A future complete-loop run must freeze source, formats, seed, workers, row/game/time limits and unchanged panels. The accepted turn-limit wiring (`verification/training_turn_limit_20261102/REPORT.md`) and 13 deterministic runner handoff checks (`verification/bounded_final_20261102/REPORT.md`) prove wiring only; actual post-BC execution remains unverified.

**Pass:** all declared formats pass ordinary BC, commit at least two PPO updates, resume without repeating committed work, complete the required final panel and pass audited export. Record model/input identities, complete/faulted/truncated counts and stage durations. No forced PPO or automatic budget extension. Native strength remains outside this smoke.

**Evidence:** current v2 branch diagnosis, identities, complete metadata and limits: `verification/team_bc_branch_20261102/REPORT.md`; parent evidence: `verification/team_bc_v2_20261102/REPORT.md`. These do not replace failed all-format evidence in `verification/bounded_loop_20261101/REPORT.md` or historical v1 evidence in `verification/team_bc_readiness_20261102/REPORT.md`. No new post-BC or same-future acceptance is claimed.

## R3 — Adapted teacher maintained-strength acceptance

**Status:** RUNNING on Ubuntu from source `97d7d9d`, under the user-selected non-inferiority fallback. The fixed deadline is 2026-11-03 13:25:35 Asia/Shanghai; startup and frozen identities are recorded in `verification/teacher_noninferiority_20261103/STARTUP.md`. The two completed scoring repair rounds did not establish superiority; their complete native panels and tactical red/green evidence remain unchanged. The user selected a maximum loss of 5% of normalized official score for maintained strength. This new criterion is prospective and does not reclassify the old inconclusive panels. The candidate teacher remains source `9118fac`, digest `ad75d870ce68fa6b489ad922fd8bb3059e29bbe7626f296e74d2b6fad828c7d4`.

**Procedure:** follow `docs/r3_noninferiority_temp.md`. Freeze the committed source/archive, candidate, parent and derived-control packages, executable, entropy shim, rules/maps and all jobs before starting. The derived control preserves original scoring/strategy and adds only the candidate's native ambush execution compatibility; the historical parent archive stays read-only. Use fresh master seed 20261104, all 15 validation scenario families, 960 duel / 300 ffa4 / 180 team blocks (4560 games), complete seat rotations, both team contexts, eight workers and a six-hour deadline. Observe progress/faults only, analyze once at the fixed endpoint, and do not retry, replace seeds, tune or extend the run. No training or learning shards; final holdout maps remain untouched.

**Pass:** all planned jobs and blocks complete without faults, each format retains 15 scenario families, and each format's existing 95% scenario-cluster interval has normalized lower bound > -0.05. Divide duel/team score differences and interval endpoints by 3; FFA is already 0–1. All three formats must pass; the two team contexts retain their original equal-weight combined primary result and are also reported separately. Official 30-turn adjudications remain in the score and are counted separately from natural endings; missing/deadline-interrupted games are not draws. The production superiority and training gates remain unchanged. A budget-limited or statistically inconclusive panel leaves R3 open.

**Evidence:** the new panel will be archived at `verification/teacher_noninferiority_20261103/REPORT.md`, including the committed protocol, source/package identities, fixed schedule, raw results, both scoring summaries and resource cost. Prior superiority evidence stays at `verification/teacher_strength_surviving_slow_20261103/REPORT.md` and its linked predecessors. No maintained-strength result exists yet. R3 remains the item-5 native teacher transfer blocker.

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
