# Teacher slow-value risk attribution — 2026-11-03

Two fixed legal duel boards reproduce a teacher scoring defect in both native
and Lite: adding an unrelated remote threat changes the chosen weapon from
faerie fire to entangle, although the attacked target, landing, combat forecasts
and target's potential damage do not change. The danger cost is zero in both
boards. No production scoring change or strength evaluation was made.

## Frozen design and identity

The design was declared before running: reuse the 13x13 fully visible legal-board
fixture, with a full-HP Elvish Enchantress at `(7,7)` and full-HP Dwarvish
Steelclad at `(8,7)`. Both have zero movement; leaders cannot act. The second
board adds one full-HP Troll Warrior at `(6,10)`, also with zero current movement.
It is not attackable by the Enchantress but enters the teacher's next-turn threat
map. Seed 713 is unchanged. The Steelclad has no ranged counter, and even four
faerie-fire hits cannot kill it. No alternative combinations or seeds were tried.

- Source: `c96369396efe214fcb9b1a382ed543c714d5880a`.
- Git archive SHA256, matching local and server:
  `8bd512eafca0bb85022e682e5318d581fdc8595e625b565771c8306ac92f8398`.
- Fresh Ubuntu extraction:
  `/home/tongshu/acceptance/teacher_slow_diagnosis_20261103`.
- Unchanged teacher: `probabilistic_combat_v6`, source SHA256
  `24aa546bbcce6670b0baef8751730d64c229b37cfe608d6cc59fd3e4c211eb98`.
- Rules: `1.18.8-combat-filtered`, SHA256
  `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`.
- Reused accepted v6 extension SHA256:
  `63b1c119670d4d0981925fafef4f781ab274f05fb0aa2fedafc8b24dfd503059`.
- Native executable SHA256:
  `33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf`.
- Entropy shim built from the extracted source, SHA256:
  `f12d763303445aa437de06d0dba129dc923e3d81fd1fc82d72b8e331916480cf`.

`teacher_score_trace.lua` is diagnostic instrumentation only. It calls the real
`wesnoth.simulate_combat` and `V.combat_score` with their original arguments and
returns their original values, attaching copies of their plain results to the
returned plan. It supplies no mock forecasts and changes no production module
or RPC. Its separate target-damage estimate uses the fixed neutral target's
actual weapons, the attacker's terrain defense and resistance, with turn-1 TOD
multiplier one. That estimate is not passed to the teacher.

## Command and observed results

From the extracted root, with `PYTHONPATH=.extension:.:vendor/arena`,
`OMP_NUM_THREADS=1`, `SDL_VIDEODRIVER=dummy`, `SDL_AUDIODRIVER=dummy`:

```sh
/home/tongshu/venv/bin/python tests/diagnose_teacher_slow.py \
  --rules data/rules/1.18.8-combat-filtered \
  --wesnoth /home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth \
  --source c96369396efe214fcb9b1a382ed543c714d5880a --output evidence
```

One query per board per backend, four teacher decisions total. Wall time is
2.7383 seconds; exit code 0 means the diagnostic's controlled-comparison
conditions hold, not that the scoring defect is repaired.

| Observed value | Target alone | Remote Troll added |
| --- | --- | --- |
| Chosen weapon, native and Lite | 3, faerie fire | 2, entangle |
| Target potential damage estimate | 19.8 | 19.8 |
| `risk` passed to the scorer | 0 | 24 |
| Ranged danger-cost margin | -44 | -35.6 |
| Native entangle score | 10.82590526315789 | 22.72870526315789 |
| Native faerie-fire score | 21.221052631578946 | 21.221052631578946 |

In each backend, both ranged forecasts are exactly equal across the two boards,
including every nonzero HP bin. Entangle deals 14 expected damage and has slow
probability 0.9919; faerie fire deals 33.6. Both have zero retaliation, kill and
death probabilities. Native and Lite differ only at floating-point roundoff in
these values. The chosen attack is legal in every query; no legal action attacks
the remote Troll. The target and landing remain `(8,7)` and `(7,7)`.

The score change is exactly `0.9919 * 0.5 * 24 = 11.9028`: `duel.lua` supplies
`danger(..., excluded=target.id)` as `risk`, while `value.lua` uses that same
other-enemy risk to value slowing the target. The negative danger-cost margins
show that the survival penalty does not account for the flip. No fatal-status
marginal contributes to this example.

## Evidence and limits

`evidence/alone.json` and `evidence/remote_threat.json` preserve the full specs,
real teacher plans, legal actions, public forecasts and scorer inputs/results.
`evidence/summary.json`, `diagnostic.log` and `diagnostic.exit` preserve the
comparison and process result. `git diff --check` passes; both added files are
below 1000 lines.

This is a diagnosis, not repair acceptance or a strength result. Neither proposed
scoring alternative was selected. No collection, training, strength-panel games,
Windows tests or production changes ran. The already accepted combat and board
evidence was not rerun. The separate fatal-slow valuation issue is not exercised
by these zero-death boards.
