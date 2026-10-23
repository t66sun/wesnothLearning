# V5 engine benchmark contract

> Language: English | [中文](README_zh.md)

This directory holds the fixed benchmark contract and the real-resource Linux runner. Performance results are authoritative only in the actual output directory.
`learning.benchmark.build_manifest()` generates a deterministic native/lite paired manifest.
Each format separately covers cold start/resident hot run, equal work/end-to-end, and regular/dense scenarios,
with 30 full seat-rotation blocks per group; single game worker, CPU inference and single thread are the primary acceptance.
4/8 worker throughput is a later independent result and cannot replace the single-worker gate.

## Freezing and execution

`freeze_artifacts(paths)` takes a name→real-file-path mapping and computes SHA256 for each.
Primary acceptance requires six artifacts: `native_executable`, `lite_rules`, `astra`, `v4_duel`, `v4_ffa4`,
`v4_team2v2`. Pass the return value to `build_manifest(artifacts)` and write it to
manifest.json; a missing artifact keeps the report `inconclusive`. Historical V4 artifacts are read only.

The maps, rules, seeds, faction rotation, seats and turn caps in the manifest must be consumed by the actual runner.
The equal-work runner uses fixed positions/scripts/hit sequences and records their hashes together with actual
action counts and turns as `work_signature`, `actions`, `turns`.
When different full-game RNG ends a game earlier, the end-to-end saving is not counted as rule-core speedup.

`run_benchmarks({'native': native_runner, 'lite': lite_runner}, manifest, directory)`
is the explicit entry. Each runner receives one workload and returns the following real raw fields;
the entry alternates both engines, appends to raw.jsonl and finally writes report.json.
With only backend adapters and no real measurer, calling this entry to fake resource numbers is forbidden.

## raw.jsonl fields

The entry appends `engine`, `manifest_id` and `workload_id` to each line; the runner provides:

- `host_id`, `cpu_quota`, `workers=1`, `threads=1`, `inference="cpu"`.
- `cache_aligned=true`: real proof both sides' cache state matches the cold/hot contract.
- `wall_seconds`, `cpu_core_seconds`, `startup_seconds`, in seconds.
- `cpu_scope="process_tree_including_coordinator"`: cumulative CPU covers game, host,
  inference and coordinator processes; CPU of short-lived children must be captured around exit too.
- `peak_rss_bytes`, `peak_pss_bytes`, `disk_bytes`, in bytes.
  PSS is the real measurement after shared-memory apportionment; write null when the platform cannot measure it and never substitute RSS.
- `actions`, `turns`, `terminal_reason`, `faults`, `work_signature`.
- `components_seconds` holds real timings for seven items: `rules`, `visibility_pathfinding`, `candidates`,
  `teacher`, `inference`, `serialization`, `logging`.
  Items that cannot be split are null and the report lists the diagnostic gap separately; measured resource ratios are never erased for that reason.

`benchmark_report(raw_samples, manifest)` starts no engine and groups by format/cache/workload/
density, reporting each resource's p50/p95/total for both sides plus wall/CPU ratios over full rotation blocks
with per-block bootstrap 95% intervals. Missing seats, faults, differing host/quota, unequal work and missing resources
are excluded with the reason retained. Native/lite wall and CPU must each be at least 5×; the PSS 5× target is reported separately.

`pipeline_report(native_equivalent, measured_pipeline)` separately compares measured total wall/CPU including native audit
and coordination cost; it requires identical `work_signature`.
When only pure lite passes, the audit-inclusive pipeline stays `inconclusive` and no theoretical formula may replace measurement.

## Ubuntu real runner

Depends on the existing Python environment, release `_engine_lite`, native Wesnoth 1.18.8 and a readable
`/proc/*/smaps_rollup`; adds no third-party dependency. Run a minimal paired instance in the project root first:

```bash
python -m learning.benchmark_runner --executable "$WESNOTH_EXE" \
  --output verification/perf-smoke --formats duel --caches cold \
  --modes equal_work --densities regular --blocks 1 --seats 1 \
  --script-turns 1 --max-decisions 4
```

For full samples remove the format/cache/mode/density/seat limits and pass `--blocks 30`.
Each output directory can be written only once; `raw.jsonl` lands per sample and faults are never turned into a successful 0.
`manifest.json` binds native, rules and Astra hashes. This runner compares pure Astra and therefore needs no unrelated V4 student weights; student inference performance must be measured separately in a real small loop.

- Each engine starts an independent single worker with BLAS/OpenMP pinned to one thread and CPU inference. Native child processes
  follow the accounting. cold includes import, host creation and shutdown; hot first completes one observe/legal/decision in the same resident host before timing. Neither clears OS page cache, and the report records that explicitly.
- `equal_work` runs a fixed observe/legal/decision/end_turn script on the same GameSpec,
  with no combat and an empty hit sequence; the signature includes the full initial state and the actual actions/turns. Regular positions are
  arena2/arena4; dense positions add 8 Elvish Fighters near each side's spawn.
  This result is limited to that script and must not be passed off as combat performance.
- `end_to_end` calls the shared Lua real Astra decision and executes it. It records actual action counts, turns and
  terminal reason; `decision_limit` means an artificial budget truncation and cannot support a full-game conclusion.
- Linux `getrusage` collects exited subprocesses, resident children's hot-window CPU is completed from `/proc/stat`
  counters, and the coordinator's own CPU is counted too. The real process tree and coordinator RSS/PSS are sampled every 20 ms,
  so peaks are sampled peaks. `disk_bytes` means retained benchmark file bytes only and explicitly excludes deleted temp files.
- `operation_seconds` gives measured time at observe/legal/decision/execute/serialization boundaries;
  components of the shared decision that are not yet split stay null. Pure Astra student inference
  is 0 because this run has no student model forward pass.
- `observed.json` shows measured ratios over full rotation blocks with available bootstrap intervals; numbers are still viewable below 30 blocks.
  `acceptance.json` keeps the criteria of at least 30 complete blocks, identical host/quota/work, and 5× each for wall and CPU. The two serve different purposes and a minimal instance is never a passed acceptance.
