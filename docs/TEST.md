# Acceptance plan

> Language: English | [中文](TEST_zh.md)

Updated 2026-10-31. This file holds only acceptance work that is still open. Accepted items leave it as a whole and stay as dated evidence under `verification/`; `docs/architecture.md` describes the current implementation, not its acceptance history.

Every item states what is open, the smallest Ubuntu procedure that would close it, the pass criteria and the evidence path. Status vocabulary: **PASS**, **FAIL**, **NOT RUN**, **REUSED** (existing evidence with matching identities). A check that cannot run is NOT RUN, never a skipped pass. Bounded smoke results label themselves inconclusive for strength, and no item here authorizes collection, formal training or tuning.

## Boundaries and shared inputs

- Ubuntu accepts; Windows provides reference only. Work in an isolated directory or temporary run. Frozen inputs, manifests, evidence and installed models remain read-only.
- Activate only cases whose owner changed. Every changed behavior needs an assertion that fails when reverted; missing fixtures or runtime mean NOT RUN.
- Reuse accepted evidence instead of duplicating it. No full faction/rules/worker/seed matrix, new corpus, long convergence run or repeated pressure test merely because code moved.
- Derived fixtures are prepared once with parent hashes and without editing historical evidence. A small chain proves wiring, not quality, promotion, convergence or strength.

## N1 — Native terminal capture

**Status:** implemented, NOT RUN; a fixed scenario helper is unwritten. Blocks only the new native terminal path, not lite. The 2026-10-30 sweep could not start it: the reference host has no native 1.18.8 install (`.runtime/` absent).

**Procedure and pass:** one fixed native 1.18.8 early-elimination/endgame scenario capped at five turns plus the existing truncation counterexample. Actual initial, eliminated and terminal events preserve surviving sides and real own HP; bootstrap absorption only for a real terminal. Failure or truncation cannot invent a terminal. Missing events mean missing evidence, not zero-valued success. Diagnostic rows enter neither actor/BC/PPO shards nor memory writes. Record raw events, command and identities in `N1/`; no native rules or performance matrix.

## L1 — Reduced full-loop run

**Status:** NOT RUN. The historical reduced chain covered duel BC → PPO → resume → final; uninterrupted same-future comparison, scheduled mid-run ticks and all-format coverage remain unproven. Nothing started on 2026-10-30: no runtime and no run authorization.

**Procedure:** on an isolated source tree, freeze one lite configuration with the smallest panel that reaches BC, at least two applied PPO updates, one stop/resume from a committed-batch checkpoint and the final-evaluation entry. Record counts, seed, manifest and checkpoint identities before launch. Poll status/log every 30 minutes and retain anomalies; do not raise game counts, lower gates or edit frozen evidence during the run.

**Pass:** the run reaches final evaluation; both PPO updates commit; resuming from the saved boundary reproduces the uninterrupted future exactly where identities match; the selected checkpoint and its export are recorded; every stop reason is reported rather than hidden. Reduced-panel limits stay inconclusive for strength, and a failure remains a failure.

**Evidence:** new dated `verification/<run>_<date>/REPORT.md` with commands, counts, identities, checkpoint/resume trace, final-evaluation entry and resource readings.

## R3 — Adapted teacher strength evidence

**Status:** the adaptation itself is implemented and six value-level positions were checked; full legal-board teacher query/ranking and a matched strength comparison are NOT RUN, and the 2026-10-30 sweep had no runtime to start one. Tactical evidence and strength evidence stay separate.

**Procedure:** compare frozen unadapted versus adapted Astra under the same rules, with paired initial maps, factions and roles, using one complete existing rotation block per format as a bounded smoke (predeclare games and turn cap). Reuse matching new-rule games where roles and schedules align. Truncated or underfilled results stay inconclusive. Claiming maintained or improved strength requires the unchanged complete 12-block validation/champion contract on a frozen hold-out validation schedule, never tuned on.

**Pass:** the smoke detects obvious tactical or runtime deterioration without claiming statistical non-regression; a full-strength claim requires the complete matching panel with the hold-out reserve untouched. Otherwise the status stays unverified and hypotheses are revised instead of adding seeds until a win.

**Evidence:** `verification/acceptance_<date>/R3/` with the comparison schedule, identities, result and an explicit tactical/smoke/full-panel label.

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
