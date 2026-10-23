# Implemented but awaiting acceptance

> Language: English | [中文](TEST_zh.md)

Updated 2026-10-23. Only unfinished evidence scopes remain; accepted Ubuntu wiring, phase switching, two real PPO rounds, final model selection and the opening check are archived in the [repair report](../verification/training_repair_20261023/REPORT.md) and not retested. Original document snapshots and old reports keep their original dates/hashes.

## T5: Restricted BC quality with corrected tactical inputs

**Status/reason:** schema 5/v3 Ubuntu wiring and Python/Lua consistency have passed. The old Windows comparison showed a move gain, but the collection side covered only three factions, FF4 undead is 15/49 (30.61%), and the recruit/attack and overall gates are not all passed; this round also fixed the repeated_move column misread, so the old trajectory comparison cannot be written as new data quality passing.

**Minimal Ubuntu plan:** use this round's isolated sources/environment and reuse the same-initialization, same-data, equal-update ablation method of `verification/bc_move_fix_20261023/quality_ablation.py`. Prepare at least two train and two independent validation game families each for ffa4/team2v2, at most 12 turns, with the training pool covering six factions; plan the family split before collecting and do not top up satisfied conditions. The old challenge family stays holdout and never enters training. After fixing all data, compare normal tactical inputs against a zeroed ablation, keeping the 120-update cap; insufficient samples stay honestly inconclusive instead of mass re-collection to fill gates. The corrected data/quality test is not yet written or executed, and existing helpers must be bound to the current version with actual families and source hashes recorded.

**Pass:** full-action argmax moves of at least 32 each across at least two validation families, with normal inputs ≥35% in both formats and better than the ablation; also list actual recruit/attack/overall correct counts, totals, CE and six-faction coverage. Teacher candidate move coverage ≥80% and overall ≥90%. Conditional accuracy, top-k and training-set accuracy cannot substitute for holdout accuracy.

**Training blocker and evidence:** the acceptance blocker "corrected BC quality gain proven" is not cleared; accepted phase entries are unaffected. The next formal training still needs user authorization, automatic PPO is still bound by all real BC gates, and force override only uses the explicit entry. Output to a new `verification/bc_quality_ubuntu_<date>/` and report sources/rules, data families, factions, update counts and per-class counts; after passing, archive and delete the whole item, without first collecting the full 1300 games or rerunning the full-pipeline matrix.

## T6: New native terminal-state observation capture

**Status/reason:** the native runtime and parser are wired to independent METRIC events sharing the terminal-statistics contract; this round's real Ubuntu capture validation covered lite only and no new native terminal-state game was run. Existing native acceptance cannot stand in for this new production path.

**Minimal Ubuntu plan:** when a later native training/evaluation needs it, reuse native 1.18.8 and the current rules/lightweight LearningSupport to run one fixed early-elimination/endgame scenario limited to 5 turns, then reuse the existing budget-truncation counterexample. Verify only initial/eliminated/terminal events, surviving side and real own HP, result parsing, and that shards contain no metric_event; report missing tests when events are absent. The scenario helper is not yet written and native rules or the performance matrix do not need rerunning.

**Pass/blocker/evidence:** real terminal states can form the T5/T10 absorbing state, faults and budget truncation cannot synthesize terminals, and actor/BC/PPO rows stay unpolluted. This blocks only acceptance of the new native terminal-state capture and not the default pure lite flow. Commands, source/rule identity and raw events are archived to `verification/native_terminal_<date>/` and the whole item is deleted after passing.
