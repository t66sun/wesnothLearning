# Frozen recruit labels and bounded-reader cost

Ubuntu read-only diagnosis, 2026-11-02. No games, optimizer updates or checkpoint changes.

## Identities and execution

Frozen run: `/home/tongshu/acceptance/team_bc_readiness_20261102/runs/team_bc`.
Checkpoint: `team2v2/last_bc.pt`, SHA256 `ffb554ca152ac93e3602bd45c98841238ef7ee59640b5bf7fb4ba64ba8148a97`.
The authoritative checkpoint hash is also recorded in `full/labels.json`.
Teacher `four.lua`: SHA256 `a4f8f66d67170212704c89d3e3077ed9325ff7607536c85e362088b73cee55e0`.

Each source was shipped with `git archive` to a fresh directory under `/home/tongshu/acceptance/`, using the existing training-rule link and `/home/tongshu/venv/bin/python`, `PYTHONPATH=.:vendor/arena OMP_NUM_THREADS=1`.

| Source | Directory | Script | Evidence |
| --- | --- | --- | --- |
| `42b812d4c7297cb4edcd00c00f04a25346103af8` | `recruit_label_audit_20261102` | `tests/diagnose_recruit_labels.py` | `initial/` |
| `d1c56453a55b251cbf4f6cb0aac6fe92238db0c8` | `recruit_label_full_20261102` | `tests/diagnose_recruit_labels.py` | `full/` |
| `aca6250d1134307d073e90b1363d60fb976a88d3` | `bc_prefix_cost_20261102` | `tests/diagnose_bc_prefix_cost.py` | `prefix/` |

Commands: `timeout --signal=TERM --kill-after=10 180 /home/tongshu/venv/bin/python -u SCRIPT --run RUN --output labels.json` (prefix script uses `prefix.json`). Each exits 0 with empty stderr; JSON, logs and exit status are retained. These are completed diagnostics, not imitation acceptance tests.

## Labels and available exposure

Exact limited reads use 2048 training rows (seed 20261103) and 1024 validation rows (seed 20261101). The initial placement reconstruction omitted the teacher's three-hex leader radius and falsely flagged one selected training label; the corrected diagnostic preserves that restriction. Original output is retained separately.

| Pool | Recruit rows | Optimal type | Optimal slot | Complete own-unit context | Matching enemy count |
| --- | ---: | ---: | ---: | ---: | ---: |
| Selected train | 98 | 98 | 98 | 98 | 94 |
| Validation | 59 | 59 | 59 | 59 | 59 |
| Full train | 348 | 348 | 347 | 348 | 309 |

The full training stream contains 17 families, 8936 raw rows, and 8258 supervised rows: 348 recruit, 903 end turn, 5782 move, 1118 move-attack and 107 attack. Thirty validation placements and three types have tied optima; exact teacher agreement is stricter than membership in those sets. Age-zero remembered enemies need not be currently visible, so the diagnostic does not establish exact enemy context throughout the corpus. The one full-corpus placement mismatch (family `e5e79707...`, turn 53, decision 2917) also has an enemy-count mismatch; its cause is not established here.

Validation recruitment contexts represented in training rise from 7/59 in the selected batch to 25/59 in the full corpus. A context here means own nonleader type counts, the two teacher enemy-boost flags, and available eligible recruit types. It excludes positions, terrain and history and is not full policy-input equality. This supports investigating data retention; it does not prove that exposing more rows will pass imitation.

## Retained-memory attribution

Across all 17 training families, compressed bytes total 106067144 (already above the unchanged 96 MiB cap). All target rows cost an estimated 1031458084 bytes. Current prefix charges total 139623564; 906 unique history slots retain 95270516 bytes of packed backing arrays plus 17462400 estimated metadata bytes, totaling 112732916. The difference is 26890648 bytes. Estimates use the reader's metadata constant and are not RSS measurements.

Unused supervised targets dominate the avoidable charge: the reader retains all admitted family windows before assigning its final 2048 rows. Prefix overcount is much smaller. Packed history views retain their entire owning row buffer, so merely counting history features would undercharge them.

Next repair: fairly allocate and release unused target rows during admission, preserve full history and fixed byte/row limits, and ensure earlier shares cannot grow after adding a family. The existing ceil-first allocation can give `[2,2,0]` for three equal families and four rows, then `[1,1,1,1]` after adding a fourth; it cannot safely support early discard without a fair rounding correction. Verify actual object release, one decode per family, backfill, provenance quotas and deterministic replay. Ordinary BC, teacher strength and the complete loop remain open.
