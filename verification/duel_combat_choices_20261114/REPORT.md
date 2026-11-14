# Frozen duel combat-choice opportunity and design

[#326](https://github.com/t66sun/wesnothLearning/issues/326) passed on cpuServer. The v38 policy chose a different retained combat action from Astra on **546 of 1,936** greedy combat decisions (**28.20%**) across **60** complete validation games and **two** physical boards. The gate required 5%, 12 games and two boards. These are teacher trajectories re-scored with the frozen greedy v38 tensors and the original complete committed turn histories.

| Validation board | Decisions | Greedy combat | Different retained combat |
| --- | ---: | ---: | ---: |
| Arena2 | 2,746 | 1,198 | 350 |
| Weldyn Channel | 1,956 | 738 | 196 |
| Total | 4,702 | 1,936 | 546 |

Of the other greedy combat choices, 736 matched exactly, 302 lacked the Astra combat intent in the candidate list, and 352 had a noncombat Astra intent. The 546 differences include 211 target, 448 landing and 176 weapon changes. Categories overlap. [Counts, inputs and witnesses](opportunity.json)

## Paired evaluation

Use the frozen greedy v38 decision as the control. The variant queries the existing Astra planner when greedy selects attack or move-attack. It selects a different retained action only on an exact combat intent match. Both roles play the same frozen Astra opponent under the official 30-round duel task.

Fallenstar Lake and Sulla's Ruins are derived from Wesnoth 1.18.8 two-player maps. Each had two mountain-village composite tiles (`Mm^Vhh`) outside the frozen Lite catalog. The experiment copies use the supported hill village `Hh^Vhh` at those four positions, with all village sites retained. Results apply to the derived Lite boards. The current catalog had no pair of unmodified, eligible and independent village-bearing layouts. The original and derived physical hashes differ from every audited prior board and both #322 reservations. [Map changes and hashes](inputs.json) · [Historical exposure set](exposure.json)

For each map, use the 30 ordered nonmirror faction pairs and both learner seats under the recorded combat seeds. Each role plays 60 games per map, for 120 paired slots and 240 games. Use eight workers. The 60-minute limit budgets 10 minutes of preparation, 45 minutes for games and five minutes for audit. Score wins, draws and losses as 1, 1/3 and 0. Average the two rotations within each scenario and weight the maps equally. Use 10,000 paired bootstrap draws resampling scenario blocks within maps, driven by seed 2026111459. The variant passes with at least +5 percentage points and a positive 95% lower bound, given complete fault-free task-terminal results within budget.

## Reproduction

The opportunity audit ran from source `180401066da54cfd7bca34fd56364ae9972f9909`, Git archive SHA-256 `5fb89a0749d3c95e9163e04895539152808bb9c444442f7f50499232223650f9`. It took 27.67 seconds. The static preflight ran from `9422df4c27bd2c79bdc249e0b4d6c538a586e666`, archive SHA-256 `6fe5253d630f1d53d217f7d982ab07e1539af39726c27cf32c60de107fc293d2`. The preflight source archive uses the separately provisioned historical 1.18.8 map tree for exposure checks and schedule generation. Neither step started games.

```sh
base=/home/tongshu/acceptance
op=$base/duel-combat-20261114-n6xzRf
design=$base/duel-combat-20261114-R3PckZ
ext=/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export WESNOTH_RULES_DIR=$base/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
cd "$op/source"
PYTHONPATH="$PWD:$ext" /home/tongshu/venv/bin/python -m verification.duel_combat_choices_20261114.opportunity \
  "$op/opportunity-recount.json" 180401066da54cfd7bca34fd56364ae9972f9909 "$op/source.tar"
cd "$design/source"
PYTHONPATH="$PWD:$ext" /home/tongshu/venv/bin/python -m verification.duel_combat_choices_20261114.protocol \
  "$design/design-recount" "$op/opportunity.json" 9422df4c27bd2c79bdc249e0b4d6c538a586e666 "$design/source.tar"
```
