# Weapon retention at the shared candidate cutoff

Ubuntu `cpuServer`, 2026-11-07. [#273](https://github.com/t66sun/wesnothLearning/issues/273) · [#228 witness](../candidate_support_20261106/REPORT.md)

On `combat_slots`, the decision now offers the Elvish Marksman's ranged attack from `(9,3)` against the 20 HP Orcish Grunt at `(9,4)`. Weapon 2 replaces weapon 1 in the same slot. The ranged attack has a 47.52% kill chance, 17.1072 expected target damage and zero expected own damage. The displaced melee attack has zero kill chance, 7.2 expected target damage and 10.8 expected own damage. Both have zero own death chance. [Red assertion](red.log) · [Native/Lite forecasts](native.json)

The generator compares weapons only when the initial allocation retains a sibling and excludes a challenger for the same actor, target and landing. It reserves one forecast per retained combat slot and spends spare calls on the split groups. A challenger must improve at least one of the public HP, kill, death, slow or poison outcomes and be at least as good on the others. A plausible plague conversion or an exposed disabling special outside those forecast fields protects the incumbent. The slow and Necromancer plague controls retain their status-bearing weapons even though the ranged alternatives improve immediate HP outcomes. Primary full moves, recruit-type coverage and end turn pass their existing controls. The candidate identity is `schema5-work-12000-v9`. [Green checks](green.log) · [Plague guard reverted](plague-red.log)

## Paired cost

The panel ran the unchanged production decision path once to warm each arm and twice to measure it, alternating v8/v9 and v9/v8. Construction uses the generator's integer millisecond clock. Decision wall time covers observation, construction, DTO serialization and Python decoding. The independent call-count test wraps the actual Lua combat API outside the timed path and asserts one call per forecasted intent, accurate reporting and nonzero reuse. [Raw measurements and replaced slots](timing.json) · [Host window](host.txt)

| State | Candidates | Construction v8 → v9, ms | Decision v8 → v9, ms | Actual forecasts v8 → v9 | v9 reuses | Work v8 → v9 |
| --- | ---: | --- | --- | --- | ---: | --- |
| #228 `combat_slots` | 37 | 8, 7 → 8, 8 | 13.04, 13.08 → 13.16, 12.71 | 28 → 32 | 4 | 1,980 → 2,100 |
| Recorded FFA turn 7, side 1 | 37 | 15, 15 → 15, 15 | 20.86, 20.91 → 20.53, 20.30 | 28 → 32 | 4 | 8,016 → 8,136 |

The second state uses the 29 live units, map, ownership, current side and turn from `bc_priority_20261101.json` with fresh observation history under the current combat profile. Both variants read the same reconstructed board. The first attempted archived turn had an eliminated side and could not initialize a fresh game. The replacement uses a recorded turn with every side alive. The #228 state replaces four melee attacks with ranged siblings. The recorded state replaces one moving attack's weapon at landing `(6,10)` against target `(7,10)`. The exact 120-work increase in each state is four forecasts at 30 work each. Two warmed observations per arm show similar decision costs on these positions. Wider throughput and playing strength remain questions for [#275](https://github.com/t66sun/wesnothLearning/issues/275).

## Checks and identities

- The original v8 witness exits 1 because it retains weapon 1. The v9 build without the plague guard exits 1 because it displaces the Necromancer's plague staff. The final build passes all 46 affected checks. The retained ranged action is legal in native 1.18.8, and both engines agree on its candidate features, full HP probability masses, mean HP, and slow/poison marginals at `1e-9`. One native attack exercised the existing differential oracle. The first native attempt stopped before startup because its archive subset omitted the frozen Astra asset. The completed probe used the existing asset with the recorded digest. [Initial native input error](native-missing-input.log)
- Four older movement snapshot checks stop before candidate generation with `snapshot version mismatch` on v8 and v9. The captures specify `expected_damage_v1` while the current extension requires `probabilistic_combat_v6`. These checks provide no new movement acceptance. The current primary-move and public-context checks pass in the 46-test result. [Baseline restore output](legacy-v8.log) · [Changed-source restore output](legacy-v9.log)
- Rules SHA256 `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`. Lite extension SHA256 `56dd77140411db987377d6de4ffbf562da4d0e5c76bc16d34780da67e60e5ae4`. Native executable SHA256 `33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf`. Frozen Astra asset SHA256 `2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933`. The recorded FFA fixture SHA256 is `eda37a7b2b943363211df1d3143662c4978ef91054becaae2f5323b8a58742e5`.

The branch starts at `07db85b8ba4def9bfebc7b42fe4c7bec0c4fd1b0`. Each source subset was shipped with `git archive --format=tar.gz` and extracted under `/home/tongshu/acceptance/`.

| Purpose | Shipped commit | Archive SHA256 | Fresh directory |
| --- | --- | --- | --- |
| v8 witness and timing control | `7bc652072f3566281e9ef43ca239007bb1950888` | `2f40ff1de0918899397d5049b7c17a01fc3d322e84e2119ef8d6026f7a27e309` | `candidate_weapon_red_20261107` |
| First v9 check with legacy restore cases | `5e7ced0d35b3c8de9f909305c6a7c27e83fc96b8` | `c2a6fdcf027141bda1ee74e2944899fc0185191bf8c29a1b45c261fad64d88d0` | `candidate_weapon_green_20261107` |
| v9 without plague protection | `d46895b16762e227820d3a6d13539484494c56f3` | `5470e706ef1d10ebe025556be75fdea75427525798f865b583b6735484b0871c` | `candidate_weapon_plague_red_20261107` |
| Final v9 | `0d51078d5762ab7e1da7be713bf34b6de8b4008b` | `3e696882a0498ed22ed797dd8d940a36cb5ae97dd0d0ee3dfda69e4f699ca18e` | `candidate_weapon_final_20261107` |

Use the archived filtered rules and v6 extension, and link the frozen Astra asset at `data/opponents/gpt6astra.zip` for the native command. These commands use `/home/tongshu/venv/bin/python`, one numerical thread and dummy SDL for native. Each probe writes a fresh output path.

```bash
export PYTHONPATH="$PWD:/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension:$PWD/vendor/arena"
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
python=/home/tongshu/venv/bin/python
probe=verification/candidate_weapon_retention_20261107/probe.py
"$python" "$probe" --baseline ../candidate_weapon_red_20261107 \
  --real-board data/datasets/diagnostic/bc_priority_20261101.json --output ../timing-new.json
mkdir .runtime
cc -O2 -fPIC -shared -o .runtime/entropy.so vendor/arena/entropy.c -ldl
"$python" "$probe" --wesnoth /home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth \
  --output ../native-new.json
"$python" -m unittest tests.v5.test_candidate_weapon_retention tests.test_candidate_budget \
  tests.test_lua_contracts tests.v5.test_candidate_pool_budget tests.v5.test_candidate_provenance \
  tests.v5.test_candidate_gating tests.v5.test_duel_hurt_branch tests.v5.test_tactical_inputs \
  tests.v5.test_forecast_public_context -v
```
