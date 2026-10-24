# Collection memory repair and Ubuntu pressure acceptance

Date: 2026-10-24. Original incident: [PPO OOM](../bc_oom_20261024/REPORT.md).
Validation directory: `/home/tongshu/myDev/wesnothLearning/validation_memory_repair_20261024_1321`.
The original formal experiment remains stopped. This task did not migrate its
manifest, change parameters, install an AI or resume training.

## Result

**The affected collector/write memory acceptance passes.** Eight independent
processes each replayed the complete existing 1,621-decision 2v2 rollout,
then wrote indexes concurrently and computed projected game metrics. Three
additional processes held the real duel/FF4/2v2 models, optimizer states and
bounded teacher replay pools; each also ran one forward/backward calculation
without an optimizer step or checkpoint write. All eleven processes exited.

| Measurement | Result |
| --- | ---: |
| Pressure duration | 149.29 seconds |
| Process-group peak PSS | 5.40 GiB |
| Process-group peak RSS | 5.72 GiB |
| Minimum host MemAvailable | 9.14 GiB |
| Old single replay worker peak RSS | 6.19 GiB |
| Largest repaired replay worker peak RSS | 413.38 MiB |
| Per-worker reduction in this replay | 93.47% |
| New kernel OOM during validation | 0 |
| Swap increase during successful pressure arm | 0; peak 184,076 KiB was pre-existing |
| Temporary full-record spool per worker | 83,600,923 bytes, closed/deleted on exit |

The old single-worker baseline and all eight repaired outputs have **identical
compressed complete-sequence payload SHA-256**:
`ffa95af6695d12cea9d3c219466160db9d6b68036a9b8366227b269ecb9c0437`.
Each contains all 1,621 decisions; there is no history/candidate truncation,
relabeling, reduction of concurrency or lowered acceptance gate.

These are real recorded trajectories replayed through collection storage,
indexing and metric projection, not eight newly simulated games. Collectors
do not instantiate eight live Lua engines or run all policy decisions. The
trainer memory exercise is one eight-record backward pass per format, not
the worst possible formal minibatch. The figures therefore prove this bounded
replay workload, not every future game, total training throughput or convergence.

## Final implementation

- `TrajectoryBuffer` immediately compresses exact per-decision float64 numeric
  arrays into private temporary records. Replay materializes one decision at
  a time; buffers close on both normal return and errors. DAgger uses the
  same storage. Existing persisted shard format/schema/labels are unchanged.
- Collection coverage/truncation counters are updated as decisions arrive.
  Metric projection keeps the actual legal entities, global features, turn
  order, raw rewards, reward configuration and committed memory views needed
  by current diagnostics; it omits candidate vectors and unused board arrays.
- `write_shard` yields augmented records directly to the index writer instead
  of building `raw_rows`. `IndexedSequenceStore.write` validates each record,
  keeps one compressor per sequence and never groups all raw decision objects
  or serializes a whole sequence at once. Existing JSON-array payloads,
  sequence identity, ordering/start checks, transactions and duplicate-content
  rejection remain supported.
- Online policy memory keeps float64 precision. No architecture, teacher,
  reward, BC/PPO gate, sampling target or worker count was tuned.

The separate BC read-share underfill is not changed by this repair. There is
also no new global RAM admission controller; observed collector pressure is
addressed at its storage/write boundary.

## Failure retained and corrected

The first attempt only compacted numeric leaves and streamed the JSON text,
but still retained full trajectories and index row groups. It passed small
functional tests, then the pressure arm hit the test's 1.5 GiB host reserve
and was **aborted as a failure**, without a kernel OOM. The abort snapshot
recorded 13,671,921 KiB PSS / 1,552,128 KiB MemAvailable. Its successful old
baseline was preserved and reused rather than rerun. Final disk spooling and
streamed record consumption address this demonstrated failure.

Initial Ubuntu setup omitted the teacher-package link: 14 checks failed with
FileNotFoundError; six unaffected checks passed. Provisioning only the new
validation directory's read-only link fixed the environment; only those 14
checks were retried. After the substantive spool changes, the directly affected
21 tests passed in 12.315 seconds. The two unchanged policy-memory tests retain
their earlier Ubuntu passes; unrelated passed suites were not rerun.

New weak-reference tests prove that collection and both write consumers
release prior decision arrays. In-memory restoration of the preceding writer
implementations makes the two consumer assertions fail. Regressions also cover
float64 precision, exact stored shard payloads except nondeterministic timing.ms,
sequence content guards, DAgger/bootstrap and turn-5/10 loss plus reward metrics.

## Identity, commands and preserved inputs

The source bundle started from the locally checked tree with the separate
repository-layout commit. Final repair commits are `ae81140` and `94ce64e`
on top of `78acd2d`; `source_v2_identity.json` records the actual uploaded
file hashes. The old baseline implementation is from `5ed7360` and is shipped
as a separate legacy module solely for the baseline replay. Local source ZIPs
are retained beside this report but are not required Git artifacts.

The publication tree excludes the unrelated layout commit. All eight modified
memory functions/classes were compared by AST against the tested source with
`verify_published_symbols.py`; only existing path-layout wiring outside those
symbols differs. Both trees resolve the same rule and teacher bytes.

```bash
# From the new isolated validation directory, threads fixed to 1:
.venv/bin/python -m unittest tests.v5.test_collection_memory \
  tests.v5.test_pipeline_contract.ShardSequenceTests \
  tests.v5.test_pipeline_contract.LiteJobTests -v
.venv/bin/python verification/bc_memory_repair_20261024_1321/stress_probe_v2.py \
  verification/bc_memory_repair_20261024_1321/pressure_run_v2
```

Do not rerun the one-time acceptance into existing paths: the first pressure
failure and successful baseline are in `pressure.ubuntu.txt`; the corrected
arm is in `pressure-spooled.ubuntu.txt` and `stress_result_v2.json`.

`unchanged.ubuntu.txt` confirms the original latest-checkpoint hashes remain
exactly as recorded before repair (duel v212, FF4 v88, 2v2 v50), no formal or
validation Python processes remain, the rule SHA is
`d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`,
and the manifest SHA is
`43cd83777cd213771cf7e574143a848020dcd975b073763c143fe66048de1bf3`.
Kernel journal inspection since 13:20 finds no new OOM. No formal training
is restarted by these scripts. Old frozen-source checks must still be honored
before any separately authorized migration/resume.
