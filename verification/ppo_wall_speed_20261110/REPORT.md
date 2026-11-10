# Duel PPO preparation and settlement checks

[#311](https://github.com/t66sun/wesnothLearning/issues/311), Ubuntu cpuServer, 2026-11-10 Asia/Shanghai. This records fixed-input checks for the three production changes. [Cost attribution](../ppo_wall_cost_20261110/REPORT.md)

| Change | Matched fixed input | Before | After |
| --- | --- | ---: | ---: |
| Vectorized packed-row validation | #306 seed 202611081 batch 38, full preparation | 22.59 s | 15.80 s |
| Vector content identity | Same batch's current rollout and rehearsal identity work | 8.63 s | 4.84 s |
| Uncompressed private spool | Isolated worker replay, rollout-00000-duel-g1 | 22.265 s | 21.787 s |

The array comparison matches the original read statistics, rollout and rehearsal v2 digests and schedule identity. The content-identity comparison runs both algorithms on the same decoded rows, reversing their order between current and rehearsal. New pending PPO batches save a v3 identity. Old pending identities still use the original v2 encoding. Both encodings reject changed protected inputs in their tested paths. The private spool comparison is the fixed worker cut from the linked cost report. The final production stack replayed the same long game in 21.35 s and matched the game result, semantic gzip rows and decompressed indexed sequence payload, excluding only timing.ms. Its temporary policy and DAgger spools occupied 56,750,443 and 56,534,119 bytes. The stored shard and SQLite formats retain their original encodings.

All three targeted revert checks failed as designed on independent overlays. The unchanged v2 digest fixture, new v3 value and position checks, 4/8-game training fixtures, exact resume, finite-task and collector checks passed. The first stack archive passed 53 tests and omitted a dependency of the 8-game module. A fresh archive including that dependency passed the five 8-game and phase tests. A broader array-suite invocation failed the existing SQLite raw-payload fixture because the current writer adds split_rule and the fixture expects it absent. The same assertion fails on the unchanged baseline. The targeted stack run exercised the affected collection and spool cases separately. [Raw Ubuntu logs and measurements](acceptance.tar.gz)

| Artifact | Identity |
| --- | --- |
| Array validation commit | 27a96b12c143547ee89bf2ae448916f74baef27d |
| Vector identity commit | 56cf5e60056298b8f3f214017d3a0ad786632059 |
| Production stack commit | 62ac6b62376fe5bcec81e0c7a8483d1bc09b02dd |
| Array check Git archive SHA-256 | 761a309fa2d1c2c5d450eb6742db3ee89953e04361b41a4f81d6bc28ddba8a3f |
| Stack check Git archive SHA-256 | cc1b796349828fa395939d7d43b7ecb32257517da3e74fd7eaee8646c4b4d695 |
| Final 8-game and replay archive SHA-256 | 3766b3067c28260a4c2915948257fb17f3745cbd21d0c060c4a04d7962bf705e |
| Evidence archive SHA-256 | a222b95462d82d48b81688d289c8a90225d8c513ee6d31ca79b1365b15b253b4 |

The tests and probes ran from fresh Git archive extractions. Original files remain under /home/tongshu/acceptance/ppo311_arrays_20261110_zaNCfV, /home/tongshu/acceptance/ppo311_combined_20261110_4ZBnPc and /home/tongshu/acceptance/ppo311_final_20261110_dCvEdW. The fixed-input results motivate the paired #312 run. End-to-end speed and resource usage await that run.
