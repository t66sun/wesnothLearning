# One complete read for each new PPO rollout

Issue: [#240](https://github.com/t66sun/wesnothLearning/issues/240), part of [#221](https://github.com/t66sun/wesnothLearning/issues/221). Date: 2026-11-06.

## Result

`FormatExperiment.learn` reads a new PPO rollout completely once, uses that result for the nonempty check, and passes the same rows to `finish_train(prepared_ppo=...)`. The former bounded preliminary read is removed. The full rollout is never limited by `bc_records`; the separate rehearsal reader still uses its existing limit, seed and quotas.

`prepared_ppo` is a keyword-only, batch-local handoff. Pending updates call `finish_train()` without it, reread the frozen shards, and check both original content identities before updating. Hashing, validation, raw-history reconstruction, optimizer logic, window plans and the 0.02 KL gate are unchanged. BC keeps its existing `prepared_bc` path.

An empty rollout still increments the batch and skips training. A nonempty rollout containing mixed or exclusively non-training rows now reaches the no-drop rejection. The old partition-filtered preliminary read silently treated the exclusively non-training case as empty; rejecting that input is the necessary consequence of checking the complete batch. Valid inputs retain identical targets and update behavior.

## Source and input identities

| Item | Identity |
| --- | --- |
| Baseline | `09d038cf6fec05ebd46cf11d1e8afbe79135098d` |
| Tested implementation, tests and diagnostic | `f836c5aa827c6c5cc785c822d5f96838cba7182b` |
| Source archive SHA-256 | `308be2566e0266dfc3e9678a6dd9ec47483376b3858acc43baeff7452430f0d7` |
| Ubuntu source | `/home/tongshu/acceptance/rollout_read_once_20261106_f836c5a/source` |
| Frozen run | `/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/runs/formal_30h_scratch` |
| Frozen run manifest SHA-256 | `6de9d81858c71c41de505db2c445bae5229fa8587db7a6d3d66d2ebc3eab3c88` |
| Rules | `1.18.8-combat-filtered`, `rules.json` SHA-256 `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17` |
| Runtime | Ubuntu; Python 3.12.3; PyTorch 2.9.1+cpu; one intra-op/inter-op thread for the timing probe; OMP/MKL/OpenBLAS = 1 |
| Measurement window | 2026-11-06 04:35:53–04:47:04 UTC |

Each source shipment used `git archive` and a fresh Ubuntu directory; the host needs no git. Subsequent changes are documentation and evidence only. [Source checks](source_checks.txt) record unchanged implementation/test/probe contents and line counts. The two existing oversized test files remain unchanged.

The selected policies, schedules and rollout-shard SHA-256 values are in [timings.json](timings.json), together with the historical rehearsal path-list identity and complete read statistics. Existing run data and prior dated reports were only read. [Host before](host_before.txt) and [host after](host_after.txt) record the coordinated measurement window; this is not an OS-isolated benchmark.

## Regression evidence

All **31 Ubuntu tests passed**: [26 PPO/runner/plan/resume/rehearsal tests](tests.txt), then [5 direct BC-preflight and content-identity tests](caller_tests.txt). No Windows tests ran.

The seven new runner tests cover:

- A real gzip/rowpack reader and the real `learn`/`finish_train`/PPO path: exactly one unbounded rollout read, with the rehearsal read counted separately. Eleven supervised targets exceed `bc_records=2`; the turn-12 target remains, with all eleven preceding raw turn slots, including an uncovered first-turn decision. Planned targets remain eleven and repeated targets remain zero.
- Empty-batch skipping, mixed train/validation rejection, and exclusively validation rejection before identity commitment or training.
- The new path versus the former sequence of discarded bounded read plus a full reread: equal ordered targets, GAE advantages/returns, both content identities, every metrics field, exact pre-clipping gradients, final model digest, Python RNG and Torch RNG.
- Identical KL-stop metrics and cursor with zero committed updates, plus real-checkpoint interruption/resume matching uninterrupted loss, model digest, counters, final cursor and Python RNG. Resume performs a new full read.
- Rejection of changed target values and changed uncovered raw-prefix observations when resuming a pending update.

The behavior assertion was also run in a separate extracted copy with only `learning/experiment.py` restored from the baseline archive. It failed at the intended assertion, **`2 != 1 : fresh rollout must be read exactly once`**. See [reverted test output](reverted_test.txt). The passing source was not modified by this check.

The tests use bounded synthetic fixtures and transient optimizer updates. They do not collect new games or start a training run. The frozen cost diagnostic below constructs no optimizer and performs no forward/backward pass, updates or checkpoint saves.

## Paired frozen-input cost

[compare.py](compare.py) uses the same six frozen batches as the [original efficiency investigation](../ppo_efficiency_20261106/REPORT.md): first, middle and last completed duel/team batches. Each mode is measured twice, with `legacy, single_read` in the first repetition and the reverse order in the second. Both modes use production readers, eligibility, content identities and `prepare`; the legacy mode additionally performs and discards the former bounded read. The order of full rollout and rehearsal reads follows each runner path.

Every measurement asserts exact historical rehearsal read statistics, rollout target/window counts and unchanged model parameters. All modes/repetitions also compare ordered targets, per-target raw-prefix lengths, both content identities and window counts exactly. All assertions passed. [Raw timing log](timing.log) records all 24 measurements.

The table contains arithmetic means of two measurements per mode, in seconds. Total preparation includes the rollout and rehearsal reads, no-drop eligibility, both content identities and `prepare` validation. It excludes checkpoint/save/export work, scheduling, optimizer updates and training epochs.

| Format/batch | Targets | Removed preliminary read, wall | Legacy total, wall | Single-read total, wall | Legacy total, CPU | Single-read total, CPU |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Duel 38 | 447 | 0.78 | 14.11 | 13.13 | 13.99 | 13.12 |
| Duel 489 | 536 | 0.96 | 28.41 | 25.71 | 27.43 | 25.70 |
| Duel 939 | 724 | 1.27 | 29.58 | 26.54 | 28.58 | 26.53 |
| Team 53 | 1,490 | 3.04 | 37.84 | 34.82 | 37.82 | 34.82 |
| Team 168 | 756 | 1.38 | 29.24 | 27.63 | 29.16 | 27.62 |
| Team 283 | 1,353 | 2.73 | 35.30 | 32.24 | 35.15 | 32.23 |

The eliminated read took 0.78–3.04 seconds on these inputs. The measured whole-preparation differences were 0.99–3.06 seconds. Those differences include reader-order, cache and timing variation and are not all attributable to the removed call. OS caches were not evicted and metadata caches warm across calls. Reads include decoding, validation, allocations and raw-history attachment; they are not pure disk time. Two repetitions do not establish a general performance distribution.

Accepted here: one complete rollout read at the new-batch runner boundary, preserved valid-input semantics and resume/tamper detection, and the measured preparation costs for this fixed panel. Full trainer speedup, memory scaling, convergence, playing strength and native-engine acceptance were not measured. No pending implementation acceptance item remains for this behavior in `docs/TEST.md`.

## Reproduction

Extract an archive of the tested source into a new directory on Ubuntu. Provision the existing extension and frozen rules/maps; do not modify the frozen run. From the extracted source:

```bash
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PWD:/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension"
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
python=/home/tongshu/venv/bin/python
"$python" -m unittest \
  tests.v5.test_ppo_rollout_read_once tests.v5.test_ppo_plan \
  tests.v5.test_ppo_resume_counters tests.v5.test_ppo_phase_boundary \
  tests.v5.test_rehearsal_source -v
"$python" -m unittest tests.v5.test_bc_preflight_read tests.v5.test_rollout_content_identity -v
"$python" verification/rollout_read_once_20261106/compare.py \
  /home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/runs/formal_30h_scratch \
  /tmp/rollout-read-once-new-measurement.json --repetitions 2
```

The timing output must be a new file; coordinate the CPU window before reproduction. To reproduce the reverted assertion, extract the tested archive into another directory, overlay only `learning/experiment.py` from a baseline archive, and run `tests.v5.test_ppo_rollout_read_once.RolloutReadOnceTests.test_new_batch_reads_once_without_truncating_tail_or_raw_prefix`. Expected exit is 1 with the read-count assertion above. [SHA256SUMS](SHA256SUMS) identifies this report and its artifacts.
