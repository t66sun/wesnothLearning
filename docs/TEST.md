# Implemented but awaiting acceptance

> Language: English | [中文](TEST_zh.md)

Updated 2026-10-24. Only native terminal-state capture remains pending. Accepted phase/PPO evidence is in the [repair report](../verification/training_repair_20261023/REPORT.md); corrected movement quality and state reuse are in the [follow-up report](../verification/bc_rootcause_20261023_2318/REPORT.md). Passed scopes are archived and not repeated.

## T6: New native terminal-state observation capture

**Status/reason:** the native runtime and parser are wired to independent METRIC events sharing the terminal-statistics contract; this round's real Ubuntu capture validation covered lite only and no new native terminal-state game was run. Existing native acceptance cannot stand in for this new production path.

**Minimal Ubuntu plan:** when a later native training/evaluation needs it, reuse native 1.18.8 and the current rules/lightweight LearningSupport to run one fixed early-elimination/endgame scenario limited to 5 turns, then reuse the existing budget-truncation counterexample. Verify only initial/eliminated/terminal events, surviving side and real own HP, result parsing, and that shards contain no metric_event; report missing tests when events are absent. The scenario helper is not yet written and native rules or the performance matrix do not need rerunning.

**Pass/blocker/evidence:** real terminal states can form the T5/T10 absorbing state, faults and budget truncation cannot synthesize terminals, and actor/BC/PPO rows stay unpolluted. This blocks only acceptance of the new native terminal-state capture and not the default pure lite flow. Commands, source/rule identity and raw events are archived to `verification/native_terminal_<date>/` and the whole item is deleted after passing.
