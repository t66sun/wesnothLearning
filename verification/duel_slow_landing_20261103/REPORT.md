# Duel slow reward across attack landings

On the accepted b0025 replay prefix the repaired teacher selects the Shaman's own village. The only production change is in the duel strategy. When estimating the benefit of slowing a target, it uses the attacker's defense on its current hex as a common reference for that decision. Target weapon damage, resistances, alignment, target HP and the probability of a surviving slow continue to determine the benefit. Risk from other enemies and the landing defense bonus still use the proposed destination. [Native diagnosis](../duel_landing_diagnosis_20261103/REPORT.md)

## Fixed-board results

| Evaluation | Village (21,19) | Grass (20,18) | Selected |
| --- | ---: | ---: | --- |
| Original compatible control | 6.191404 | 5.891404 | Village |
| Previous adapted teacher | 5.516452 | 6.138977 | Grass |
| Repaired adapted teacher | 6.438977 | 6.138977 | Village |

The previous teacher credited target damage of 4.392973 in the village and 6.589459 on grass. With the common pre-move defense it credits 6.589459 in both places. Both have 0.84 slow probability, zero kills, zero retaliation and zero other-enemy risk. The village's +0.30 defense advantage decides the ranking. The native probe matched the original 191-command prefix (SHA256 `b74ea71ba2adda873b0b7f6763ad2dc62ad3b446ac1202e89dd3469b05d4eb5f`), enumerated 18 candidates and finished before its cutoff. The winning plan attacks the same Cavalryman with the same entangle weapon. [Repaired scores](summary.json)

The independent Lite regression uses a ranged slower with several reachable attack hexes around the same non-ranged target. Only the village offers the higher defense. The old source chose grass (8,6) and failed the expected protected landing (7,7). The single changed production file made the same regression pass. [Before](red.log) · [After, with native records](fixed-board-records.tar.gz)

The earlier fixed tactical boards give the attacker zero moves, so every evaluated attack landing is its original hex. For these inputs the old and new hit chances are equal. This permits reuse of the 18 fixed-board results, the unrelated-threat pair and the low-HP lethal-slow board. Four-player routing and the shared value module are outside the production diff. The independent duel strength result requires its prospective native panel. [Prior target-attribution cases](../teacher_slow_attribution_20261103/REPORT.md) · [Prior lethal-slow case](../teacher_surviving_slow_20261103/REPORT.md)

## Ubuntu reproduction

| Build | Shipped commit | Git archive SHA256 | Ubuntu directory under `/home/tongshu/acceptance/` |
| --- | --- | --- | --- |
| Red | `98866e532829edfbe76006153f7164a709c4fd96` | `26dcb2024512136901a0e46d72b1ddea7376d4949b019f3e7e1666f91b86fbd2` | `duel_slow_landing_red_20261103` |
| Green | `69b4e0b22d7c8ff0c10b2c8319e789f32b692c34` | `af27466b000a14327e48356cc3091f0e593c97e15c359e85501040aec6457fe0` | `duel_slow_landing_green_20261103` |

Both use the accepted v6 extension from `teacher_immunity_checked_20261103/.extension`, the shipped source and `vendor/arena` on `PYTHONPATH`. The native check uses dummy SDL, one numerical thread and the entropy shim built from the green archive. The executable, shim, package and duel/value source hashes are in the repaired score file. New teacher source SHA256 is `d64e1178c0a8af9b1b10e2626f03e7cb8ed70a5a368d3c38860d40723a903eb5`.

```sh
/home/tongshu/venv/bin/python -m unittest tests.v5.test_astra_adaptation.AstraAdaptationTests.test_duel_slow_does_not_reward_an_exposed_landing -v
# From the green directory
/home/tongshu/venv/bin/python tests/diagnose_teacher_landing.py \
  --panel /home/tongshu/acceptance/teacher_noninferiority_20261103/panel \
  --source 69b4e0b22d7c8ff0c10b2c8319e789f32b692c34 --variant challenger \
  --challenger learning/teachers/gpt6astra --output challenger
```

Red exited 1 in the Lite regression (0.032 seconds). Green exited 0 in the Lite regression (0.024 seconds) and the single native board probe exited 0. The green archive retains the native replay, event trace, logs, staged code, summary and exit records. Its local and Ubuntu SHA256 is `2d635413a468504613747ac368111a052ed1df5cd74b972bd1e25585e49706bf`.
