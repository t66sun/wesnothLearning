# Completed blocker review

Static review date: 2026-10-31 (Asia/Shanghai).
Source: `f563cade05eabeb6a45f48ce0dc476654cf71ae4`, initially clean `master` working tree.

The original static review covered training coordination, BC/PPO, recurrent policies, shared Lua candidates, Lite policy execution, combat and deployment. The numbered entries preserve their original acceptance scopes. All eleven now have Ubuntu evidence.

The original review classified direct threats to policy behavior or acceptance as P1, and scaling costs or unresolved quality prerequisites as P2.

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

`probabilistic_combat_v6` executes reproducible hit/miss strikes and exposes public HP/status distributions. Snapshots and batch rollback preserve the RNG stream. Native cases cover slow, poison, fatal-hit status marginals, retaliation, combat/kill advancement and level-zero kill XP. Prediction retains the documented berserk cutoff, pre-advancement HP cap and approximate conditional poison recovery. [Stochastic combat](../probabilistic_combat_20261102/REPORT.md) · [Boundary cases](../combat_boundaries_20261102/REPORT.md)

The default `1.18.8-combat-filtered` package supports the captured declarations used by the 158-unit training closure. Fixed comparisons cover standard AMLA and feeding (5 native cases), accuracy/parry including the Champion sword (11), and weapon conditions, counter weights and target-hostile FFA backstab (31). Dynamic declarations outside the supported forms remain outside this scope. [AMLA](../standard_amla_20261102/REPORT.md) · [Accuracy](../weapon_accuracy_20261103/REPORT.md) · [Weights](../weapon_weights_20261102/REPORT.md) · [Declaration filters](../weapon_filters_20261103/REPORT.md)

Eighteen legal native/Lite boards cover teacher selection, with six native cases for unit immunity. The accepted teacher handles ambush interruption, attributes surviving slow benefit to the attacked target, and values that target consistently when choosing a duel landing. [Boards and immunity](../teacher_immunity_20261103/REPORT.md) · [Ambush](../teacher_ambush_20261103/REPORT.md) · [Target attribution](../teacher_slow_attribution_20261103/REPORT.md) · [Surviving slow](../teacher_surviving_slow_20261103/REPORT.md) · [Duel landing](../duel_slow_landing_20261103/REPORT.md)

**Maintained teacher strength passed** against the original Astra strategy with matching ambush handling under the validation maps' 30-turn contract. The independent repaired-duel panel completed 1,920/1,920 games without faults. Its normalized 95% lower bound was −2.8125 percentage points. The verified identical four-player paths retain the earlier FFA (−4.3611) and team (−3.4028) lower bounds. Every bound exceeds the predeclared −5 percentage point margin. This closes R3 and item 5. [Independent endpoint and scope](../duel_landing_ni_20261103/REPORT.md) · [Prior all-format endpoint](../teacher_noninferiority_20261103/REPORT.md)

## 6. Completed — BC samples windows without decision-count bias

Each eight-turn window contributes one representative to the existing source/engine/family quota sampler, and the selected whole window is trained. Sampling is explicitly with replacement. The committed-step cursor records visits and visited window indices; final metrics distinguish unique and repeated window visits. Unequal-length sampling and update checks pass on Ubuntu. This intentionally changes BC sampling, not PPO rehearsal quotas.

## 7. Completed — Reuse detached prefixes and advance frozen memory incrementally

BC/PPO share detached historical scene encodings and prefix GRU states only within one logical optimizer step; the active replay suffix retains gradients and every new step starts a fresh cache. Frozen lite policies process only newly committed turn rows, maintaining separate per-side/job hidden state and 32 memory slots. Output/gradient comparisons, slot-overflow parity, bootstrap/side isolation and PPO resume checks pass. A 35-turn fixture drops encoded rows from 630 to 69; full-training wall-clock speedup is unmeasured.

Evidence for items 6-7: `verification/window_memory_20261101/REPORT.md`. Two pre-existing fixed-loss test failures remain documented, with identical baseline results. No formal training or collection was launched.

## 8. Completed — Coordinator appends job results without rereading the log

`learning/common.py` gains `repair_tail`: it reads one byte for a terminated log and otherwise scans backwards in 1 MiB chunks, so a repair costs the interrupted tail plus one chunk. `learning/coordinator.py` repairs each log once per broker call and appends every later result; `learning/sample.py` uses the same helper in `collect`. `tests/test_experiment.py` asserts exactly one repair per log across 15 appended results, byte-level tail cases including a multi-chunk tail, and the `collect` call site; point mutations of both call sites and of the chunk loop fail those assertions. Evidence: `verification/log_tail_repair_20261101/REPORT.md`. Limits recorded there: no games or training, no read-volume assertion in the repository, concurrent writers and long-run dispatch latency unmeasured.

## 9. Completed — Selected checkpoint finishes the native final panel

L1's selected trained duel v12 checkpoint completed its original 120-game Ubuntu holdout in 19m39s. The frozen Astra and baseline controls each scored 30/30 rotation blocks across 30 distinct scenarios. There were zero faults, 109 last-leader finishes and 11 turn-limit draws. From turn 10 onward the policy recorded 13,704 regular returns with p95 240 ms and maximum 316 ms. The official score differences were −1.00 against Astra and −0.65 against baseline. Both strength comparisons returned `not_passed`.

The original stop/resume and matching future batches remain covered by [the L1 run](../acceptance_20261031_astra/REPORT.md). The isolated replay used its frozen checkpoint and original schedule with the current deployment runtime. [Final evaluation evidence](../selected_final_20261103/REPORT.md)

## 10. Completed — Candidate coverage, teacher strength and ordinary BC readiness

The current `probabilistic_combat_v6` teacher and `work-12000-v8` candidates passed the unchanged ordinary BC gate for all three formats on Ubuntu. Source `87a68ea` ran the normal BC-only phase with 48 teacher games per format as the target, seed 20261101, 30 turns, eight workers, and the existing 2048/1024 train/validation reads. It ended naturally after 69m10s. All three committed checkpoints are effective, with no forced phase request, pending work or runner error. [Ordinary BC evidence and input identities](../bc_ordinary_v6_20261103/REPORT.md)

| Format | Teacher games / target | Candidate coverage | Held-out recruit / move / attack exact accuracy | Scenario families |
| --- | ---: | ---: | --- | ---: |
| Duel | 56/48 | 90.29% | 64.18% / 57.74% / 44.27% | 31 |
| FFA | 48/48 | 90.64% | 61.33% / 66.93% / 61.22% | 39 |
| Team | 48/48 | 93.22% | 62.82% / 69.89% / 38.25% | 47 |

Duel initially covered 4,735/5,263 labels (89.97%). The trainer's normal plateau refresh produced eight more teacher games. Its final gate counted 5,533/6,128 (90.29%). Four DAgger correction games were separate from that count. All class coverage floors, sample counts, cross-entropy and accuracy thresholds passed. The teacher's native maintained-strength result remains in item 5. [Candidate generation and earlier gates](../bc_root_20261101/REPORT.md) · [Teacher acceptance](../duel_landing_ni_20261103/REPORT.md)

The actual training uses the recorded schema-6 terminal outcome for valid value labels. The earlier v2 recruit-type auxiliary-loss comparison failed to improve recruitment, so the production imitation loss retained its original definition. This establishes BC readiness for the stated profile. Item 11 separately requires the complete timed training and deployment chain. [Value-label fix](../bc_terminal_value_20261103/REPORT.md) · [Matched loss comparison](../team_bc_recruit_marginal_20261103/REPORT.md)

## 11. Completed — Approximately one-hour complete training loop

The ordinary three-format run on Ubuntu source `3b6bc06` completed in 28m44s with eight shared workers. Compatible v6 weights and teacher data from item 10 initialized fresh BC with reset optimizers in all three formats. Every format earned its gate again, committed a PPO batch before stopping, resumed without replaying committed work, and made new PPO updates. All 18 due trend games and 36 reward-reference games completed.

| Format | New BC optimizer steps | PPO steps before / after restart | Final games | Complete blocks | Scenario families |
| --- | ---: | ---: | ---: | ---: | ---: |
| Duel | 56 | 4 / 4 | 60/60 | 30/30 | 30 |
| Four-player FFA | 64 | 7 / 14 | 120/120 | 30/30 | 15 |
| Team 2v2 | 56 | 10 / 7 | 240/240 | 30/30 | 15 |

All 420 final Lite games completed in 851.87 seconds under the original 864-second internal deadline, with zero faults and zero missing blocks. The ordinary CLI exported the three selected v3 models and audited 10,492 raw rows in 198.20 seconds. The SDK ZIP SHA256 was `047db8d244bfb9244be620a1ba6cb5aee1e14b7f83fe3dc21a5b1973e0b39c28`. This closes the operational training-loop test. The strength comparison was inconclusive in duel and did not pass in FFA or team. [Final commands, handoffs and artifacts](REPORT.md) · [Earlier strict result](../bounded_loop_strict_20261104/REPORT.md) · [Second strict result](../bounded_loop_confirmation_20261104/REPORT.md)
