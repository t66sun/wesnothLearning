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

## R3 — Adapted teacher strength evidence

**Status:** OPEN for strength acceptance. The complete native panel after the ambush execution repair has 168/168 completed jobs, zero faults, and 12 valid blocks / 12 distinct scenario families in each format. All three comparisons remain inconclusive: duel 95% interval [-0.75, 0.75], ffa4 [-0.107639, 0.125], team2v2 [-0.4375, 0.34375]. There are 53 turn-limit outcomes; candidate truncation counters do not measure game termination. The maintained teacher now stops its old plan on native ambush status 2005, with failing-before/passing-after native evidence. The 18 accepted fixed legal-board ranking cases remain valid for unchanged scoring, queries and combat. Neither tactical checks nor a fault-free panel prove maintained strength.

**Procedure:** reuse the completed panel and fixed-position evidence; do not repeat unchanged games. Any teacher change needs a concrete diagnosis and a predeclared independent development/validation design. Keep the 12-block / 12-family matching contract, full seat rotations, both team contexts, frozen opponent and final holdout reserve. Truncated or underfilled strength evidence stays inconclusive. The current evaluator requires CI lower bound > 0 for superiority; a separate maintained-strength/non-inferiority target has no declared margin and must be specified before another such experiment, not fitted to these results.

**Pass:** the smoke detects obvious tactical or runtime deterioration without claiming statistical non-regression; a full-strength claim requires the complete matching panel with the hold-out reserve untouched. Otherwise the status stays unverified and hypotheses are revised instead of adding seeds until a win.

**Evidence:** current full panel: `verification/teacher_strength_fixed_20261103/REPORT.md`; original failed panel: `verification/teacher_strength_20261103/REPORT.md`; ambush repair: `verification/teacher_ambush_20261103/REPORT.md`; fixed boards: `verification/teacher_immunity_20261103/REPORT.md`. Source, package, map, seed and result identities are preserved in those directories. No collection or training ran. R3 remains a native strength/transfer blocker.

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
