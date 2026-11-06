# Complete inconclusive nomination panels

## Outcome

Issue #222, completeness subtask: a complete nomination panel with an inconclusive strength interval is now recognized as complete and reused. It still cannot promote a candidate. Missing, faulted, underfilled and insufficient-scenario panels remain ineligible.

Ubuntu ran 21 affected tests successfully in 2.487 seconds. The new regression fails on the parent implementation with the exact misclassification, then passes with the one-line status change. No game, training, collection or checkpoint-selection operation was run against the historical experiment. Existing inputs and evidence remain unchanged.

## Source and inputs

| Shipment | Source commit | Archive SHA-256 |
| --- | --- | --- |
| Red regression | `112c2d139108bedbaa2d75dfc033e2f23bcf1c42` | `4d3f789def7d508a76f72b9234ede69fece2c2cf8de07f502a2dd735ca9a5d12` |
| Green implementation | `53e8629dec6ba7fdaa9d241b47682c7e72276eb9` | `ca12b78e785f81219fa17f759c29b2f4c4750cb61abf8f9178eefd8a5e711d98` |

Archives were extracted separately at `/home/tongshu/acceptance/issue222_nomination_20261106/{red,green}`. Python was `/home/tongshu/venv/bin/python` with one OMP/MKL/OpenBLAS thread and bytecode writes disabled. The extension import path was the formal run's `source/.extension`.

Frozen maps were provisioned by a new symlink from `green/data/rules/1.18.8` to `/home/tongshu/myDev/wesnothLearning/WesnothLearning/rules/1.18.8`. Rules used `/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered`, rules SHA-256 `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`. No map was generated or changed.

The first green suite attempt had four missing-map input errors because source archives exclude provisioned map data. Its [log](missing_maps.log) is preserved and is not counted as passing. After linking the existing frozen input, all 21 cases passed in [green.log](green.log).

## Regression and checks

The production nomination fixture supplies twelve distinct scenarios with balanced wins/losses, giving a complete inconclusive interval. Before the fix, nomination returns `astra nomination panel incomplete`; [red.log](red.log) records the failing assertion. After the fix it returns `astra nomination did not pass`, keeps the champion, and reuses the same hash-bound panel on a second call without collecting again. Separate fixture cases retain incomplete classification for a missing reply or a faulted game.

Red command:

```bash
python -m unittest tests.v5.test_final_nomination.FinalNominationTests.test_complete_inconclusive_panel_is_reused_without_promoting
```

Green command:

```bash
python -m unittest tests.v5.test_final_nomination tests.v5.test_selection \
  tests.v5.test_evaluation_design tests.v5.test_final_budget
```

The unchanged nomination loop still requires `status == passed` for both Astra and champion comparisons and a higher retained score. This fix changes completeness classification and reuse, not the promotion criterion.

## Historical-panel check

The new `_panel_complete` predicate was also applied read-only to the original formal run's three nomination JSONs. [recorded_panels.json](recorded_panels.json) records paths, input hashes, completeness and original outcomes.

| Format | Complete blocks / distinct scenarios | New completeness | Unchanged strength outcome |
| --- | --- | --- | --- |
| Duel v940 | 12 / 12 | true | inconclusive, difference -0.25 |
| FFA v601 | 12 / 12 | true | inconclusive, difference -0.0590278 |
| Team v284 | 12 / 12 | true | not_passed, difference -0.4375 |

All have zero missing blocks and zero fault games. These checks satisfy the former F2 acceptance item. They do not establish improved strength or complete the remaining issue #222 work on trend-panel budgets and BC comparisons.
