# Paired Lite duel combat-choice acceptance

[#328](https://github.com/t66sun/wesnothLearning/issues/328) completed all 240 games with zero faults on Ubuntu cpuServer. The Astra-assisted arm scored **35.28%** against the frozen Astra opponent. Greedy v38 scored **41.39%**. The difference was **−6.11 percentage points** with a paired 95% interval of **[−13.89, +1.67]**. The frozen adoption gate required at least +5 points and a positive lower bound. The rule remains an experiment and greedy v38 remains the reference for this comparison. [Driver verdict](verdict.json) · [Independent recount](audit.json)

## Scores by board

| Lite board | Greedy v38 W/D/L | Greedy score | Astra-assisted W/D/L | Assisted score | Difference, pp |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fallenstar Lake | 13 / 30 / 17 | 38.33% | 7 / 34 / 19 | 30.56% | −7.78 |
| Sulla's Ruins | 23 / 11 / 26 | 44.44% | 18 / 18 / 24 | 40.00% | −4.44 |
| Equal-weight pooled | 36 / 41 / 43 | 41.39% | 25 / 52 / 43 | 35.28% | −6.11 |

Both arms used the same qualified v38 tensors, consumed the same frozen schedule and faced frozen Astra. The 120 paired slots match map, ordered factions, learner seat and initial combat seed. Both seat rotations are complete for all 30 blocks on each board. Official win, draw and loss scores are 1, 1/3 and 0. The recount uses the winner and learner seat from each reply and the fixed 10,000 paired block resamples within maps. The interval includes zero. The result covers this checkpoint and the two Lite layouts, each with two documented hill-village substitutions. [Frozen design and map provenance](../duel_combat_choices_20261114/REPORT.md)

## Decisions and time

| Lite board | Games with a change (of 60) | Astra queries | Changed | Same | Absent combat intent | Noncombat intent | Greedy worker min | Assisted worker min |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Fallenstar Lake | 60 | 6,152 | 1,814 | 2,431 | 1,339 | 568 | 24.73 | 25.56 |
| Sulla's Ruins | 60 | 5,215 | 1,726 | 2,162 | 835 | 492 | 15.82 | 16.74 |
| Total | 120 | 11,367 | 3,540 | 4,593 | 2,174 | 1,060 | 40.55 | 42.30 |

The greedy arm issued zero Astra queries and picked 11,172 combat actions. The assisted arm changed 31.14% of its 11,367 combat picks. Worker minutes sum the recorded per-game execution time within each arm. The arms shared eight workers and ran from 11:43:09 to 11:53:56 Asia/Shanghai on 2026-11-15. The driver's active wall clock was **648.262 s** of the allotted 3,600 s, covering 0.854 s for preparation, 647.092 s for games and 0.316 s for the audit. All phase budgets passed and the launcher exited zero.

## Reproduction and identities

The [frozen invocation](../duel_combat_choice_worker_20261114/REPORT.md) ran once from the prepared Git archive after authorization. It used the source and inputs below. The [launch manifest](launch.json), [compressed schedule](schedule.json.gz), [compressed raw replies](results.jsonl.gz), [worker-pool timing](results.throughput.jsonl), [run start](run-start.json) and [exit code](launcher.exit) preserve the execution. [Archive checksums](SHA256SUMS)

| Input | Identity |
| --- | --- |
| Source commit | `c6aeba9c04cd4bd9559f56ec2a0c33685c731c15` |
| Git archive SHA-256 | `eb7021f15c7fbb7e61e2dff85ca587e17c470882ca0838645bd7d896f7bbe12f` |
| Launch SHA-256 | `2dcc6cc1ae1dfcce57511089dd03ede4adedb505c44fbfbf05177bc7e5789dda` |
| Schedule SHA-256 | `7923fe2217d8b72f8c79fb5a5946987fd0c5a392b2882d2b510f04974216ec23` |
| Raw replies SHA-256 | `c2b63d035f89b96b616dafe7ca78a137ad656105f9b345afa5189e5c238f0685` |
| v38 checkpoint SHA-256 | `8fc61bbb0be5c2ad8d2ec5b56760ce3dbfa08eed008c490e9b2233624ea91ebe` |
| Lite extension SHA-256 | `56dd77140411db987377d6de4ffbf562da4d0e5c76bc16d34780da67e60e5ae4` |
| Frozen rules SHA-256 | `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17` |
| Astra strategy SHA-256 | `d64e1178c0a8af9b1b10e2626f03e7cb8ed70a5a368d3c38860d40723a903eb5` |
| Astra package SHA-256 | `2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933` |

The independent recount ran on Ubuntu from `69fb3993719fd1a4d2718aff135efa7e5bf11759` (audit archive SHA-256 `e3c691e70814e940a1d78b919da6c6d7e8d5a6619a1599db0f7daf9666ac76c9`). From the repository root, the same command can read the archived compressed copies.

```sh
evidence=verification/duel_combat_choice_strength_20261115
python3 "$evidence/recount.py" "$evidence" verification/duel_combat_choices_20261114/inputs.json
```
