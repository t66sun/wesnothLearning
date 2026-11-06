# PPO training scenario coverage

Issue: [#223](https://github.com/t66sun/wesnothLearning/issues/223). Date: 2026-11-06.

## Result and scope

PPO now schedules the eligible cross-product of training maps, ordered rosters of distinct factions and learner seats. A 72-game duel cycle or 96-game four-player cycle balances each map/learner-seat/learner-faction stratum, including cycles starting at nonzero batch indices. Within each stratum, eligible rosters rotate independently of the map selection. This removes the old three-roster limitation without changing the physical scenario split, the no-drop batch contract, opponent proportions, learner rotation, seeds or frozen policy paths.

The accepted checks cover scheduling, eligibility and resume wiring. They do not establish improved strength or convergence. No matches, collection or formal training were started. Existing bounded unit fixtures execute synthetic optimizer updates only.

## Original failure and intended mixture

The [read-only architecture audit](../ppo_architecture_audit_20261106/REPORT.md#2-confirmed-ppo-distribution-collapse) found only three ordered faction rosters and six physical scenario families in 3,608 completed duel PPO games, and three rosters and seven families in 928 team games. Increasing the seed-bearing `game_family` count did not expand physical `scenario_family` support. Team learner-faction counts ranged from 115 to 193.

The original map decorator's intended training mixture was already 50% synthetic arena, with the remaining 50% divided equally among native training maps. The coupled map/faction eligibility search did not preserve that mixture: the recorded team census had 464 arena games, 155 Clash games and 309 Isar's Cross games. The new design retains the intended weights; it does not tune a new map curriculum.

## Design

`learning/rollout_scenarios.py` owns the PPO-only composer; `learning/schedule.py` delegates to it. BC, calibration and evaluation generators retain their existing behavior.

For `N` players, six factions and `M` native training maps:

1. The existing `rollout_jobs` sequence produces every learner seat once per group of `N` games. Its absolute request index supplies the group ordinal.
2. A cycle has `N * 6 * (2 * M)` games. Each map slot, learner seat and focal faction appears exactly once. The `M` repeated arena slots preserve the 50% arena share.
3. Each physical map enumerates all `6PN` ordered rosters of distinct factions (30 duel, 360 four-player), retains only `split(scenario_family) == 'train'`, then groups them by learner seat and faction.
4. Successive visits round-robin each eligible roster pool. Repeated arena slots advance the same pool; they do not repeat its first roster. An empty required stratum raises before collection.

Eligibility cache keys contain the full `scenario_identity` except the roster being enumerated, plus the frozen faction inventory. Identity includes board/starts, teams, format, engine/combat version, rule hash/version, turn cap and visibility settings. It excludes random seed, bot paths, policy version and opponent weights. The cache is an optimization; cold and warm generation produce equal complete job dictionaries.

The scheduler recomputes `game_family` and binds `scenario_family` after roster selection. `meta.eligibility_swap` records the design version, request index, selected map slot, learner seat/faction, roster index, eligible pool size and balance-cycle length. Existing opening-probe handling still removes this PPO-only metadata. The coordinator continues to bind the actual rules/engine/cap before composing and freezes each schedule before execution. Persisted schedules are replayed verbatim under their pinned source identity; this change adds no legacy sampler fallback.

Exact stratum balance does not imply equal weight for every eligible roster: pool sizes differ under the existing hash split. Nor does one balance cycle exhaust the full physical scenario support. These are separate counters and assertions.

## Observed support and cost

[Machine-readable measurement](schedule_measurements.json), seed 19, max turns 60, frozen rules listed below:

| Format | Games per balanced cycle | Map counts in one cycle | Equal count per learner faction | Physical scenarios in first cycle | All eligible physical scenarios |
| --- | ---: | --- | ---: | ---: | ---: |
| duel | 72 | arena2 36; each of 3 native maps 12 | 12 | 53 | 95 |
| ffa4 | 96 | arena4 48; Clash 24; Isar's Cross 24 | 16 | 70 | 879 |
| team2v2 | 96 | arena4 48; Clash 24; Isar's Cross 24 | 16 | 69 | 868 |

Physical support by map is duel arena2 26, The Freelands 25, Weldyn Channel 24, Sablestone Delta 20; FFA arena4 303, Isar's Cross 290, Clash 286; team arena4 294, Isar's Cross 284, Clash 290. Every eligible roster is reachable with every learner seat. The largest observed map/seat/faction pools have 5, 54 and 55 rosters respectively, giving conservative complete-support bounds of that many balance cycles. The regression assertion independently enumerates the allowed support and compares it with the actual `rollout_jobs` sequence over 5 duel cycles and 60 four-player cycles, starting at batch 53. The larger four-player test bound is the unsplit `5P3 = 60` roster bound.

| Format | Cold full-cycle wall / CPU | Warm full-cycle wall / CPU | Cold eligibility misses |
| --- | --- | --- | ---: |
| duel | 31.14 / 31.14 ms | 25.41 / 25.41 ms | 4 |
| ffa4 | 62.54 / 62.54 ms | 36.11 / 36.11 ms | 3 |
| team2v2 | 62.77 / 62.77 ms | 35.33 / 35.33 ms | 3 |

Cold means the eligibility cache was cleared, not a cold filesystem or interpreter. Each row is one full schedule construction measurement, including existing job construction and identity work, followed by one warm repetition. The cold/warm differences were 5.73, 26.43 and 27.44 ms. These are bounded observations, not a collection throughput benchmark or an estimated training speedup. The host was shared with other acceptance work.

## Assertions and execution results

- **Valid red:** [red.log](red.log), source `bdd996fff410ea6759e8efc4569f91b519f52418`. The old composer fails the new balance assertion in all nine format/start-index cases: one test, nine subtest failures, zero errors, 0.157 seconds, exit 1. This demonstrates failure when the behavior change is absent.
- **Green:** [green.log](green.log), source `482064132745f145c604fd6dee03cb3e32e667ef`. All 31 affected Ubuntu tests pass in 9.864 seconds, exit 0. The suite checks the actual rollout sequence, starts at batches 0/38/53, learner-side alignment, every eligible roster/seat, split/map exclusion, seed/policy/version independence, no-drop eligibility, actual engine/turn-cap rebinding, frozen schedule replay and PPO resume counters. A fixture deliberately prints `FAIL BC execution or bounded batch/time limit`; the unittest run ends `OK`.
- **Initial setup failure:** [setup_failure.log](setup_failure.log), source `f9b91829717a3247cc44b4303c5184846cc17c8e`. The first test attempt imported vendored `params` before `learning.common` had added its path. It ran no behavior assertion and is not counted as red evidence. The next test-only commit fixed import order.
- **Measurement:** source `38b7a206ce9a7bad4b2c1e1179976505da26d86f` adds only [measure_schedule.py](measure_schedule.py) to the green source. Production and test files are byte-identical to the green commit.

Commands run from the fresh source directory, after provisioning the existing frozen maps:

```sh
mkdir -p data/rules
ln -s /home/tongshu/myDev/wesnothLearning/WesnothLearning/rules/1.18.8 data/rules/1.18.8
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PWD:/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension"
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

# Red source only; exit 1 is expected.
/home/tongshu/venv/bin/python -m unittest \
  tests.v5.test_ppo_scenario_coverage.PPOScenarioCoverageTests.test_complete_cycles_balance_maps_seats_and_focal_factions

# Green source.
/home/tongshu/venv/bin/python -m unittest \
  tests.v5.test_ppo_scenario_coverage tests.v5.test_batch_eligibility \
  tests.v5.test_scenario_identity tests.v5.test_training_turn_limit \
  tests.v5.test_ppo_resume_counters tests.test_schedule

# Measurement source; no games execute.
/home/tongshu/venv/bin/python \
  verification/ppo_scenario_coverage_20261106/measure_schedule.py \
  ../schedule_measurements.json --source 38b7a206ce9a7bad4b2c1e1179976505da26d86f
```

## Source and input identities

Ubuntu acceptance host `cpuServer`: Linux `7.0.0-38-generic`, Python 3.12.3. No local Windows tests were run. Each source was committed locally, shipped as a `git archive` tarball and extracted into a fresh directory; the host has no Git checkout.

| Stage | Server source directory | Archive SHA-256 |
| --- | --- | --- |
| Initial setup failure | `/home/tongshu/acceptance/issue223_20261106_f9b9182/red` | `a0d73c6a09a1211804a74f059645701d67c80f2919f9bbfae766844b04d35edf` |
| Valid red | `/home/tongshu/acceptance/issue223_20261106_red2/source` | `640c2112d520b8cbc257cd1516e50df4e88fe60d1f9260e5748616487f4285bc` |
| Green | `/home/tongshu/acceptance/issue223_20261106_4820641/source` | `1d72c5497eafd4644ccc8d30d732a482f53b92a21b61b35bb3ddfcb34c1e7158` |
| Measurement | `/home/tongshu/acceptance/issue223_20261106_38b7a20/source` | `d48cf1136d6a2dc64a294d4ba90689514d82ef348540e7d8e6b0b8b91cbb2ee5` |

Frozen rules SHA-256: `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`. Extension artifact SHA-256: `56dd77140411db987377d6de4ffbf562da4d0e5c76bc16d34780da67e60e5ae4`. Per-map hashes are in the measurement JSON. Existing rules, maps, schedules, run manifests and prior audit evidence were read only. [SHA256SUMS](SHA256SUMS) pins this report, harness and copied execution evidence; copied log/measurement hashes match the server originals.

## Acceptance boundary

Issue #223's scheduling assertions are satisfied by the bounded Ubuntu checks. Future formal comparison must measure whether the broader curriculum improves PPO strength; existing run outcomes remain historical evidence of the old sampler. The change does not alter optimization, reward coefficients, BC supervision, validation or selection. It makes every intended eligible distinct-faction matchup reachable while preserving the current training/evaluation separation.
