# Remaining blockers and high-impact risks

Static review date: 2026-10-31 (Asia/Shanghai).
Source: `f563cade05eabeb6a45f48ce0dc476654cf71ae4`, initially clean `master` working tree.

Scope: the training/coordinator, BC/PPO, recurrent policy, shared Lua candidate generation, lite policy execution, combat and deployment paths. This is a targeted static review, not an exhaustive proof of correctness. No tests, games, collection, training or remote acceptance were run. Existing reports are cited as historical evidence, not fresh acceptance. The original review wrote only this report. Items 1–10 are complete within their stated acceptance scopes. Item 11 holds the remaining bounded full-loop test.

P1 means a direct threat to usable policy behavior or acceptance; P2 means a concrete scaling cost or an unresolved quality prerequisite. Implementation facts, conditional consequences and missing evidence are distinguished below. Temporary documentation is English-only under the repository rules.

## 1. Completed — Balanced candidate quotas and refill

Implemented in `lua/candidate_selection.lua`, called by the shared generator: combat/recruit/move each reserve up to 12 unique actions, with actor/type diversity, deterministic refill to 36 actionable entries, and a separate end-turn slot (37 maximum). Sparse pools are not padded with duplicates. Crowded-board and quota regressions pass on Ubuntu. Seeded native timing passes at the current limit (`verification/native_inference_20261102/REPORT_seeded.md`); no strength claim.

## 2. Completed — One candidate set in training and deployment

Removed bot prefix truncation and export-only score limits. Lite, native collection and deployed bots consume the shared Lua selection. Candidate schema/version records the change; old export/checkpoint schemas are rejected by existing checks rather than silently resumed. The numerical audit accepts a full current budget (37) and still exercises larger stress fixtures. Evidence for both items: `verification/candidate_budget_20261031_exact37/REPORT.md`.

## 3. Completed — One bounded scorer on every native policy seat

Removed the remaining score limit and the per-caller candidate budget: `lua/candidates.lua` now decides generation work itself, no caller passes `budget_ms`, and every native policy seat — rollout, nomination, collection, deployment, lite host and benchmark — scores the complete shared set (37 candidates) under the unchanged one-second native timeout. Generation is charged, so the pool no longer grows without bound on larger visible armies, and generation is timed separately from scoring (`generate_ms`, `score_ms`) so a dense midgame decision can be judged stage by stage.

Evidence: `verification/candidate_work_budget_20261031/REPORT.md` plays two seeded games per format (duel, ffa4, team2v2) on a fixed dense synthetic map with a frozen 1 s budget and records decision, generation and scoring percentiles. Remaining limits: those games use a randomly initialized exported policy on a compact map, so this is a latency and contract acceptance, not a strength, convergence or final-evaluation result. Item 9 records the separate selected-checkpoint evaluation. Native rule transfer is covered separately in item 5.

## 4. Completed — Deterministic charged work budget bounds the nested generation work

The candidate generator no longer accepts a millisecond argument or counts `expired()` calls. `lua/candidates.lua` charges a fixed work budget (`work-12000-v5`): entity scans, threat-map reach expansion and retained threats, tactical goals, scored reach positions, eagerly rated destinations, paths, native probes and combat forecasts each cost work, and each stage carries its own cap (28 `find_reach`, 8 `find_path`, 24 `ai.check_recruit`, 32 `ai.check_attack`, 32 `ai.check_move`, 16 forecasts). Cuts are decided by work and caps only, never by elapsed time, so the candidate set stays deterministic for a given observation. End turn, recruits and adjacent attacks are generated before the threat map and movement, and features for the retained set are always materialized from the bounded entity lists. Tests assert the caps, a cut dense generation, and identical actions across repeated runs and an advanced clock.

Evidence: `verification/candidate_work_budget_20261031/REPORT.md` measures generation and scoring separately on the dense map; `tests/v5/test_candidate_pool_budget.py` holds the bounded-work contract. Remaining limits: `WORK.total` is the only calibrated value, so larger boards than the measured map are bounded but unmeasured.

## 5. Completed — Supported combat transfer and maintained native teacher strength

`probabilistic_combat_v6` executes reproducible hit/miss strikes and exposes public HP/status distributions. Snapshots and batch rollback preserve the RNG stream. Native cases cover slow, poison, fatal-hit status marginals, retaliation, combat/kill advancement and level-zero kill XP. Prediction retains the documented berserk cutoff, pre-advancement HP cap and approximate conditional poison recovery. [Stochastic combat](../verification/probabilistic_combat_20261102/REPORT.md) · [Boundary cases](../verification/combat_boundaries_20261102/REPORT.md)

The default `1.18.8-combat-filtered` package supports the captured declarations used by the 158-unit training closure. Fixed comparisons cover standard AMLA and feeding (5 native cases), accuracy/parry including the Champion sword (11), and weapon conditions, counter weights and target-hostile FFA backstab (31). Dynamic declarations outside the supported forms remain outside this scope. [AMLA](../verification/standard_amla_20261102/REPORT.md) · [Accuracy](../verification/weapon_accuracy_20261103/REPORT.md) · [Weights](../verification/weapon_weights_20261102/REPORT.md) · [Declaration filters](../verification/weapon_filters_20261103/REPORT.md)

Eighteen legal native/Lite boards cover teacher selection, with six native cases for unit immunity. The accepted teacher handles ambush interruption, attributes surviving slow benefit to the attacked target, and values that target consistently when choosing a duel landing. [Boards and immunity](../verification/teacher_immunity_20261103/REPORT.md) · [Ambush](../verification/teacher_ambush_20261103/REPORT.md) · [Target attribution](../verification/teacher_slow_attribution_20261103/REPORT.md) · [Surviving slow](../verification/teacher_surviving_slow_20261103/REPORT.md) · [Duel landing](../verification/duel_slow_landing_20261103/REPORT.md)

**Maintained teacher strength passed** against the original Astra strategy with matching ambush handling under the validation maps' 30-turn contract. The independent repaired-duel panel completed 1,920/1,920 games without faults. Its normalized 95% lower bound was −2.8125 percentage points. The verified identical four-player paths retain the earlier FFA (−4.3611) and team (−3.4028) lower bounds. Every bound exceeds the predeclared −5 percentage point margin. This closes R3 and item 5. [Independent endpoint and scope](../verification/duel_landing_ni_20261103/REPORT.md) · [Prior all-format endpoint](../verification/teacher_noninferiority_20261103/REPORT.md)

## 6. Completed — BC samples windows without decision-count bias

Each eight-turn window contributes one representative to the existing source/engine/family quota sampler, and the selected whole window is trained. Sampling is explicitly with replacement. The committed-step cursor records visits and visited window indices; final metrics distinguish unique and repeated window visits. Unequal-length sampling and update checks pass on Ubuntu. This intentionally changes BC sampling, not PPO rehearsal quotas.

## 7. Completed — Reuse detached prefixes and advance frozen memory incrementally

BC/PPO share detached historical scene encodings and prefix GRU states only within one logical optimizer step; the active replay suffix retains gradients and every new step starts a fresh cache. Frozen lite policies process only newly committed turn rows, maintaining separate per-side/job hidden state and 32 memory slots. Output/gradient comparisons, slot-overflow parity, bootstrap/side isolation and PPO resume checks pass. A 35-turn fixture drops encoded rows from 630 to 69; full-training wall-clock speedup is unmeasured.

Evidence for items 6-7: `verification/window_memory_20261101/REPORT.md`. Two pre-existing fixed-loss test failures remain documented, with identical baseline results. No formal training or collection was launched.

## 8. Completed — Coordinator appends job results without rereading the log

`learning/common.py` gains `repair_tail`: it reads one byte for a terminated log and otherwise scans backwards in 1 MiB chunks, so a repair costs the interrupted tail plus one chunk. `learning/coordinator.py` repairs each log once per broker call and appends every later result; `learning/sample.py` uses the same helper in `collect`. `tests/test_experiment.py` asserts exactly one repair per log across 15 appended results, byte-level tail cases including a multi-chunk tail, and the `collect` call site; point mutations of both call sites and of the chunk loop fail those assertions. Evidence: `verification/log_tail_repair_20261101/REPORT.md`. Limits recorded there: no games or training, no read-volume assertion in the repository, concurrent writers and long-run dispatch latency unmeasured.

## 9. Completed — Selected checkpoint finishes the native final panel

L1's selected trained duel v12 checkpoint completed its original 120-game Ubuntu holdout in 19m39s. The frozen Astra and baseline controls each scored 30/30 rotation blocks across 30 distinct scenarios. There were zero faults, 109 last-leader finishes and 11 turn-limit draws. From turn 10 onward the policy recorded 13,704 regular returns with p95 240 ms and maximum 316 ms. The official score differences were −1.00 against Astra and −0.65 against baseline. Both strength comparisons returned `not_passed`.

The original stop/resume and matching future batches remain covered by [the L1 run](../verification/acceptance_20261031_astra/REPORT.md). The isolated replay used its frozen checkpoint and original schedule with the current deployment runtime. [Final evaluation evidence](../verification/selected_final_20261103/REPORT.md)

## 10. Completed — Candidate coverage, teacher strength and ordinary BC readiness

The current `probabilistic_combat_v6` teacher and `work-12000-v8` candidates passed the unchanged ordinary BC gate for all three formats on Ubuntu. Source `87a68ea` ran the normal BC-only phase with 48 teacher games per format as the target, seed 20261101, 30 turns, eight workers, and the existing 2048/1024 train/validation reads. It ended naturally after 69m10s. All three committed checkpoints are effective, with no forced phase request, pending work or runner error. [Ordinary BC evidence and input identities](../verification/bc_ordinary_v6_20261103/REPORT.md)

| Format | Teacher games / target | Candidate coverage | Held-out recruit / move / attack exact accuracy | Scenario families |
| --- | ---: | ---: | --- | ---: |
| Duel | 56/48 | 90.29% | 64.18% / 57.74% / 44.27% | 31 |
| FFA | 48/48 | 90.64% | 61.33% / 66.93% / 61.22% | 39 |
| Team | 48/48 | 93.22% | 62.82% / 69.89% / 38.25% | 47 |

Duel initially covered 4,735/5,263 labels (89.97%). The trainer's normal plateau refresh produced eight more teacher games. Its final gate counted 5,533/6,128 (90.29%). Four DAgger correction games were separate from that count. All class coverage floors, sample counts, cross-entropy and accuracy thresholds passed. The teacher's native maintained-strength result remains in item 5. [Candidate generation and earlier gates](../verification/bc_root_20261101/REPORT.md) · [Teacher acceptance](../verification/duel_landing_ni_20261103/REPORT.md)

The actual training uses the recorded schema-6 terminal outcome for valid value labels. The earlier v2 recruit-type auxiliary-loss comparison failed to improve recruitment, so the production imitation loss retained its original definition. This establishes BC readiness for the stated profile. Item 11 separately requires the complete timed training and deployment chain. [Value-label fix](../verification/bc_terminal_value_20261103/REPORT.md) · [Matched loss comparison](../verification/team_bc_recruit_marginal_20261103/REPORT.md)

## 11. P1 — Add an approximately one-hour complete training-loop test

**Status:** executed on Ubuntu 2026-11-01; **FAIL at BC**, full-loop acceptance remains open. `tests/bounded_training_loop.py` froze all three formats and stage ceilings before launch. After 558.33 s, duel reached the five-committed-batch cap; BC batches were 5/1/1. Recorded complete games were 24/16/13 with zero recorded faults. The item-10 raw-record audit finds 1/6/6 actual turn-truncated games; the earlier prose counted candidate-generation cuts instead (historical evidence remains unchanged). Duel met its 24-game target but failed candidate coverage and imitation (overall accuracy 31.33%; recruit coverage 37.94%). The other formats had only eight games in their last gate. PPO, stop/resume, final evaluation and export were NOT RUN; no forced gate or retry. Evidence: `verification/bounded_loop_20261101/REPORT.md`.

**Profile mismatch repaired:** the historical plan declared 30 turns but frozen teacher schedules used 60; original evidence remains unchanged (`verification/recruit_ranking_20261102/turn_limit_audit.json`). The manual runner now passes its explicit limit through teacher/PPO/DAgger scheduling and scenario identity. Ordinary/legacy defaults remain 60, evaluation 30 and opening probes 5; resume honors frozen configuration and schedules. All 50 affected Ubuntu checks pass (`verification/training_turn_limit_20261102/REPORT.md`). This closes the wiring defect only; the full loop is still open.

**Purpose:** exercise the complete operational chain on Ubuntu: initialization/calibration, BC and its ordinary gate, PPO rollouts and at least two committed updates, checkpoint stop/resume, validation/selection, final evaluation, and audited export. Use a manually bounded smoke profile to expose integration failures and actual training cost; one hour cannot establish convergence or playing strength.

**Export size blocker repaired:** lossless float32/base64 weights reduce the regression add-on from 50,380,768 to 12,718,530 bytes under the unchanged 16 MiB SDK limit. All 59 affected checks pass, including every loaded coefficient, sequence parity and actual three-format SDK packaging. Six seeded original-game cases complete without faults and pass the existing timing gates in 259.63 seconds. Evidence: `verification/compact_weights_20261102/REPORT.md`. This closes the serialization/loading blocker. The independent ordinary BC phase subsequently passed in item 10. The bounded full loop remains open.

**PPO progress accounting repaired:** the manual runner previously derived every format's PPO cap from the smallest BC batch count, so uneven BC progress could stop PPO immediately. Each format now gets its own four-batch allowance. Both initial PPO and resume require new committed updates and a completed boundary without pending training or errors; previous updates cannot satisfy a stalled resume. Ten deterministic Ubuntu checks pass, with four baseline assertion failures demonstrating the defects (`verification/bounded_progress_20261102/REPORT.md`). These simulate stages; actual post-BC execution and same-future acceptance remain open.

**Final-panel handoff repaired:** normal CLI exit previously allowed the manual runner to proceed to export after failed or incomplete evaluation. It now requires finished error-free states and complete 30-block panels with zero missing blocks/fault games and at least 12 distinct scenarios for every control. Complete panels may remain statistically inconclusive or not passed; operational completeness does not require strength. All 13 affected deterministic Ubuntu checks pass; nine baseline assertion failures demonstrate the earlier gap (`verification/bounded_final_20261102/REPORT.md`). Actual final evaluation and export remain unrun.

**Procedure:** ship a committed source archive to a fresh dated directory on cpuServer and record its hash. Reuse compatible frozen rules, eligible teacher/human data and existing acceptance evidence. Before launch, explicitly freeze the formats (target all three), shared worker count, seed, game/turn limits, BC row/window/update caps, PPO batch/update caps and evaluation schedule. Use the smallest supported workload that preserves the ordinary gates and required panel sizes; do not silently change configuration validators. Budget roughly 5 minutes for preparation/calibration, 20 for BC, 15 for PPO including one committed-boundary stop/resume, 15 for validation/final evaluation and 5 for export/reporting, with an overall approximately 60-minute wall-clock limit. Treat these as stage ceilings, not promises that the gates will pass in that time. Reserve evaluation/export time rather than letting BC consume the entire run.

**Pass criteria:** every declared format reaches all stages; the ordinary BC gate passes; at least two PPO updates commit; resume continues from the recorded boundary without replaying committed work; the selected checkpoint completes its required evaluation and exports with the current sequence-parity audit. Record completed/faulted/truncated games, training updates, gate results, elapsed time by stage, source/rule/model identities and the actual candidate budget. Reuse matching same-future evidence where valid. If a gate or required panel cannot finish inside the cap, record the exact incomplete stage as FAIL/NOT RUN as appropriate, rather than forcing PPO, reducing acceptance criteria or extending the run automatically. Any reduced-format diagnostic must be identified as partial, not a completed all-format loop.

**Repair direction:** the bounded orchestration is implemented and its BC failure path was exercised; later stage paths remain unverified. Item 10 independently established ordinary BC readiness. A separately activated run still needs to exercise all stages within item 11's own phase ceilings. Keep the ordinary gates and the distinction from formal strength evaluation.

## Suggested order

The common deployed candidate contract and its bounded decision budget across native paths are settled (1-4). The selected-checkpoint evaluation (9) and the training-cost repairs (6-8) are complete. Teacher transfer (5) and ordinary BC readiness (10) are accepted for their stated profiles. Finish with the bounded complete-loop test (11), recording any stage that cannot complete within its one-hour budget.

This report proposes repair directions only. It does not authorize implementation, collection or training, and it does not replace the resident acceptance plan.
