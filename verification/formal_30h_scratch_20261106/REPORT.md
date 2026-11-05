# Formal 30-hour from-scratch training acceptance

## Outcome and scope

The process finished normally with exit code 0, but the training objective did not pass. Duel and team reached PPO; FFA never passed ordinary BC. All three formats selected v100. The selected duel's final comparison is inconclusive; selected FFA and team are significantly below the frozen Astra opponent on the recorded Lite panel. No improved playing strength is established.

This review reused existing games, checkpoints and logs. It performed no new collection, optimization, matches, native evaluation, deployment or source-code repair. A completed process is distinct from a passed BC gate, a fully committed training batch and a passed strength comparison.

## Frozen run and observed termination

- Host: `ssh cpuServer` (Ubuntu).
- Experiment root: `/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041`.
- Run: `source/runs/formal_30h_scratch` under that root.
- Source commit: `d2e6da5fbd07396c0c4d13a6588f66e1796f80fd`.
- Source archive SHA-256: `0bff83d5c982a7f00c09a06cd7b1396224282b0c251915c34623f146433682fd`.
- Run manifest SHA-256: `6de9d81858c71c41de505db2c445bae5229fa8587db7a6d3d66d2ebc3eab3c88`.
- Rules SHA-256: `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`.
- Extension SHA-256: `56dd77140411db987377d6de4ffbf562da4d0e5c76bc16d34780da67e60e5ae4`.
- Configuration: Lite training and evaluation; CPU; 8 global workers; 1 trainer thread; seed 20261017; training 60 turns; evaluation 30 turns; BC game targets 300/600/400; random initialization without a parent model or reused human/teacher corpus.
- Beijing start: 2026-11-04 20:43:47.165450. Update deadline: 2026-11-05 21:43:47.165450. Total deadline: 2026-11-06 02:43:47.165450. Four hours were reserved for final holdout.
- Observed finish: 2026-11-05 22:14:12.547670, about 25h30m25s after start. The 30 hours were a budget ceiling; the completed final panels did not consume the remaining allowance.
- `exit.code` is 0 and `training.log` ends with `Experiment: finished`. The recorded coordinator PID 591709 is no longer running. The source audit found no run process and no mismatches across 2,042 archived source files.
- Across 9,238 job records, 9,234 are complete and four final duel rollout jobs are `budget_interrupted`. There are no recorded game faults, state errors or per-format trainer error logs. Those four budget interruptions are not completed training games. [Full job-status summary](job_status_summary.json)

[Identity inventory](identities.json) records the runtime, teacher and resolved shared input paths. [Source check](source_check.json) compares the shipped archive against the actual source tree. Shared rule and extension symlink targets outside this experiment remain outside cleanup scope.

## BC and actual optimization

| Measure | Duel | FFA | Team |
| --- | ---: | ---: | ---: |
| Valid BC games / target | 300 / 300 | 960 / 600 | 400 / 400 |
| Covered teacher decisions / total | 29,767 / 32,672 | 242,124 / 274,888 | 166,379 / 182,287 |
| Overall candidate coverage | 91.1086% | **88.0810%** | 91.2731% |
| Held-out imitation accuracy | 63.1846% | 83.2305% | 67.3550% |
| Ordinary BC gate | Passed | **Failed: coverage below 90%** | Passed |
| Completed BC batches | 38 | 601 | 53 |
| Completed PPO batches | 902 | **0** | 231 |
| Committed PPO optimizer steps / planned | 6,435 / 9,020 | 0 / 0 | 3,196 / 5,460 |
| Latest complete candidate | last_ppo v940 | last_bc v601 | last_ppo v284 |
| Final state pending training | None | BC, 10 updates in incomplete next batch | PPO, 21 updates in incomplete next batch |

FFA met its corpus, imitation, per-class coverage and scenario-design requirements; overall candidate coverage alone blocked PPO. It performed 47 ordinary plateau refreshes. Additional optimizer work cannot make an absent candidate selectable.

The incomplete FFA/team batches are preserved in `latest.pt` and `state.json`; the nominated `last_bc.pt`/`last_ppo.pt` candidates are complete checkpoints. `stage=finished` describes orchestration termination, not completion of every pending training batch. See [checkpoint completeness](checkpoint-completeness.json).

## Final playing strength

Every final panel has 30/30 complete rotation blocks, zero missing blocks and zero game faults. The audit matched all 420 game IDs, seat rotations, scenarios, roster and engine identities to their frozen schedules. Recomputing the comparisons with the frozen evaluation code reproduced the original results exactly.

| Format | Games / independent scenario clusters | Outcome | Policy / Astra mean official score | Difference and scenario-cluster 95% CI | Result |
| --- | --- | --- | --- | --- | --- |
| Duel | 60 / 30 | 25 wins, 7 draws, 28 losses | 1.366667 / 1.516667 | -0.150000 [-0.600000, +0.300000] | Inconclusive |
| FFA | 120 / 15 | Mean rank 2.65 | 0.450000 / 0.601389 | -0.151389 [-0.248611, -0.054167] | Not passed |
| Team | 240 / 15 | 48 wins, 103 draws, 89 losses | 1.029167 / 1.541667 | -0.512500 [-0.837500, -0.200000] | Not passed |

FFA and team each reuse 15 independent scenarios twice; 30 blocks do not mean 30 independent scenarios. The existing confidence intervals account for scenario clustering. Raw official score scales differ by format, so the three raw differences are not directly comparable. These are Lite results against the frozen Astra package, not native/official-baseline strength acceptance.

Duel's final win rate is 25/60 = 41.67%; it belongs to selected v100, not latest PPO v940. Team's Astra-partner context has difference -0.275 [-0.625, +0.05]; self-team has -0.75 [-1.25, -0.20]. The worse self-team result warrants a coordination diagnosis, but does not by itself identify the tactical mechanism.

Raw recomputations: [duel](recomputed-v2-duel.json), [FFA](recomputed-v2-ffa4.json), [team](recomputed-v2-team2v2.json).

## Why the newest model was not selected

All 168 nomination games also completed, covering 12/12 blocks and 12 distinct scenarios per format, with no missing games or faults.

| Candidate | Difference against Astra and 95% CI | Recorded nomination status |
| --- | --- | --- |
| Duel v940 | -0.250000 [-1.375000, +0.875000] | Inconclusive |
| FFA v601 | -0.059028 [-0.163194, +0.048611] | Inconclusive |
| Team v284 | -0.437500 [-0.781250, -0.093750] | Not passed |

`learning/selection.py:_panel_complete` accepts only `passed` or `not_passed`; consequently the complete inconclusive duel/FFA panels are described as `astra nomination panel incomplete`. This is a reporting/completeness defect, not a timeout. All three candidates stopped at the Astra nomination stage, so no candidate-versus-champion nomination or final holdout of the latest candidates ran. Correcting that label alone would not make these candidates pass the positive-strength requirement.

The first v100 full promotion became the retained champion even though its Astra comparison was inconclusive. Subsequent champion comparisons did not establish a replacement. The word champion therefore names the retained reference, not a model proven superior to Astra.

The v100 and latest nomination panels share matched scenario parameters. Reusing those recorded blocks gives changes in score difference of duel -0.5 [-2.125, +1.125], FFA -0.09375 [-0.222222, +0.03125], and team -0.1875 [-0.75, +0.40625]. All intervals cross zero. This provides no significant evidence of improvement or regression from v100. Duel/team v100 already contain 62/47 PPO batches; the pre-PPO v38/v53 models have no comparable full panel. A causal claim about PPO benefit or damage is therefore unsupported. See [paired comparison](paired-earliest-latest.json).

## Improvement analysis

### Confirmed FFA bottleneck

A single read-only scan of all 960 original teacher shards reproduces the BC gate exactly. It counted `choice >= 0` as covered and folded `move_attack` into attack once, avoiding the overlapping diagnostic counters in the gate JSON.

| Existing teacher records | Covered / total | Coverage |
| --- | ---: | ---: |
| Turns 1-30 | 170,171 / 187,869 | 90.5796% |
| Turns 31-60 | 71,953 / 87,019 | 82.6865% |
| arena4 | 107,764 / 119,244 | 90.3727% |
| isars_cross | 65,482 / 68,361 | 95.7885% |
| clash | 68,878 / 87,283 | 78.9134% |
| clash, turns 31-60 | 19,294 / 28,895 | 66.7728% |

Late turns account for 31.66% of teacher decisions and 45.98% of omissions. Clash accounts for 56.17% of all omissions. Missing move/attack destinations account for 24,684 of 32,764 uncovered actions (75.34%). Repairing at least 5,276 currently uncovered decisions without losing covered decisions would bring this fixed corpus to 90%; this arithmetic is not acceptance of a future implementation.

The first 600 games had 88.2761% coverage; the additional 360 had 87.7447%. Repeated refresh did not resolve the representation gap. FFA's BC learning rate also fell from 0.0003 to 0.00000235655 after 46 reductions across 47 refreshes, despite held-out imitation already passing. Coverage is measured on teacher evidence, so fitting weights or adding DAgger rows does not directly repair these missing teacher actions.

FFA teacher games use arena4/isars_cross/clash in counts 480/240/240. Its 504 ordinary validation games use loris_river at the 30-turn evaluation cap. Held-out BC accuracy is measured on covered teacher actions from the training-map corpus; it is not a direct measure of play on the validation map. Coverage in the original teacher validation partition is only 86.7135%, versus 88.3678% in the training partition. These measured distribution differences limit what the passing imitation score establishes.

The recorded exclusion reason identifies the first failed matching stage among surviving candidates; it does not distinguish generation failure from later candidate-budget pruning. The first-30-turn slice is an observed prefix of 60-turn games, not a newly accepted 30-turn run. [Full counts and limits](ffa_coverage_by_turn_map.json); [read-only scan](scan_ffa_coverage.py).

### Team optimization and opponent distribution

Team entered PPO after about 4.62 hours. Its 231 committed PPO batches all changed the model weight digest. KL stopping occurred in 207/231 batches (89.61%), leaving 2,264/5,460 planned optimizer steps unperformed (41.47%). That establishes constrained update size, not that relaxing the KL limit would improve play.

All 231 batches report `rehearsal_sources = policy`. The current code excludes the matching control teacher identity from PPO rehearsal; Astra and its DAgger rows therefore do not provide continuing teacher imitation in this run. On average 992.42 candidate rehearsal rows per batch were excluded. The configured `bc_aux=0.1` must not be described as sustained Astra supervision. Whether this causes forgetting needs a measurement on held-out teacher actions before and after PPO, followed by an authorized controlled experiment if justified.

The 928 collected team PPO games include the final pending four-game batch. Their 1,856 enemy seats contain 928 Astra, 464 historical-policy and 464 current-policy opponents; 928 teammate seats contain 464 Astra and 464 current-policy partners. The original 400 team teacher games and 960 FFA teacher games use four Astra seats. There are no official baseline opponents in this Lite run. Both recorded team evaluation contexts are represented in training, but final evaluation's fixed Astra opposition is not the same distribution as the mixed training opponents.

Self-team was weaker than the Astra-partner context in the final scores and at v200. The existing diagnostics do not measure missed attack opportunities, coordinated focus fire, blocking allies or rescue choices. Those tactical explanations remain hypotheses. The shaping-to-terminal reward RMS ratio is 0.0493-0.1958 across 23 available team validation diagnostics; reward version remains zero. This evidence does not support a claim that shaping overwhelmed the terminal objective, nor does it decompose the actual training gradients.

The 54 ordinary FFA and 26 ordinary team trend reports each have only one scenario block against a three-scenario minimum and are marked `insufficient_design`. They can show noisy observations but cannot establish progress. Promotion, nomination and final panels have their separate complete designs. [Training summaries and limits](learning_causes_summary.json); [read-only aggregation](summarize_learning_causes.py).

### Prioritized next work, subject to a separate instruction

| Priority | Change or investigation | Expected value / cost | Smallest meaningful validation |
| --- | --- | --- | --- |
| 1 | Trace missing FFA move/attack destinations on late Clash boards, then repair the responsible generation/retention seam | High: removes the measured PPO blocker; moderate implementation cost | Select fixed omitted-action examples from existing traces; identify where each disappears; compare coverage on the same frozen corpus while preserving legal visibility, 37 candidates and the work budget. Then use an independently authorized ordinary 60-turn BC gate. |
| 2 | Distinguish complete/inconclusive nomination from incomplete/faulted nomination | High diagnostic value; low cost; does not promise strength | Reuse the three existing nomination JSONs and one truly incomplete/faulted case. Correct completeness labels while preserving the strength promotion rule. No matches needed. |
| 3 | Separate a coverage-limited BC stall from an imitation plateau | Prevents repeated unproductive refresh/learning-rate decay; low-to-moderate cost | Replay the recorded FFA gate sequence through the proposed decision rule; prove it reports the coverage blocker without lowering gates or entering PPO. |
| 4 | Measure team imitation retention and KL-limited updates before tuning PPO | Potentially high; moderate diagnostic cost, higher experiment cost | Evaluate v53/v100/v284 on the same held-out teacher rows; inspect existing KL records. If warranted, predefine one changed variable and compare fixed-opponent panels in both partner contexts; retain KL protection and teacher-provenance boundaries. |
| 5 | Diagnose team attack/coordination and align progress evaluation with deployment questions | Potentially high but presently less certain; moderate-to-high cost | Review a small fixed set of existing self-team losses for visible attack opportunities and ally interactions. For a later authorized training run, ensure trend panels meet their scenario floor and record matched pre-PPO/selected/latest comparisons with independent final scenarios. |

More training hours, larger models, relaxed gates and increased reward shaping are not supported as first actions by this evidence. No proposed repair or new training was executed during this review.

## Retained artifacts and cleanup boundary

All unique models, all policy export paths, `latest.pt`, `best.pt`, `selected.pt`, `last_bc.pt`, and every existing `last_ppo.pt` remain under the original run. FFA has no `last_ppo.pt` because it never entered PPO. Frozen manifests, controls, RNG/optimizer state, pending cursors, raw shards, sequence databases, logs, schedules, reports and audits are retained.

The three selected checkpoint SHA-256 values are:

| Format | selected.pt SHA-256 |
| --- | --- |
| Duel | `7065ad90650e48c0776ca4c3cb066008c1e151e62d0aeaa6095364c8e244f65b` |
| FFA | `e11e8809161e2be84343f5657536eeea8e1296962fb882d1425c7caf3cef0eaa` |
| Team | `02de100f80960c93450e491fc4b72d6094bd4702fcb4bb9efadabcf1ab560993` |

[Checkpoint inventory](checkpoints.json) hashes all 14 checkpoint files. [Load check](checkpoint_load_check.json) loads the 11 selected/latest/last-phase files, verifies their manifest pin, and confirms 776,178 finite model values in each. All selected versions are 100, and selected/best/selection/report hashes agree. This is integrity evidence, not a newly performed delivery parity or restart acceptance.

The pre-cleanup inventory found 2,399 policy model files, including 1,143 byte-identical extra copies. Historical references and export provenance still use their paths, so they are retained. The three sequence databases occupy 17,157,623,808 bytes; full equivalence to the raw shards was not established, so they are retained. The original remote source archive is retained as provenance. See [cleanup candidates and retention inventory](cleanup_candidates.json.gz).

Before deletion, the result, analysis, frozen identities and original metadata archive were saved locally; a pre-cleanup report was also saved remotely as `review_20261106/REPORT-before-cleanup.md`. The cleanup verified no remaining run process, resolved each cache path inside the experiment root and checked its hash and surviving source file. The local archive was opened exclusively before deletion, confirming no active file handle prevented exclusive access.

| Removed artifact | Files | Logical bytes |
| --- | ---: | ---: |
| Four enumerated Python bytecode cache directories | 50 | 657,400 |
| Byte-identical local launch source archive | 1 | 113,989,235 |
| Total | **51** | **114,646,635 (109.34 MiB)** |

The four empty cache directories were removed too. Remote filesystem allocation released by those caches was 770,048 bytes; the combined figure above reports file lengths, not a measured cross-filesystem free-space delta. All deleted paths are absent, and all 14 preserved checkpoints still match their pre-cleanup SHA-256 values. The original remote source archive is the retained complete copy of the local archive. [Remote cleanup result](cleanup_result.json), [local pre-cleanup plan](local_cleanup_plan.json), [local cleanup result](local_cleanup_result.json).

## Evidence and reproduction

- `metadata.tar.gz` captures 609 original metadata/log/report files (67,765,247 uncompressed bytes). SHA-256: `65ccae29697be4cd06fb10cc42dbf9171028bc2d07b9343e17e66dd85593fdf3`. [Inventory](metadata_inventory.json) records every original path, size and hash.
- `nomination_schedules.tar.gz` supplements the three frozen `nominate-*.json` schedules. [Inventory](nomination_schedule_inventory.json) preserves their individual hashes.
- [Ubuntu archive check](archive_check.json) verifies all 612 archived members against their recorded lengths and SHA-256 values, with zero discrepancies.
- Evidence lives locally in this dated directory and remotely under the experiment's `review_20261106/`. The original training logs and data remain at their recorded locations.
- Read-only procedure: inspect `exit.code`, `finished.txt`, `training.log`, process ownership and frozen identities; load final states/gates/checkpoints; join `jobs.jsonl` to final/nomination schedule IDs; recompute existing official-score comparisons and scenario-cluster intervals; aggregate existing training history and teacher traces; inventory references/hashes before cleanup.
- No source behavior changed, and no unrelated test suite was rerun. Future repair and new training require a separate user instruction.
