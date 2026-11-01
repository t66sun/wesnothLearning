# Release unused BC targets during family admission

Ubuntu acceptance, 2026-11-02. No collection, optimizer steps or checkpoint writes.

## Cause and implementation

The reader retained every admitted supervised target until the final row allocation. Those unused rows consumed the retained-byte budget and excluded later families. The frozen-corpus diagnosis is in `verification/recruit_labels_20261102/REPORT.md`.

Source `b75d5f1aa55622ab9ddfe9d6c02290deee18a56c` allocates fair shares after each family admission and releases excess targets before the next decode. Equal allocation now uses max-min filling with stable remainder order, so an existing family's share cannot grow after adding a family; early deletion cannot remove rows needed later. Decoder container references are explicitly dropped, and weak references verify actual target-object release. Complete attached histories remain unchanged. Existing prefix estimates are unchanged and are not discounted for shortened targets.

The 96 MiB compressed, 768 MiB estimated retained and requested-row limits are unchanged. Provenance buckets still own their row quotas; initial family pools, additional-family backfill and one decode per family remain. Full reads are unchanged. Candidate generation, optimizer/loss and quality gates are untouched; no production assertion or exception handler was added. Bounded sample identities can change; historical pending batches must resume with their matching source, not this reader.

## Source shipment and regression evidence

Each committed source was shipped with `git archive --format=tar` and extracted into a fresh `/home/tongshu/acceptance/` directory. The existing training rules were symlinked at `data/rules`. Environment: `PYTHONPATH=.:vendor/arena OMP_NUM_THREADS=1`; interpreter `/home/tongshu/venv/bin/python`.

| Source | Directory | Result |
| --- | --- | --- |
| `162d5d5a38c2470c02498217da37e54db704ea94` | `bc_retention_red_20261102` | Three regressions fail on unchanged production reader |
| `b75d5f1aa55622ab9ddfe9d6c02290deee18a56c` | `bc_retention_fixed_20261102` | 64 pass; one new test's history expectation fails |
| `f3abd8ee2812cd6e3bf8740db805752be5962179` | `bc_retention_history_20261102` | Corrected three-test regression module passes |

Baseline command: `python -m unittest tests.v5.test_bc_retention -v`. Failures are `[2,2,0]` instead of balanced `[2,1,1]`, 256 live targets before the next decode despite a 96-row request, and only one family instead of three under the same measured byte budget. Raw output: `red/tests.log`, exit 1.

Affected command on production fix:

```sh
/home/tongshu/venv/bin/python -m unittest \
  tests.v5.test_bc_retention tests.v5.test_bc_fill \
  tests.v5.test_learning_core tests.v5.test_scenario_identity \
  tests.test_rowpack tests.v5.test_rollout_content_identity \
  tests.v5.test_bc_preflight_read -v
```

65 tests run in 50.713 s: 64 pass and the new history assertion fails. It incorrectly assumed every row's history has `turn-1` slots; later decisions within a turn legitimately include that turn's committed memory. Production did not change again. The test now compares each retained history's exact turn sequence with the original decoded history, while preserving its lifetime and single-decode assertions. On `f3abd8e`, the three-test module passes in 33.116 s (exit 0). The other 62 passing affected checks are reused, so all 65 affected cases have passing evidence. The failed intermediate output remains in `fixed/`, final regression output in `history/`.

The tracked source-size scan reports only the two unchanged grandfathered files (1050 and 1748 lines); no new file exceeds 1000 lines. `git diff --check` passes.

## Frozen-data comparison

Separate read-only processes ran sequentially on the baseline and production-fix archives, each under `timeout --signal=TERM --kill-after=10 180`. Both exit 0 with empty stderr (`red/frozen.*`, `fixed/frozen.*`). Inputs are the unchanged team run `/home/tongshu/acceptance/team_bc_readiness_20261102/runs/team_bc`, `team2v2/last_bc.pt`, SHA256 `ffb554ca152ac93e3602bd45c98841238ef7ee59640b5bf7fb4ba64ba8148a97`.

The probe loads `runner.teacher_shards` and config, then times exactly:

```python
rows = sequences.read_shards(
    state['teacher_shards'], partition='train', format_name='team2v2',
    limit=config['bc_records'], seed=config['seed'] + state['version'] - 1,
    stats=stats)
```

Here the limit is 2048 and seed is 20261103. It reports `time.monotonic()` elapsed time, process `resource.getrusage(resource.RUSAGE_SELF).ru_maxrss`, checkpoint SHA256, reader stats, family/faction counts and maximum attached history length. It performs no model inference, sampling update or corpus writes.

| Metric | Baseline | Fixed |
| --- | ---: | ---: |
| Returned rows | 2048 | 2048 |
| Families retained / available | 12 / 17 | 16 / 17 |
| Rows per retained family | 167–171 | 128 |
| Compressed bytes read | 67943528 | 98498946 |
| Final estimated retained bytes | 343658072 | 382374612 |
| Process peak RSS, KiB | 1339080 | 999280 |
| Read seconds | 11.801 | 16.619 |
| Recruit rows | 98 | 91 |
| Attack + move-attack rows | 339 | 324 |
| Maximum history slots | 60 | 60 |

The fixed read exposes more families and lowers process peak RSS by about 25.4%, while taking longer because it decodes more data. Final retained estimates increase with the extra families and prefixes; this is distinct from peak process memory. Both reads return all requested rows with no deficit and include all six factions. The full corpus exceeds the fixed compressed-byte limit, so all 17 families are not promised.

This single sequential comparison establishes the concrete admission/memory benefit, not a throughput benchmark or learning-quality improvement. Recruit and attack counts decrease at fixed row capacity. Ordinary BC imitation, teacher strength and the complete training loop remain unaccepted; there is no post-change fitting result.
