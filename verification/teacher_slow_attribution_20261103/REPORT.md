# Teacher slow benefit follows its target — 2026-11-03

The maintained teacher now values slowing the attacked target using that target's existing damage estimate. Other enemies' threat remains an input to the existing danger cost, but no longer increases the target's slow reward. No scoring constant, forecast, RNG, rule package or frozen opponent changed.

## Diagnosis and change

The fixed counterexample is preserved in `verification/teacher_slow_risk_20261103/REPORT.md`. Adding an unattackable remote Troll changed the real native and Lite teacher from faerie fire to entangle, although the target, landing and complete combat forecasts were identical and the danger penalty remained zero. The additional reward was exactly `0.9919 * 0.5 * 24 = 11.9028` from the wrong enemy.

Each existing `danger()` scan now returns the excluded target's damage estimate separately as its third result. The other enemies retain the same sorting, four-threat cap, HP weighting and aggregation. All three strategy callers pass `target_damage`; `V.combat_score` consumes it only for the slow benefit. The existing first two danger results and risk cost are unchanged. There are no additional forecasts, caches, exception handlers or runtime assertions.

This is an input-attribution repair using the existing damage model and constants, not a parameter search. Fatal slow marginals and the existing four-player exposure approximation are outside this change.

## Source and commands

Each committed source was sent as a git archive and extracted into a fresh Ubuntu directory:

| Phase | Commit | Archive SHA256 | Directory under `/home/tongshu/acceptance/` |
| --- | --- | --- | --- |
| Red: new behavioral expectation, old production score | `f820df13a745d7be1b4313c77f4be8a05bc4ba1f` | `04a38e6f554cb29b2086dbe1fa220d7f328f29b95e1c86421eed353eebaa66a9` | `teacher_slow_attribution_red_20261103` |
| Green: repaired target attribution | `cbee1cf4ec48fe204a3cded7513680e57642def6` | `b5f608a2369bf2587e4966e48716acaf599f7144c48c5c38d7cebe33ccc3c5bb` | `teacher_slow_attribution_green_20261103` |

Teacher profile remains `probabilistic_combat_v6`. Its source hash changes from `24aa546bbcce6670b0baef8751730d64c229b37cfe608d6cc59fd3e4c211eb98` to `02ea1d360add0950be8db9cf11d9c2997ad1ad8ae2562f31bc44ab69c2d0311a`; old manifests and rows are not relabelled. Captured rules SHA256 is `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`, native executable `33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf`, and the unchanged accepted v6 extension is reused from `teacher_immunity_checked_20261103/.extension`.

From each extracted root, with `PYTHONPATH=.extension:.:vendor/arena`, `OMP_NUM_THREADS=1`, and dummy SDL video/audio drivers:

```sh
/home/tongshu/venv/bin/python -m unittest tests.v5.test_astra_adaptation -v
/home/tongshu/venv/bin/python tests/diagnose_teacher_slow.py \
  --rules data/rules/1.18.8-combat-filtered \
  --wesnoth /home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth \
  --source <phase-commit> --output pair
```

On green only, the existing affected case is also run in all three formats:

```sh
/home/tongshu/venv/bin/python tests/diagnose_teacher_boards.py \
  --rules data/rules/1.18.8-combat-filtered \
  --wesnoth /home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth \
  --source cbee1cf4ec48fe204a3cded7513680e57642def6 \
  --case slow_weapon --output slow_boards
```

## Observed result

| Check | Red | Green |
| --- | --- | --- |
| Three existing adaptation tests | One behavioral failure: 2.0 is not greater than 6.0; exit 1 | 3/3 pass; exit 0 |
| Fixed pair, real native and Lite teacher callers | Weapons 3 then 2; stability assertion fails; exit 1 | Weapons 3 then 3; exit 0 |
| Existing `slow_weapon`, duel / ffa4 / team2v2 | Not repeated | 3/3 pass; exit 0 |

The value-level test now supplies the intended target damage and keeps its weapon comparison; its redundant assertion of the exact helper constant was removed. The full pair regression asserts the same ordinary attack remains selected when only the unrelated threat changes. Both backends execute their real teacher and forecast functions through diagnostic wrappers that do not alter arguments or results.

In the green pair, the actual caller supplies `target_damage=19.8` on both boards, while other-enemy `risk` still changes from 0 to 24. Native entangle score stays `20.64571526315789` and fire stays `21.221052631578946`. Both danger-cost margins remain negative (-44 and -35.6). Target, landing, legal choices and ranged HP/status distributions match across the pair. The pair takes 2.706 s and the three existing slow cases 8.083 s; these are fixture durations, not performance acceptance.

Raw logs, exit codes, full board specs, public predictions, scorer inputs and plans are preserved under `red/` and `green/`. No failed artifact was replaced. No additional board combination or seed was searched.

## Limits

This accepts the target-attribution repair on the exercised paths, not teacher strength. The separate R3 panel must record the new source identity; the previous strength report cannot stand in for this changed scorer. Unchanged combat, immunity and unrelated tactical evidence remains at its original paths. No collection, training or Windows tests ran. All changed files are below 1000 lines and the source diff check passes.
