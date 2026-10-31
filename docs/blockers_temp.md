# Remaining blockers and high-impact risks

Static review date: 2026-10-31 (Asia/Shanghai).
Source: `f563cade05eabeb6a45f48ce0dc476654cf71ae4`, initially clean `master` working tree.

Scope: the training/coordinator, BC/PPO, recurrent policy, shared Lua candidate generation, lite policy execution, combat and deployment paths. This is a targeted static review, not an exhaustive proof of correctness. No tests, games, collection, training or remote acceptance were run. Existing reports are cited as historical evidence, not fresh acceptance. The original review wrote only this report. The subsequently authorized implementation of items 1-4 and 8 is recorded below; the other items remain proposals.

P1 means a direct threat to usable policy behavior or acceptance; P2 means a concrete scaling cost or an unresolved quality prerequisite. Implementation facts, conditional consequences and missing evidence are distinguished below. Temporary documentation is English-only under the repository rules.

## 1. Completed — Balanced candidate quotas and refill

Implemented in `lua/candidate_selection.lua`, called by the shared generator: combat/recruit/move each reserve up to 12 unique actions, with actor/type diversity, deterministic refill to 36 actionable entries, and a separate end-turn slot (37 maximum). Sparse pools are not padded with duplicates. Crowded-board and quota regressions pass on Ubuntu. Native timing at the new limit remains pending in TEST.md C1; no strength claim.

## 2. Completed — One candidate set in training and deployment

Removed bot prefix truncation and export-only score limits. Lite, native collection and deployed bots consume the shared Lua selection. Candidate schema/version records the change; old export/checkpoint schemas are rejected by existing checks rather than silently resumed. The numerical audit accepts a full current budget (37) and still exercises larger stress fixtures. Evidence for both items: `verification/candidate_budget_20261031_exact37/REPORT.md`.

## 3. Completed — One bounded scorer on every native policy seat

Removed the remaining score limit and the per-caller candidate budget: `lua/candidates.lua` now decides generation work itself, no caller passes `budget_ms`, and every native policy seat — rollout, nomination, collection, deployment, lite host and benchmark — scores the complete shared set (37 candidates) under the unchanged one-second native timeout. Generation is charged, so the pool no longer grows without bound on larger visible armies, and generation is timed separately from scoring (`generate_ms`, `score_ms`) so a dense midgame decision can be judged stage by stage.

Evidence: `verification/candidate_work_budget_20261031/REPORT.md` plays two seeded games per format (duel, ffa4, team2v2) on a fixed dense synthetic map with a frozen 1 s budget and records decision, generation and scoring percentiles. Remaining limits: those games use a randomly initialized exported policy on a compact map, so this is a latency and contract acceptance, not a strength, convergence or final-evaluation result; item 9 stays open, and native rule transfer (item 5) is untouched.

## 4. Completed — Deterministic charged work budget bounds the nested generation work

The candidate generator no longer accepts a millisecond argument or counts `expired()` calls. `lua/candidates.lua` charges a fixed work budget (`work-12000-v5`): entity scans, threat-map reach expansion and retained threats, tactical goals, scored reach positions, eagerly rated destinations, paths, native probes and combat forecasts each cost work, and each stage carries its own cap (28 `find_reach`, 8 `find_path`, 24 `ai.check_recruit`, 32 `ai.check_attack`, 32 `ai.check_move`, 16 forecasts). Cuts are decided by work and caps only, never by elapsed time, so the candidate set stays deterministic for a given observation. End turn, recruits and adjacent attacks are generated before the threat map and movement, and features for the retained set are always materialized from the bounded entity lists. Tests assert the caps, a cut dense generation, and identical actions across repeated runs and an advanced clock.

Evidence: `verification/candidate_work_budget_20261031/REPORT.md` measures generation and scoring separately on the dense map; `tests/v5/test_candidate_pool_budget.py` holds the bounded-work contract. Remaining limits: `WORK.total` is the only calibrated value, so larger boards than the measured map are bounded but unmeasured.

## 5. P1 — Lite tactical values remain structurally different from native play

**Evidence:** `engine_lite/src/combat.rs:40-46,74-85` uses rounded deterministic expected damage with a 10% uplift and applies poison/slow whenever hit chance is positive and the target survives. `counter_weapon` at lines 34-37 chooses raw damage times strikes among matching ranges, without the attacking unit's resistance or weapon specials. `docs/architecture.md` sections 4 and 13 explicitly retain approximate rules and unaccepted native semantics.

**Impact:** kill thresholds, risk-taking, status reliability and retaliation choices learned in lite need not transfer to native Wesnoth. This is an intentional surrogate-rule design, not a newly discovered accidental change; it is still a major risk when the objective is native playing strength. Deterministic damage equality within lite does not establish equality of expected tactical utility under native combat.

**Repair direction:** prioritize native comparisons on common training-unit tactical situations (kill/death thresholds, slow/poison and alternative retaliation weapons). Either close the material semantic gaps or explicitly train/adapt and select on native evidence. Keep lite-only strength claims separate, and do not discard approximation guards to get through startup.

## 6. P2 — BC samples windows in proportion to their number of decisions

**Evidence:** `learning/bc.py:23-35` samples rows with `BCSampler`, then maps each sampled row back to its entire window. `learning/data.py:266-283` chooses a source/engine/family and then a row uniformly within that pool. `learning/bc.py:38-58` averages each selected window equally, but does not correct the probability by which it was selected.

**Impact:** within a fixed source/engine/family pool, a 200-decision window is selected ten times as often as a 20-decision window. The per-selection mean does not remove this length bias. Sampling with replacement also permits the same window several times in a logical batch while others remain unseen. The docstring that each real decision counts once and the equal-window explanation therefore overstate the actual coverage; decision totals/effective passes count repeated visits rather than unique coverage. This can spend disproportionate BC cost on long, action-heavy positions and distort the intended learning balance.

**Repair direction:** build the quota-aware sampler over windows, or weight inverse to window selection probability. State whether replacement is intended and report unique versus repeated visits separately. Add a sampler-distribution/coverage assertion with unequal-length windows; preserve the existing source and family quotas.

## 7. P2 — Historical scene encoding repeats across training microbatches and frozen-policy turns

**Evidence:** `learning/model.py:69-101` traverses and encodes every supplied history row, including the no-gradient prefix. Its caches are explicitly local to one `context()` call. `learning/bc.py:40-46` and `learning/ppo.py:152-175` invoke the model repeatedly for microbatches (PPO also invokes rehearsal). `learning/lite_policy.py:64-70` caches one memory context per history-length/turn key but reconstructs that context from the complete history whenever the key changes.

**Impact:** the eight-turn replay setting bounds differentiable recurrence, not total prefix encoding work. Shared histories save work within a call, but repeated calls redo entity attention and board encoding for those same old turns. Frozen-policy whole-game prefix work grows quadratically with turn count if history grows one row per turn. Training pays repeated prefix costs even before any optimizer update changes the weights. The current 30-turn cap limits magnitude; no percentage slowdown is claimed.

**Repair direction:** for frozen rollout weights, advance GRU/slot state incrementally as Lua already does. For training, reuse only safe detached prefix computations within an unchanged-weight boundary, retaining gradients for the active replay suffix and invalidating at optimizer steps. Compare memory/context outputs before adopting the optimization; never reuse old-policy hidden state across weight updates.

## 8. Completed — Coordinator appends job results without rereading the log

`learning/common.py` gains `repair_tail`: it reads one byte for a terminated log and otherwise scans backwards in 1 MiB chunks, so a repair costs the interrupted tail plus one chunk. `learning/coordinator.py` repairs each log once per broker call and appends every later result; `learning/sample.py` uses the same helper in `collect`. `tests/test_experiment.py` asserts exactly one repair per log across 15 appended results, byte-level tail cases including a multi-chunk tail, and the `collect` call site; point mutations of both call sites and of the chunk loop fail those assertions. Evidence: `verification/log_tail_repair_20261101/REPORT.md`. Limits recorded there: no games or training, no read-volume assertion in the repository, concurrent writers and long-run dispatch latency unmeasured.

## 9. P1 — End-to-end final evaluation acceptance is still open

**Evidence:** `docs/TEST.md`, L1, records that the restored-Astra reduced run reached updates/resume/selection but its 120 final games all faulted. It separately records the subsequent action-budget fix and says the final-evaluation rerun is NOT RUN. `verification/action_budget_20261031/REPORT.md` measures eight short duel games using a seeded policy, not the selected trained checkpoint across the required final panel.

**Impact:** the previous timeout cause has a bounded fix; it should not be reported as universally still broken. However, a usable selected-checkpoint final-evaluation chain has not yet been established by that evidence, and there is no measured coverage here of dense midgames or the other two formats. This is an acceptance blocker, not a static proof of a current execution failure.

**Repair direction:** after resolving the deployment selection contract, explicitly authorize and run the remaining isolated Ubuntu final-evaluation step using frozen source/checkpoint identities. Reuse the existing resume evidence, preserve failed history, and report actual complete/faulted/truncated counts without lowering the panel or timeout requirements.

## 10. P2 — Teacher quality and normal BC-to-PPO readiness remain unproven

**Evidence:** `docs/TEST.md`, R3, leaves full legal-board teacher ranking and the complete 12-block adapted-versus-frozen comparison NOT RUN. Its 14-game smoke is explicitly inconclusive and includes negative observed rank differences in duel and team2v2. L1 records five BC batches below the imitation gate followed by explicitly forced PPO. `docs/architecture.md` section 13 states that no convergence/playing-strength claim exists.

**Impact:** value-level correctness of the adapted teacher does not establish action-ranking quality. An effective PPO wiring run also does not show that normal BC gates will be reached at affordable cost. Scaling the current setup before separating teacher quality, candidate coverage and imitation fit risks paying for more data that reproduces the same limitation. The smoke is too small to establish teacher regression, and the reduced BC run is too small to establish non-convergence.

**Repair direction:** first diagnose per-kind label coverage and held-out imitation fit using existing eligible rows and the deployment-matched candidate contract. Then, only when explicitly authorized, complete the paired teacher-quality panel and ordinary gated training evidence. Keep forced-PPO smoke results distinct from readiness; do not weaken the gates or increase seeds opportunistically.

## 11. P1 — Add an approximately one-hour complete training-loop test

**Status:** planned, NOT RUN. This is a requested follow-up test plan; this document edit does not launch it. Run after the relevant repairs with the candidate contract frozen.

**Purpose:** exercise the complete operational chain on Ubuntu: initialization/calibration, BC and its ordinary gate, PPO rollouts and at least two committed updates, checkpoint stop/resume, validation/selection, final evaluation, and audited export. Use a manually bounded smoke profile to expose integration failures and actual training cost; one hour cannot establish convergence or playing strength.

**Procedure:** ship a committed source archive to a fresh dated directory on cpuServer and record its hash. Reuse compatible frozen rules, eligible teacher/human data and existing acceptance evidence. Before launch, explicitly freeze the formats (target all three), shared worker count, seed, game/turn limits, BC row/window/update caps, PPO batch/update caps and evaluation schedule. Use the smallest supported workload that preserves the ordinary gates and required panel sizes; do not silently change configuration validators. Budget roughly 5 minutes for preparation/calibration, 20 for BC, 15 for PPO including one committed-boundary stop/resume, 15 for validation/final evaluation and 5 for export/reporting, with an overall approximately 60-minute wall-clock limit. Treat these as stage ceilings, not promises that the gates will pass in that time. Reserve evaluation/export time rather than letting BC consume the entire run.

**Pass criteria:** every declared format reaches all stages; the ordinary BC gate passes; at least two PPO updates commit; resume continues from the recorded boundary without replaying committed work; the selected checkpoint completes its required evaluation and exports with the current sequence-parity audit. Record completed/faulted/truncated games, training updates, gate results, elapsed time by stage, source/rule/model identities and the actual candidate budget. Reuse matching same-future evidence where valid. If a gate or required panel cannot finish inside the cap, record the exact incomplete stage as FAIL/NOT RUN as appropriate, rather than forcing PPO, reducing acceptance criteria or extending the run automatically. Any reduced-format diagnostic must be identified as partial, not a completed all-format loop.

**Repair direction:** implement only the bounded smoke orchestration/configuration needed to exercise the existing pipeline, then run this test when explicitly activated. Save new commands and results under a new dated verification directory. Use the first concrete failure to guide repair; keep this short loop distinct from the formal strength evaluation in items 9-10.

## Suggested order

The common deployed candidate contract and its bounded decision budget across native paths are settled (1-4). Close the final-evaluation acceptance gap (9) with that contract frozen. In parallel planning, address the measurable training-cost causes (6-8). Treat native rule transfer and teacher/BC quality (5,10) as prerequisites for a native-strength claim, not as issues that a successful smoke can clear. Finish with the bounded complete-loop test (11), recording any stage that cannot complete within its one-hour budget.

This report proposes repair directions only. It does not authorize implementation, collection or training, and it does not replace the resident acceptance plan.
