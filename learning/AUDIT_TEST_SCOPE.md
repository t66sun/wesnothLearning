# Follow-up test scope for P0 audit, sequence data and engine benchmarks

> Language: English | [中文](AUDIT_TEST_SCOPE_zh.md)

This round implemented code only: no tests were written or run, and no training, game, benchmark or 64-decision fit was executed.
The following is a historical per-item list; current status and validation scope are maintained in [docs/TEST.md](../docs/TEST.md).

## Audit

- Walk the complete fixed validation set block by block; cover both covered teacher decisions and uncovered ones with choice=-1,
  never inferring overall coverage from shards of successful labels. State the denominator and gaps explicitly when teacher original intent is missing.
- Compare on exactly identical inputs including global/opponents/spatial/turn/raw history and every candidate
  feature/actor/target/local/geometry; do not round floats and do not compare only schema-3 features.
- Identical vectors with different target/actor/endpoint must be distinguishable; exactly identical inputs keep exact labels,
  never auto-creating equivalence classes; record non-first aliases and conflicting exact labels for the same full input.
- Break down by map, faction, action type, turn phase, format, source and engine; a missing stratum does not pass.
- Overall coverage ≥90% and recruit/move/attack each ≥80%; missing data must be inconclusive.
- Check interrupted moves against the teacher's legal original intent as coverage and list the actual endpoint separately; actual-only evidence states its limits.
- The 64-decision small set must include recruit/move/attack per format and keep full raw prefixes; a future `fit_small_set` run only
  trains a model copy and verifies the original model/optimizer/RNG are unchanged, exact ≥90%.
  Report explicit equivalent_choices only with independent rule/teacher evidence and never treat an alias as equivalent.

## Sequences

- One SQLite compressed block holds one ordered game/side/source/engine; train/validation partition stably
  by family, and native/lite variants sharing a family never cross the partition.
- Reuse one store instance's decoding LRU per batch; validation iteration walks the full index and never a fixed small panel.
- Raw read/write persists no embedding or old-weight hidden state; each turn's first successfully committed decision's
  post-execution memory_write enters memory, the turn's other decisions include that first one,
  and failed commits and unexecuted teacher queries are guaranteed by committed=False not to advance memory.
- A real commit with choice<0 is kept as history but never enters the supervision loss.
- Continuous full replay matches the 8-own-turn window replay; the window keeps the true full prefix and recomputes it
  from scratch with current weights; no old embedding is reused after an update; only the last 8 history turns keep gradients.
- Partially declared or prefix-missing mid-sequence samples must be rejected; a suffix with an explicit prefix may be restored.
- Memory never streams across format, source, engine, game_id or side; out-of-order turns are rejected.
- The compatible gzip reader filters uncovered decisions and limits supervision counts only after full replay; it never randomly picks single
  steps and loses the memory before them. training_windows groups once at the start of a training batch.

## Engine benchmarks

- Freeze real hashes of the V4 three models, native 1.18.8, Astra and lite rules; manifest rebuilds are stable.
- Identical host, quota, threads, frozen models/opponents, rules, maps, factions and cache state;
  single-worker CPU is primary acceptance. Regular/dense, cold/hot and all three formats each ≥30 full rotation blocks.
- Equal-work scripts fix state, actions, turns and injectable combat results; a hash or action-count mismatch
  cannot pass. End-to-end actual action counts and terminal reasons are reported separately so early wins cannot pass as rule speedup.
- Subprocess-tree total CPU core-seconds cover short-lived processes and coordination cost; peak RSS/PSS, disk bytes,
  startup time and all seven component timings are each really measured; unmeasurable PSS must be missing, never 0.
- p50/p95 with per-full-rotation-block bootstrap intervals, plus reasons for missing seats/faults/invalid rows;
  missing resources, artifacts, blocks, duplicate rows or config mismatch cannot pass.
- Wall and CPU ratios are each ≥5 and the PSS target is reported separately; 4/8 worker throughput never replaces primary acceptance.
- Pure lite and the audit-inclusive pipeline are measured separately; without a pipeline result it stays inconclusive.

## Reporting format

Every result states command, commit, host, format, engine/rules/RNG/candidate/observation/architecture/policy/
reward versions, artifact hashes, data-family partition, teammate context, start/end time, status
passed/failed/inconclusive/skipped, and raw data and report paths.
The audit adds overall and per-stratum denominators/coverage/alias/non-first-alias/missing-target-attribute counts and the 64-set exact rate;
sequences add full/window replay error and pre/post-update checks with current weights; performance adds per-group complete block counts,
p50/p95, wall/CPU/PSS ratios and intervals, the fault-exclusion list and the separate pipeline result.
Blank and unexecuted items are marked "not executed"; planned thresholds, best historical numbers or hypothetical ratios must never be filled into measured columns.
