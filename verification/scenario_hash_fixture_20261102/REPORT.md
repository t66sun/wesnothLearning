# Bind the legacy hash assertion to the committed LF fixture

Source `9fc402fffcb6b9e223d496e0cfeb4917d24b7d4f`, shipped by `git archive`
to `/home/tongshu/acceptance/scenario_hash_fixture_20261102` on Ubuntu cpuServer.

The existing scenario test expected a seed-bearing game-family hash calculated
from CRLF map bytes. The repository's `.gitattributes` requires LF, and the
committed source archive contains LF. Read-only calculations and the identical
baseline/fixed-reader failure are preserved in
`verification/bc_admission_20261102/REPORT.md` and
`verification/bc_admission_20261102/red/scenario_baseline.log`.

Only the test's expected literal changes, to
`95ef082e251ed7d45add147f907dcec4643aee736b1571ac687a75b593209371`.
The map, production identity algorithm, partition rule, frozen runs and their
recorded identities are untouched. This preserves the fixed-fixture assertion;
it is not replaced with an expected value calculated by the implementation.

```sh
PYTHONPATH=.:vendor/arena OMP_NUM_THREADS=1 /home/tongshu/venv/bin/python \
  -m unittest tests.v5.test_scenario_identity -v > checks.log 2>&1
```

**7 tests pass**, 1.044 seconds, exit 0. This includes seed-independent scenario
partitioning, seed-bearing game identities, physical-change sensitivity,
scheduled-corpus separation and shard/index partition checks. Restoring the old
literal reproduces the already recorded baseline failure on the same LF fixture.
The other 51 passing reader/learning/rowpack checks from the admission repair are
reused; they were not rerun for this test-only correction.

No games, collection, training, checkpoint writes, model export or Windows tests.
This correction does not close ordinary BC or teacher-strength acceptance.
