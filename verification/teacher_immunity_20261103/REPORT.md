# Teacher board and unit immunity acceptance — 2026-11-03

The current change is accepted for fixed legal-board teacher decisions and per-unit combat immunities. Item 5 remains OPEN for the complete R3 native strength/transfer panel. The user requested wrapping up the current work; no complete-game panel, collection or training was launched.

## Change

A native/Lite teacher disagreement exposed a shared combat bug: the strike function checked type immunity but ignored the unit's current unpoisonable flag. Its poisoned survivor then entered the probability distribution even though the fatal-hit marginal already checked the flag. The same execution seam omitted undrainable, and plague conversion discarded the victim's status before checking immunity.

The strike function now checks both type and per-unit poison/drain immunity. Plague retains a reference to the victim and rejects unplagueable victims in both combat directions, avoiding the previous temporary type-name clones. The probability propagator uses the corrected strike function. No teacher scoring weights, RNG algorithm, forecast cache or broad structure changed. Profile probabilistic_combat_v6 separates the changed semantics from old snapshots and rows; historical inputs remain unchanged.

## Identity

- Production source/build: `90d796ae996354c954b14c0c6cdfe509f0acbae2`; extension SHA256 `63b1c119670d4d0981925fafef4f781ab274f05fb0aa2fedafc8b24dfd503059`.
- Final board fixture source: `0111083915a5a5076f39e43be7c67c9e4739b447`; final native fixture source: `afec90f76d7157315a25974ba758cee315e1be8a`. Production code is identical across these commits. `archives.json` records shipped git archive commit headers and SHA256 values. Each archive was extracted into a fresh Ubuntu acceptance directory.
- Rules: unchanged `1.18.8-combat-filtered`, SHA256 `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`; rule version `lite-combat-2-58ead901dadf8ebe`.
- Native executable SHA256 `33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf` (Wesnoth 1.18.8).
- Teacher profile `probabilistic_combat_v6`, source SHA256 `d0eb8d922b0c5b8092863ff712b9f2b4df097ac3653d90432c5d2d906aa87a38`.
- Python `/home/tongshu/venv/bin/python`; Rust `/home/tongshu/.cargo/bin`; native executable `/home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth`. `OMP_NUM_THREADS=1`.

## Results

| Check | Result | Evidence |
| --- | --- | --- |
| Unmodified v5 extension, new immunity tests | FAIL: six assertions, both combat directions | `baseline.log` |
| Rust unit tests and release build | PASS: 21 tests, zero ignored | `rust.log`, `build.log` |
| Affected Python contracts | PASS: 84 tests, no skips | `python.log` |
| Real teacher decisions on complete legal boards | PASS: 18/18, six positions × three formats | `boards/` |
| Native immune poison/drain attacks | PASS: two cases, full HP/status distributions within 1e-9 | `native_partial/immune_*.json` |
| Native immune plague attack and three immune counters | PASS: four cases, no recorded differences | `native_final/immunity/` |
| Complete R3 12-block comparison | NOT RUN | Separate authorization and execution remain |

The board runner uses the original maintained teacher modules on both backends. Expected target/weapon choices are explicit: lethal target, survive retaliation, magical weapon, poison weapon, slow weapon and avoidance of poison immunity. It checks native/Lite plan agreement, successful legal execution, unchanged student candidates and game state, repeated snapshot queries and a second Lite seed. These are 13×13 fully visible, first-decision tactical positions with six or seven units in four-player formats, not complete games, recruitment/movement ranking coverage or trained-policy strength.

The initial 7×7 poison-immunity disagreement is retained in `initial/duel-poison_immunity.json`: native chooses the susceptible alternative, Lite chooses the immune defender. Other initial fixture failures were not engine evidence: the 1-HP attacker declined the dangerous fight, enemy leaders threatened the compact board, and the four-player home-radius penalty suppressed isolated attacks. The final layout keeps remote enemy leaders out of threat range and anchors the own leader within the existing radius. Neither teacher policy nor score threshold was changed.

The native plague fixture initially missed both strikes, so it did not exercise a lethal conversion (`native_partial/immunity.log`). The final fixture puts the victim on deep water, where the captured definition and native predictor give 100% hit chance. Both backends must actually kill the victim and leave its hex empty. No seed search or retry-to-pass was used. The two already passing native cases were reused; their full distributions were independently compared at 1e-9 when archiving. The remaining four cases were run once with the final fixture.

`commands.sh` records the build/Python command and first board invocation; that shell stops when the earlier board fixture fails, so its following native command did not run. `final-commands.sh` records the completed board and separate native invocations. Earlier invalid no-leader test construction and the Rust borrowed-name compilation error were corrected before the recorded successful build; neither is counted as passing evidence.

## Limits and reuse

The accepted v5 rule compilation/weapon-weight/backstab evidence remains valid for unchanged behavior (`verification/weapon_filters_20261103/REPORT.md`). Current affected contracts and fixed immunity positions were rerun rather than relabelling that evidence as v6. Inventory native/performance acceptance flags remain false. No Windows tests ran, no frozen data was modified, and no training/strength claim follows from this change.
