# Prospective duel teacher acceptance

This protocol covers one authorized duel repair and one independent native confirmation. The previous 4,560-game endpoint failed its all-format criterion on duel. Its FFA and team results passed their respective criteria. The previous duel result stays in the historical report. [Previous endpoint](../verification/teacher_noninferiority_20261103/REPORT.md)

## Candidate and reuse

Before the first game, freeze the repair commit, source archive, teacher digest, staged packages, executable, entropy shim, maps, schedule and plan. The candidate must have an accepted targeted regression that connects the repair to a legal duel decision. Selection and fixed-board development end before preparing the confirmatory panel.

The four-player reference is the completed panel at source `97d7d9ddf87948bb59781f8f68a7d9b1e3a03fe3`, using teacher digest `ad75d870ce68fa6b489ad922fd8bb3059e29bbe7626f296e74d2b6fad828c7d4`. For four players, the deployed `bot.lua` loads `four.lua` and its shared value module. The new staged candidate must differ from the previous staged candidate in `lua/duel.lua` only. Every member of the staged compatible control must match its counterpart, including its three ambush-handling move helpers. Compare unpacked bytes because zip timestamps can differ. [Native routing](../learning/teachers/gpt6astra/lua/bot.lua) · [Reference identities](../verification/teacher_noninferiority_20261103/identities.json)

Prepare checks the reference summary identity, staged package contents, previously recorded common native inputs and the four-player validation map digest. Before launch, also review the archive diff from the reference for native referee/SDK code, map/faction profiles, shared observers, game I/O and the native installation used on cpuServer. Record the command and result with the prepared plan. Any difference that could change four-player inputs, behavior, comparator or scoring prevents FFA/team evidence transfer. Stop before launching if the four-player behavior cannot be isolated.

## Fixed endpoint

| Setting | Value |
| --- | --- |
| Native format, map | duel, validation Hamlets |
| Master seed | 20261105 |
| Work | 15 frozen faction-pair families × 64 blocks × 2 seat rotations = 1,920 games |
| Pairing | Same physical map, faction assignment and game seed within each two-seat rotation |
| Budget | Eight workers, one-second action and ten-second first-call limits, 30 turns, six hours from preparation |
| Score | Official candidate-minus-compatible-control score normalized by 3 |
| Interval | Existing equal-family percentile bootstrap, 5,000 resamples, seed 19 |

The deterministic duel schedule draws 960 distinct game seeds. A read-only check against the archived three smoke schedules, all four 168-game panels and the 4,560-game NI schedule found zero overlap with their 1,672 distinct game seeds. Prepare freezes the actual new schedule before execution. Each paired rotation deliberately shares its seed. New seeds supply fresh battles on the same 15 validation families. Final holdout maps are outside this design.

All 1,920 declared jobs, all 960 complete rotation blocks and all 15 families are required, with zero faults. The normalized lower endpoint of the two-sided 95% scenario-cluster interval must strictly exceed −0.05. The five-point margin is a difference in normalized official score. Count official 30-turn adjudications in the score and report their number separately from natural endings. Missing, interrupted or faulted results cannot be substituted with draws. Preserve the ordinary superiority comparison as a separate descriptive output.

Observe only progress, runtime faults and the deadline until the endpoint. Run the frozen schedule once and calculate the endpoint once. There is no retry, replacement seed, budget extension, additional repair or interim scoring. On any failure, archive the actual result and keep the duel gate open.

## Ubuntu execution and reporting

Use a new dated archive extraction and output directory. Set `ROOT`, `PANEL`, `WESNOTH`, `SOURCE_COMMIT` and `SOURCE_ARCHIVE` to the verified final identities. `PREVIOUS_PANEL` points to the complete November 3 NI panel on cpuServer or to a byte-identical extraction of its archived panel records.

```sh
python tests/acceptance_teacher_strength.py prepare \
  --root "$ROOT" --output "$PANEL" --wesnoth "$WESNOTH" \
  --source-commit "$SOURCE_COMMIT" --source-archive "$SOURCE_ARCHIVE" \
  --duel-noninferiority --reuse-panel "$PREVIOUS_PANEL"
python tests/acceptance_teacher_strength.py run --output "$PANEL"
```

Archive the protocol, identities, scope review, schedule, raw results, counts, runtime and endpoint in a new dated evidence directory. Report the new duel result separately from the previously measured FFA and team results, including their original source identities and equal-weight team contexts. A maintained-strength claim across formats requires a passing new duel endpoint and documented applicability of both historical results to the candidate's four-player path.
