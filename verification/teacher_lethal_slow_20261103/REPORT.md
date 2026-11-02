# Fatal slow teacher choice diagnosis

Ubuntu cpuServer, 2026-11-03. One predeclared board, one teacher query per backend. No scoring change, board sweep, action execution, collection, training or strength games.

## Observation

Native and Lite choose entangle (weapon 2), with kill probability 0.9163 and score 40.5290358421, over faerie fire (weapon 3), with kill probability 0.9919 and score 33.5784252632. Both choices are legal. The actual teacher receives target_damage 14.6936842105 and other-enemy risk 0. Both ranged attacks have no retaliation, and the danger penalty is inactive.

The entangle forecast is HP 0 with probability 0.9163, HP 3 with probability 0.0756, HP 8 with probability 0.0081, and slowed marginal 0.9919. This initially unslowed target cannot advance in this combat; every entangle hit slows it. Thus only the 0.0756 HP-3 branch is a living slowed target. The remaining 0.9163 slow marginal describes dead targets and cannot prevent future damage or movement. The current slow bonus rewards it anyway.

This agrees with the read-only prior native/Lite evidence in `verification/combat_boundaries_20261102/tactical/lethal_slow.json`: initial HP 1, final HP 0 probability 0.84, HP 1 probability 0.16, slowed 0.84. The prior forecast contract includes fatal hits, so the teacher's benefit calculation owns the error.

## Fixed inputs and command

Reuse `diagnose_teacher_slow.position(rules, False)` unchanged except defender HP=8. Enchantress at 84, Steelclad at 85; leaders 78 and 168; all moves=0; seed 713; no Troll. The existing trace wrapper passes real forecasts and score calls through unchanged.

Source commit: `b8e8399839b0da675f17d90bc3ddfdc652750c79`, based on `87a31bffe5303d996077a6c89413a8168f3a0ae6`.

Fresh server archive directory: `/home/tongshu/acceptance/teacher_lethal_slow_diagnosis_20261103`.

```sh
export PYTHONPATH="$PWD/.extension:$PWD:$PWD/vendor/arena" OMP_NUM_THREADS=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
/home/tongshu/venv/bin/python -m tests.diagnose_teacher_lethal_slow \
  --rules data/rules/1.18.8-combat-filtered \
  --wesnoth /home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth \
  --source b8e8399839b0da675f17d90bc3ddfdc652750c79 --output evidence
```

Exit 0 means the diagnostic completed, not that the behavior passed acceptance. Wall time 1.371366 seconds. Raw output: `diagnostic.log`, `diagnostic.exit`, `evidence/board.json`, `evidence/summary.json`.

## Identities

- Source archive SHA256: `daeadf5895e3e0d9d20f05a0b3432c21da9d3b0e1cedf2105e9a7bfa27469b29`.
- Teacher source SHA256: `02ea1d360add0950be8db9cf11d9c2997ad1ad8ae2562f31bc44ab69c2d0311a`.
- Extension SHA256: `63b1c119670d4d0981925fafef4f781ab274f05fb0aa2fedafc8b24dfd503059`.
- Rules SHA256: `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`.
- Native executable SHA256: `33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf`.
- Entropy shim SHA256: `f12d763303445aa437de06d0dba129dc923e3d81fd1fc82d72b8e331916480cf`.

## Next minimal change

Make the fixed board require actual weapon 3 on both backends, and add one all-fatal slow behavior comparison. Then remove the fatal part only from the shared slow benefit, leaving native/Lite forecasts, poison, coefficients and four-player exposure unchanged. This board establishes the specific error, not full-game strength.