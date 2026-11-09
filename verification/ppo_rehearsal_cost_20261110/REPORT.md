# Frozen eight-game Duel PPO rehearsal preparation

[#310](https://github.com/t66sun/wesnothLearning/issues/310) under [#309](https://github.com/t66sun/wesnothLearning/issues/309), measured on cpuServer on 2026-11-10 Asia/Shanghai.

The measured preparation stages used **1,935.49 s** for 72 recorded batches whose original PPO intervals totaled **5,495.64 s**. Within the nine sampled blocks, eliminating every observed repeat family decode and all rehearsal content-identity time would account for **12.35%** of the recorded intervals. A 256 MiB LRU model plus the same zero-cost identity assumption accounts for **7.17%**. The replay does not support an implementation cut that meets the 20% whole-run target. Stop at #310 and close the gated implementation and short-run acceptance without executing them.

## Workload and checks

The three #306 lambda 0.95 arms supplied three chronological eight-batch blocks per seed. The probe uses the same rules, 2,048-row rehearsal quota, control identity and CPU thread settings. It selects the original eight rollout shards from each schedule. The original lists of inherited teacher and DAgger shards keep their order. Current-run DAgger and policy shards enter the rehearsal pool through the greatest rollout index in that batch's schedule. Each batch uses its sampled policy version plus the seed for the rehearsal draw. [#306 archived run](../ppo_terminal_return_20261109/REPORT.md)

| Seed | Early | Middle | Late |
| --- | ---: | ---: | ---: |
| 202611081 | 38–45 | 125–132 | 213–220 |
| 202611082 | 38–45 | 125–132 | 212–219 |
| 202611083 | 38–45 | 124–131 | 211–218 |

All 72 replays match the corresponding original rehearsal read statistics, rehearsal exclusion counts and identities, fresh rollout target counts and window counts. The fixed qualified BC model retains the same parameter digest. The probe runs production reads, content identities, validation and window setup with the timer used by #270. It measures family decoding, raw-prefix attachment and window construction together. The probe's extra family-size accounting time is subtracted from the rehearsal-read time. No optimization step or game ran. [Prior fixed-input measurement](../ppo_batch_cost_20261107/REPORT.md)

## Cost and decision

| 24 batches per period | Recorded wall, s | Measured prep, s | Rehearsal read, s | Of read, family decode, s | Rehearsal identity, s | All repeat decode + all identity | Bounded LRU + all identity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Early | 1,764.29 | 633.60 | 346.94 | 338.42 | 129.27 | 18.09% | 7.52% |
| Middle | 1,884.64 | 661.76 | 373.99 | 360.14 | 129.74 | 10.23% | 6.96% |
| Late | 1,846.71 | 640.12 | 361.47 | 345.16 | 129.42 | 9.03% | 7.04% |
| Pooled | 5,495.64 | 1,935.49 | 1,082.39 | 1,043.72 | 388.42 | 12.35% | 7.17% |

Recorded wall is the sum of successive settled PPO history timestamps for the selected batches, starting at phase time zero for each first batch. It covers work between those history entries and supplies the denominator for screening. The preparation timings are a separate, fixed-input replay. The three process-start batches took 20.41–22.65 s in preparation. The later block-entry timings are 25.79–29.51 s. Across processes, the preparation probe's maximum RSS was 896.68 MiB.

A repeated decode is the same ordered family shard list already decoded within the same eight-batch block. Early, middle and late blocks repeated 1,032/1,858, 455/2,452 and 286/2,518 family decodes. Simulated 256 MiB LRU retention of decoded windows and raw prefixes would hit 19, 8 and 6 times, saving 5.54 s of family preparation in the pooled replay before cache costs. Its byte charges use the existing row and prefix estimates. Repeated selected target keys and prefix slots account for 31,531/147,329 and 13,215/58,697 observations within blocks. Even so, both percentage estimates grant the full 388.42 s of rehearsal identity time as a saving, including first-seen material.

These estimates screen one reuse cut. They assume zero reuse overhead and reset the simulated retention at each block boundary. They do not measure an implemented cache or predict every possible representation or admission change. The absolute cost of all rehearsal reads and identities accounts for 26.76% of the historical intervals, so reaching 20% would require saving about three quarters of that cost. Measured reuse under the plan's constraints does not justify that claim.

## Reproduction

The input is the original [#306 run](../ppo_terminal_return_20261109/REPORT.md) at /home/tongshu/acceptance/ppo306_20261108_Miwoyq/source/runs/ppo306. The measurements ran from fresh Git archive extraction on Linux 7.0.0-38-generic x86_64, Python 3.12.3 and PyTorch 2.9.1+cpu, with one Torch intra-op/inter-op thread. The code uses a new output path and reads existing shards and checkpoints in place.

| Artifact | Source or SHA-256 |
| --- | --- |
| Probe Git archive source | f3580eea57b2dfcdb7103a55aa32d3bc7978bc31 |
| Probe Git archive SHA-256 | 118e3c4df96fc8112f7c6cb1b438d2f60e6c44a194209979536a42c80d130b95 |
| Summary Git archive source | a3f7e55e9a8a6d05c7eef4c12cee3019ade71d99 |
| Summary Git archive SHA-256 | 086f643d7870c88db8381f26fe78f236733dd37750becddda415989c8561b70f |
| [Raw measurements](raw-measurements.tar.gz) | c21ca8e925324250a919e844dbd4840f742ba2a9aa8ea7c420d1b4cb4d7c6459 |
| [Computed summary](summary.json) | 5b1ec2c69366bc320e355d406795d7d93971e06c008bdfa75606dbc2d8550951 |

From a fresh extraction of the probe archive, set the #306 rules and extension identities and write into a fresh directory.

~~~sh
root=/home/tongshu/acceptance/ppo306_20261108_Miwoyq/source/runs/ppo306
out=$(mktemp -d)
python=/home/tongshu/venv/bin/python
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export PYTHONPATH="$PWD:/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension"
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
for seed in 202611081 202611082 202611083; do
    "$python" -u verification/ppo_rehearsal_cost_20261110/measure_rehearsal.py "$root" "$seed" "$out/$seed.jsonl"
done
~~~

The summary command takes the directory of the three original JSONL files and a new output filename. The original Ubuntu evidence root is /home/tongshu/acceptance/ppo310_20261110_HXRsSX.
