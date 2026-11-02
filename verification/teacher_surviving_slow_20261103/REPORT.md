# Teacher slow benefit excludes fatal outcomes

Ubuntu cpuServer, 2026-11-03. This fixes the exact lethal-slow choice recorded in `verification/teacher_lethal_slow_20261103/`. No numerical tuning, production forecast change, collection, training or strength games.

## Change and observed result

Only `V.combat_score` changes production behavior: when the target was not initially slowed, slow benefit uses `max(0, slow - kill)`. Native slow probability includes fatal hits; dead targets retain no future damage or movement benefit. Poison, risk costs, numerical coefficients and four-player exposure remain unchanged.

The existing diagnostic now requires a legal weapon-3 choice on both backends. The adaptation suite adds one behavioral comparison: an all-fatal slow attack has the same score as the otherwise identical all-fatal attack without slow.

- Red source `ed62f88f9b9a6d592c0610e7ef208283614029a8`: adaptation fails `92.0 != 80.0`; native and Lite choose weapon 2, so the fixed-board check fails. Both commands exit 1.
- Green source `9118fac3628542b585a35f27d2115560057d4ddc`: all 3 adaptation tests pass; native and Lite legally choose weapon 3. Both commands exit 0.
- Entangle score changes from 40.5290358421 to 31.9645244211. Faerie-fire score remains 33.5784252632. Kill probabilities remain 0.9163 and 0.9919 respectively. Entangle's slow marginal remains 0.9919, with only 0.0756 surviving slow probability.

The predeclared board is unchanged: Enchantress / Steelclad, defender HP=8, positions 84 / 85, leaders 78 / 168, all moves=0, no Troll, seed 713. Each red/green run queries this board once per engine. Red wall time is 1.371282 seconds; green is 1.368884 seconds.

## Commands and evidence

Each committed source was shipped using `git archive` and extracted into a new Ubuntu directory:

- `/home/tongshu/acceptance/teacher_surviving_slow_red_20261103`
- `/home/tongshu/acceptance/teacher_surviving_slow_green_20261103`

Both use the accepted v6 extension and frozen combat-filtered rules via symlink; the entropy shim is compiled from each shipped source. From each extracted root:

```sh
export PYTHONPATH="$PWD/.extension:$PWD:$PWD/vendor/arena" OMP_NUM_THREADS=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
/home/tongshu/venv/bin/python -m unittest tests.v5.test_astra_adaptation -v
/home/tongshu/venv/bin/python -m tests.diagnose_teacher_lethal_slow \
  --rules data/rules/1.18.8-combat-filtered \
  --wesnoth /home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth \
  --source "$SOURCE_COMMIT" --output evidence
```

`SOURCE_COMMIT` is the exact red/green source above. Raw output is preserved under `red/` and `green/`: `python.log`, `lethal_board.log`, `exit-codes.txt`, `evidence/board.json`, `evidence/summary.json`.

## Identities

- Red source archive SHA256: `98bc5027e0c1d21d2d5cf0528026e1e7014e86652c5ea89282118550cbe89c69`.
- Green source archive SHA256: `79838efc62399020802684e3ff2c3dfdda78cd9780da6cfbfb1347f021d726de`.
- Red teacher SHA256: `02ea1d360add0950be8db9cf11d9c2997ad1ad8ae2562f31bc44ab69c2d0311a`.
- Green teacher SHA256: `ad75d870ce68fa6b489ad922fd8bb3059e29bbe7626f296e74d2b6fad828c7d4`.
- Extension SHA256: `63b1c119670d4d0981925fafef4f781ab274f05fb0aa2fedafc8b24dfd503059`.
- Rules SHA256: `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`.
- Native executable SHA256: `33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf`.

## Reuse and limits

The prior target-attribution pair in `verification/teacher_slow_attribution_20261103/green/pair/` has kill probability zero for every weapon. With unchanged forecasts, `max(0, slow - 0)` equals its original nonnegative slow marginal, so those choice results remain applicable without repeating the pair. Engine and other combat evidence remain unchanged.

This proves the specific fixed-board scoring regression. It does not establish strength or close the R3 gate; that requires the separately coordinated unchanged panel. No additional seed, board sweep, wrapper or error-handling mechanism was introduced. Changed source files remain below 1000 lines.