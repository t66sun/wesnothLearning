# Preserve the planned BC family pool before stopping a full bucket

## Cause and change

Baseline diagnostic source `9a9626b6c83e9dbb00eee4d2488592309acb0212` reads
the three frozen final BC batches from
`/home/tongshu/acceptance/bc_root_20261101_readiness/runs/bc_readiness`.
Its return-frame trace shows that FFA stops after 22/33 families and team2v2
after 9/19 with **zero compressed or retained-budget rejection**. The bucket
was closed as soon as admitted families could fill its target rows, before
the initial pool declared by `_candidate_plan` had been considered.

Production source `4ab779bf81f63b1ab1fe2ec16eba90c14da12116` marks initial-pool
entries and permits early bucket completion only outside that pool. Each bucket
still considers at most `max(1, limit // (32 * bucket_count))` initial families,
or all its families if fewer exist. Additional families remain backfill only.
Compressed/retained budgets, bucket quotas, window selection, raw prefixes,
partitions, loss functions, candidates and ordinary gates are unchanged. No
production exception handler, assertion or fallback is added.

## Ubuntu verification

Each source was shipped as a committed `git archive` into a new directory under
`/home/tongshu/acceptance/`, with the existing provisioned rules symlinked at
`data/rules`. No frozen source, run, input or earlier evidence was overwritten.

Regression source `67ab3c6156762f5606335a87199ce47c20597b2a`:

```sh
PYTHONPATH=.:vendor/arena OMP_NUM_THREADS=1 /home/tongshu/venv/bin/python \
  -m unittest tests.v5.test_bc_fill.BoundedFillTests.test_long_family_cannot_short_circuit_the_initial_family_pool -v
```

The same-training-bucket fixture has three 64-row families and requests 64 rows.
The initial pool is two families. Baseline fails with `[64]` instead of `[32, 32]`;
fixed source passes. The first fixture accidentally spanned train/validation
buckets and passed without exposing the bug; its output remains in
`initial_fixture/`. The corrected fixture and its failing output are in `red/`.

Fixed-source affected checks:

```sh
PYTHONPATH=.:vendor/arena OMP_NUM_THREADS=1 /home/tongshu/venv/bin/python \
  -m unittest tests.v5.test_bc_fill tests.v5.test_learning_core \
  tests.v5.test_scenario_identity tests.test_rowpack -v
```

**57 pass, 1 pre-existing failure**, 16.663 seconds. All bounded-read checks,
including quotas, budget rejection, single decode, raw prefixes, repeatability,
and the new family-pool regression pass. The failure is
`test_seed_does_not_move_the_scenario_between_splits`'s fixed legacy game-family
hash. The exact same failure occurs on the unmodified reader baseline, recorded
in `red/scenario_baseline.log`. Its other assertions, including seed-independent
scenario partitioning, pass. No test or gate was weakened or skipped.

The fixture expects the hash of a CRLF `vendor/arena/maps/arena2.json`; committed
archives use LF. Read-only calculation on baseline confirms:

| Map bytes | Map SHA-256 | Seed-0 game family |
| --- | --- | --- |
| Actual / LF | `654da578da1aa8499f0c1c7f7735c59cfe13737382ebd946d3e021509e998cc4` | `95ef082e251ed7d45add147f907dcec4643aee736b1571ac687a75b593209371` |
| Same content as CRLF | `883c0e63933e5adb3dd242d6347ec2ee48b4bec434a928471cb6d8f131723922` | `ab8a9b778bc432db2c569078daa05b56736fd7f410c878c21384053dc9103dbe` |

This unrelated fixture issue is left visible and unchanged in this behavior PR.

## Same-input admission replay

Run on both baseline and fixed source, with identical checkpoint/shard/seed/limit
identities recorded in `baseline/admission.json` and `fixed/admission.json`:

```sh
PYTHONPATH=.:vendor/arena OMP_NUM_THREADS=1 timeout 300 \
  /home/tongshu/venv/bin/python -u tests/diagnose_bc_admission.py \
  --run /home/tongshu/acceptance/bc_root_20261101_readiness/runs/bc_readiness \
  --output admission.json > admission.log 2> admission.err
```

Both exit 0 with empty stderr. Each format still returns exactly 2048 rows.

| Format | Families before / after / available | Compressed bytes after | Charged retained estimate after | Budget rejections after |
| --- | --- | --- | --- | --- |
| duel | 38 / 38 / 38 | 39,255,622 | 425,737,140 | 0 |
| ffa4 | 22 / 30 / 33 | 68,744,818 | 800,090,088 | 3 |
| team2v2 | 9 / 14 / 19 | 69,190,455 | 800,237,448 | 5 |

The unchanged limits are 100,663,296 compressed bytes and 805,306,368 retained
estimated bytes. The remaining FFA/team families are now rejected by the actual
retained-budget check, not early row completion. Returned-row retained estimates
are 250,067,816 / 296,526,956 / 342,773,448 bytes; these are estimates, not measured
process RSS. The audit uses Python tracing and makes no throughput claim.

Broader exposure is not automatically better per-kind fit: FFA recruit/attack
rows change from 207/583 to 223/616; team from 113/335 to 101/294. The team corpus
still has no Undead training game. No fitting, games, collection, checkpoint
writes, PPO, final evaluation or export ran for this repair. Ordinary readiness
and teacher strength remain open; new fitting should follow the corpus/faction
audit rather than treating this reader acceptance as an imitation pass.
