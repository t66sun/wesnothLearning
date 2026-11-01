# BC validation history reuse

Date: 2026-11-02 (Asia/Shanghai).

Scope: blocker 10, repeated historical scene encoding in the ordinary imitation gate. No corpus collection, game, experiment training, fitting probe, tuning or final evaluation was launched. Existing unit checks use small synthetic optimizer steps for gradient equivalence.

## Identity

- Failing regression source: `1564e04fa6a5576651ebc61db8fc3b9b45548492`, production code from `cb8e497`.
- Accepted production: `60450bc40ef1f3fdd3bfad10cde711f7006252ff`; source archive SHA-256 `fd6dec26a49cebd3c69b210272eb64e26cd49e44793996be4f2456a898935fe3`.
- Final source: `6f357ab55bca51c8e4a50b7fa9cd6e959b183b70`; archive SHA-256 `88624e89c51c937c3d758de2805907ce61993ab6b870249801b80fb258110083`. Only two mock signatures differ from the accepted production source; unchanged passing checks remain valid.
- Ubuntu `cpuServer`, Python 3.12.3, torch 2.9.1+cpu, Linux 7.0.0-38-generic x86_64; same host as the bounded-runner checks.
- Each commit was delivered by `git archive --format=tar.gz`, scp and extraction into fresh `/home/tongshu/myDev/wesnothLearning/bc_validation_{red,green,final}_20261102` directories. Existing main-tree `data/rules` is linked for feature fixtures. Frozen inputs remain unchanged.

## Commands and results

All commands run in the corresponding source directory with `/home/tongshu/venv/bin/python`, `WESNOTH_RULES_DIR=/home/tongshu/myDev/wesnothLearning/WesnothLearning/data/rules/1.18.8-training` and `OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1`. The shell preserves unittest's exit code.

| Directory | `python -m unittest ... -v` arguments | Observed result | Output |
| --- | --- | --- | --- |
| red | `tests.v5.test_bc_validation_cache` | exit 1; 2 expected failures; 1.044 s | [baseline.log](baseline.log) |
| green | `tests.v5.test_bc_validation_cache tests.v5.test_replay_optimization` | exit 0; 4 passed; 2.381 s | [core.log](core.log) |
| green | `tests.v5.test_window_memory_cost` and four AuditExportTests below | exit 1; 9 passed, 2 mock errors; 8.245 s | [dependents.log](dependents.log) |
| final | first two AuditExportTests below | exit 0; 2 passed; 0.007 s | [fixture_recheck.log](fixture_recheck.log) |

```text
tests.v5.test_learning_core.AuditExportTests.test_imitation_quality_gate
tests.v5.test_learning_core.AuditExportTests.test_imitation_quality_enforces_kind_precision_thresholds
tests.v5.test_learning_core.AuditExportTests.test_verify_numerics_37_candidates_two_turns
tests.v5.test_learning_core.AuditExportTests.test_verify_numerics_memory_overflow_and_128_entities
```

The first two mocks accepted only `batch(rows, device)` and rejected the existing optional `history_cache` parameter. They now accept that named argument; every gate assertion is unchanged. Only those failed cases were rerun. Fifteen affected unittest cases have passing evidence: four core, nine unchanged dependent cases and two corrected-fixture cases. The initial failure is retained.

## Observed effect

130 validation decisions in three chunks share 36 historical turns, including 32-slot rollover. Baseline encodes **238** scenes; the fix encodes **166**, a **30.25% reduction in encoded scene rows**. Each of the 36 historical rows is encoded once instead of once per chunk. This measures work, not wall-clock or full-run speedup.

Effective status, per-kind counts/accuracies/ranks, overall accuracy and uniform metrics match uncached inference; cross-entropy matches to six decimal places. A changed-weight second gate recomputes all history and matches an uncached reference. Existing output/gradient comparisons across two unit optimizer updates, detached-prefix reuse, incremental memory/side isolation and serialized Python/Lua parity (37 candidates; 128-entity memory overflow) pass.

## Limits

The gate owns a cache only while weights are unchanged. No-gradient context reuses suffixes as well as detached prefixes; gradient-enabled eight-turn replay is unchanged. The cache is discarded after each gate and is not stored on the model/checkpoint. Inputs, losses, sampling, thresholds and candidate limits are unchanged.

The cache retains encoded scenes/prefix states for one validation call, trading temporary storage for computation. Production RSS and wall-clock changes are unmeasured. Ordinary v2 BC readiness, recruit generalization, full-loop acceptance, native transfer and strength remain open. Windows ran static source checks only.
