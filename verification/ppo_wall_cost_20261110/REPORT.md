# Duel PPO costs across the game boundary

[#310](https://github.com/t66sun/wesnothLearning/issues/310) under [#309](https://github.com/t66sun/wesnothLearning/issues/309). Ubuntu cpuServer, 2026-11-10 Asia/Shanghai.

## Observed costs

The three original lambda 0.95 cells recorded 42,354.17 s through their last settled PPO history entries. Scheduler spans from first game submission to last worker reply total 11,835.55 s across 546 eight-game batches, or 27.94% of recorded wall. The rest includes preparation, PPO work, export, validation, saves, and scheduling outside these spans. It is not a single stage. [Original #306 run](../ppo_terminal_return_20261109/REPORT.md)

| Frozen batch in seed 202611081 | Rehearsal read, s | Rehearsal identity, s | Numeric and metadata validation in reads and update preparation, s | Row unpack in reads, s |
| --- | ---: | ---: | ---: | ---: |
| 38 | 9.04 | 5.61 | 8.87 | 3.49 |
| 129 | 15.68 | 5.34 | 9.84 | 6.28 |
| 220 | 15.83 | 5.32 | 9.90 | 6.28 |

Validation and unpack overlap the rehearsal-read column. Content identity is separate. All three preparation replays match the original read statistics, exclusion and work counts. The 72-batch preparation measurements remain the broader cohort. [Earlier preparation report](../ppo_rehearsal_cost_20261110/REPORT.md)

| Recorded game replay | Whole worker, s | Learner weight SHA-256, s | Host initialization, s | Shard and index settlement, s |
| --- | ---: | ---: | ---: | ---: |
| rollout-00000-duel-g0 | 2.31 | 0.0018 | 0.266 | 0.81 |
| rollout-00000-duel-g1 | 22.43 | 0.0018 | 0.260 | 7.22 |
| rollout-00364-duel-g0 | 16.90 | 0.0124 | 0.263 | 6.27 |

The rules and learner hashes protect input and cache identities. The existing rules catalog already reuses file parsing and SHA-256 within each process. On these replays, warm provenance comparisons cost about 0.04 ms per game and catalog loading 2.1–7.1 ms. Repeated feature schema lookups total 8–65 ms. Coordinator microprobes averaged 39 ms per fresh export, 3 ms per reopened export check, 25 ms to write both a late checkpoint payload and its state JSON, 20 ms to read the late job log, and 0.48 ms per scenario composition. These probes use existing data in isolation. Worker totals overlap in the real eight-worker batch.

A second fixed replay of the 276-decision long game compared two independent settlement changes. All variants match the recorded game result, coverage, training rows and decompressed SQLite payload content after excluding only the measured timing.ms field.

| Fixed replay | Whole worker, s | Private buffer append, s | Settlement, s | Compressed index payload bytes |
| --- | ---: | ---: | ---: | ---: |
| Baseline | 22.265 | 0.836 | 7.129 | 5,321,335 |
| Uncompressed private spool | 21.787 | 0.545 | 6.883 | 5,321,328 |
| Faster SQLite compression | 21.896 | 0.811 | 6.788 | 8,656,880 |

## Implementation cuts

1. Run the existing numeric finiteness checks on packed arrays in vector form. Keep width, shape, metadata and rejection semantics, including legacy rows.
2. Encode numeric vectors directly in the PPO content identity, keeping integrity checks and a reader for existing pending identities. Retain bit-level coverage of accepted numeric values, target fields and real history. Rehearsal identity currently spends 5.3–5.6 s per sampled batch before accounting for the current rollout.
3. Remove compression from the private per-game spool and keep the persisted gzip shard and SQLite sequence formats. The measured long-game saving is 0.48 s in isolation. Keep streaming row lifetime and account for the temporary disk cost.

The three cuts target distinct work. Keep per-game package and rule identity checks. The faster SQLite compression adds about 63% to the stored index payload for 0.37 s of isolated wall saving, so leave that format unchanged. These measurements prioritize the implementations. The authorized paired run decides the combined 10% whole-run result.

## Reproduction

The probes ran on Ubuntu from fresh Git archive extracts, with the #306 rules, frozen maps, extension and one Torch thread. They did not start an optimizer or collect new scenarios. The preparation benchmark used the qualified BC model and the original recorded samples. The first boundary attempt needed the original frozen map tree mounted. The initial replay comparison also identified the dynamic timing.ms field as the only shard difference. The recorded evidence uses the original map tree and a comparison which omits exactly that field.

| Run | Source commit | Git archive SHA-256 | Output SHA-256 |
| --- | --- | --- | --- |
| Full boundary profile | f49e49df282c9cff7dfaac39b6a8ccb600fb3c5c | 7512423c4482fed8a1e7ec5f856d84c66cd285cd9465d2e2d1dc818b4efeac31 | 9f75d4f3952b9c75136b7adb5ea5447904e1f28a51e1940ff6e1dcb01d0b02bf |
| Fixed worker cuts | ed508db42daa943f05cfb5b800a9c2443e69c8bd | bac0dde20cb378f0560ee8a96ae7677a6f7e9fb8a8edb56e19bacb1c7d772f28 | ba39292bf2f6dd30534cc29faa77eda13b2c3bc6e2504894af50a88aae80a39f |

Use [measure_wall.py](measure_wall.py) with the original #306 run root and a fresh output path. For the second probe, append worker-cuts. The Ubuntu roots are /home/tongshu/acceptance/ppo310_wall_20261110_z071G5 and /home/tongshu/acceptance/ppo310_wall_20261110_Q4MKwx. [Full profile](result.json) · [Worker cuts](worker-cuts.json)
