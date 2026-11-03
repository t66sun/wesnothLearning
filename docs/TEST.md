# Acceptance plan

> Language: English | [中文](TEST_zh.md)

Updated 2026-11-03. This file holds only acceptance work that is still open. Accepted items leave it as a whole and stay as dated evidence under `verification/`; `docs/architecture.md` describes the current implementation, not its acceptance history.

Every item states what is open, the smallest Ubuntu procedure that would close it, the pass criteria and the evidence path. Status vocabulary: **PASS**, **FAIL**, **NOT RUN**, **REUSED** (existing evidence with matching identities). A check that cannot run is NOT RUN, never a skipped pass. Bounded smoke results label themselves inconclusive for strength, and no item here authorizes collection, formal training or tuning.

## Boundaries and shared inputs

- Ubuntu accepts; Windows provides reference only. Work in an isolated directory or temporary run. Frozen inputs, manifests, evidence and installed models remain read-only.
- Activate only cases whose owner changed. Every changed behavior needs an assertion that fails when reverted; missing fixtures or runtime mean NOT RUN.
- Reuse accepted evidence instead of duplicating it. No full faction/rules/worker/seed matrix, new corpus, long convergence run or repeated pressure test merely because code moved.
- Derived fixtures are prepared once with parent hashes and without editing historical evidence. A small chain proves wiring, not quality, promotion, convergence or strength.

## L2 — Ordinary gated all-format bounded loop

**Status:** FAIL at ordinary BC; all-format readiness and the complete loop remain unaccepted. The current v2 team-only branch (`bdecbbd`, seed 20261101, eight workers, 30 turns, 2048/1024 rows) reuses 40 parent games and completes the missing eight, all turn-limit truncated with zero recorded gameplay faults. Five additional batches commit 272 updates, reaching v10 at the declared batch cap after 631.25 s. Corpus 48/48 and coverage 94.21% pass. Only recruitment fails the imitation gate (34/85 versus 51/85 required). Move 426/667 (63.87%) and attack 56/141 (39.72%) both clear the 35% minimum. No pending training or runner error remains, but the v10 periodic validation has eight submitted tasks without final results and remains pending. PPO, final evaluation and export are NOT RUN. This is a partial team diagnosis, not full-loop acceptance.

**Fitting evidence:** the final exact 2048-row training read retains 37 families / 54 windows; train recruit/attack accuracy is only 54/126 (42.86%) / 162/361 (44.88%). Held-out recruit-type/slot matches are 48/85 and 60/85. Of 141 attacks, 56 predictions choose movement; restricting the winner to attack candidates yields only 82 exact matches, so both action-kind competition and within-kind ranking remain. Earlier fixed-batch original-loss and matched context probes establish incomplete fitting and generalization; the two context inputs remain rejected. No production optimizer, sampler or feature change is adopted. Evidence: `verification/team_bc_branch_20261102/REPORT.md`, `verification/team_bc_v2_20261102/REPORT.md`, `verification/recruit_context_v2_20261102/REPORT.md`.

**Current boundary:** ordinary BC readiness is still open. The teacher met its separate maintained-strength criterion ([evidence](../verification/duel_landing_ni_20261103/REPORT.md)). The v2 experiments do not migrate historical v1 evidence or establish convergence. Compatible branch evidence reuse has 30 passing Ubuntu checks and now avoids recollecting the 40 inherited games (`verification/branch_teacher_evidence_20261102/REPORT.md`). Reader/faction fixes, redundant-read removal and validation-history reuse remain accepted; earlier controls are not matched runtime comparisons with this corpus/checkpoint. Historical evidence stays at its original paths.

**Procedure:** address held-out recruit-type and attack ranking without lowering any gate. Use the frozen v2 batch for bounded, matched diagnostics before collecting another corpus or adopting tuning. A future complete-loop run must freeze source, formats, seed, workers, row/game/time limits and unchanged panels. The accepted turn-limit wiring (`verification/training_turn_limit_20261102/REPORT.md`) and 13 deterministic runner handoff checks (`verification/bounded_final_20261102/REPORT.md`) prove wiring only; actual post-BC execution remains unverified.

**Pass:** all declared formats pass ordinary BC, commit at least two PPO updates, resume without repeating committed work, complete the required final panel and pass audited export. Record model/input identities, complete/faulted/truncated counts and stage durations. No forced PPO or automatic budget extension. Native strength remains outside this smoke.

**Evidence:** current v2 branch diagnosis, identities, complete metadata and limits: `verification/team_bc_branch_20261102/REPORT.md`; parent evidence: `verification/team_bc_v2_20261102/REPORT.md`. These do not replace failed all-format evidence in `verification/bounded_loop_20261101/REPORT.md` or historical v1 evidence in `verification/team_bc_readiness_20261102/REPORT.md`. No new post-BC or same-future acceptance is claimed.

**Candidate coverage under v9 remains unmeasured across formats.** The Sablestone decision recovers eight recruit choices and displaces seven partial moves. Compare matched v8/v9 teacher-intent coverage by class on frozen inputs before using v9 as readiness evidence. Preserve the 90% overall and 80% per-class coverage gates and the original imitation thresholds. Record candidate identities with the L2 result. [Fixed-board Ubuntu evidence](../verification/recruit_probe_priority_20261103/REPORT.md)

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
