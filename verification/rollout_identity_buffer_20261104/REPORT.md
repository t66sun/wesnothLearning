# One-buffer rollout identity hashing

On 32 eligible decisions from the resumed team rollout, the full `rollout-content-v2` calculation fell from 293.66 ms to 86.20 ms. Both implementations produced the same canonical bytes for every target and history payload and the same final identity, `d5113ab4e73640b6f0e4831545539d1ff78f63a4cc7c3eb2b4f76d0dd0d6e4a0`. [Raw timings and digests](timing.json)

The existing JSON encoder now builds one canonical string for each target or unique prefix. SHA256 consumes its UTF-8 bytes in one call. The largest encoded payload observed in this sample was 176,127 bytes. Encoding scratch space scales with a single payload. The caller continues to retain the input rows and the shared-prefix digest cache.

## Sample and sensitivity

The sample was fixed before timing as the first 32 fault-free, eligible policy targets in the strict run’s resumed team batch, file `rollout-00002-team2v2-g0.jsonl.gz`. The probe restored real prefixes before selecting targets. The slice spans turn 1 decision 13 through turn 5 decision 121 and uses five distinct prefix payloads. Shard SHA256 was `370539f929b67f10e06538f121cac5b73fd2f62b7b881bd1e6b8dccd3ef84e23`. The two implementations ran in the same interpreter, in baseline/changed/changed/baseline order. Timing covered only the full identity call. [Reproduction program](probe.py)

| Representation | Targets | Unique prefixes | Canonical payload bytes | Full identity |
| --- | ---: | ---: | --- | --- |
| Real packed NumPy rows | 32 | 5 | Equal for all 37 payloads | Equal |
| The same rows as Python lists | 32 | 5 | Equal for all 37 payloads | Equal to the packed case |
| Legacy plain JSON fixture | 2 | 1 | Equal for all 3 payloads | Equal across implementations |

The measured saving was 6.48 ms per sampled target. Applied linearly to the original resumed team's 1,492 policy and 2,048 rehearsal targets, this gives an estimate of 22.95 s. Different game stages, supervised sources, candidate counts and shared histories can change that figure. The 172.7 s observed between the last rollout and the recorded commit also included shard reads, checkpointing and PPO itself. Actual full-batch and phase wall savings were not measured.

## Ubuntu verification

| Source | Commit | Git archive SHA256 |
| --- | --- | --- |
| Baseline assertions | `c743d09061a2d1c252e2bfe48ab99fb7b26dcc5c` | `5720ffc0d69cf552f78a02fa29a5e3506d7342c60fd07142193838a13a7256e6` |
| Implementation | `43f7dfd6bc3e3f9a5211b83eced99ba57ae3d6a9` | `d508a631fb16210130c9fe0e67bbf5c9dc85b3e02b5de94a14c5312a710a0561` |

The revisions were shipped with `git archive --format=tar.gz --output=<archive> HEAD -- learning lua engine_lite tests vendor benchmarks`. The implementation archive also included the probe path. Both local and remote archive digests matched. Fresh Ubuntu roots were `/home/tongshu/acceptance/rollout_hash_red_20261104` and `/home/tongshu/acceptance/rollout_hash_green_20261104`. The environment used Python 3.12.3, the filtered v6 rules from the ordinary BC run, and one thread each for OpenMP, OpenBLAS and MKL.

```sh
nice -n 19 /home/tongshu/venv/bin/python -m unittest \
  tests.v5.test_rollout_content_identity.RolloutContentIdentityTests.test_hashes_one_buffer_per_target_and_shared_prefix -v
```

The baseline exited 1 in 0.001 s. It fed the three content digests 11, 25 and 25 times while reproducing the fixture’s existing v2 digest. [Baseline output](baseline.txt)

```sh
nice -n 19 /home/tongshu/venv/bin/python -m unittest tests.v5.test_rollout_content_identity \
  tests.v5.test_checkpoint_ops.CheckpointContractTests.test_rollout_identity_covers_targets_and_provenance -v
nice -n 19 /home/tongshu/venv/bin/python -B verification/rollout_identity_buffer_20261104/probe.py
```

The fixed revision passed all four checks in 0.997 s, including the one-feed assertion, mutation rejection before updates, unchanged rereads and provenance. The retained-input probe exited 0. No collection or training was launched. [Ubuntu test output](ubuntu.txt)
