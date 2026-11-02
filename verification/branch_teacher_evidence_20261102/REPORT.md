# Inherited teacher evidence

A branch inherited its checkpoint's teacher shards but counted only its own job log for corpus and coverage gates. This made a compatible child recollect games already available for training. Read eligible ancestor job records only when their canonical shard paths belong to the inherited checkpoint, deduplicating paths across nested lineage. Parent collection after that checkpoint, other formats and ineligible games remain excluded. Row provenance validation and all gate thresholds are unchanged.

## Ubuntu checks

Baseline source `a44de041f3e955dc0e1c9c8f801eba7e1215e23c`: three of four new regressions fail (`red.log`).

Final source `25732536f74a4910e8f80f3eb7412c007527689a`, archive SHA256 `5087e0e42fd949e1a19f3c3cad896ee1f79589b5bbe5b397fae19bef363e6c36`, extracted fresh at `/home/tongshu/acceptance/branch_teacher_final_20261102`:

```sh
PYTHONPATH=/home/tongshu/acceptance/team_bc_v2_20261102/.extension:.:vendor/arena OMP_NUM_THREADS=1 /home/tongshu/venv/bin/python -m unittest tests.v5.test_branch_teacher_evidence tests.v5.test_checkpoint_ops tests.v5.test_bc_preflight_read tests.v5.test_training_failure_fixes -v
```

All 30 tests pass in 1.281 seconds (`ubuntu.log`). The isolated v2 extension SHA256 is `ccb7c763cbce620e5d07736e6ae73df2c3891bdd9f281ab79ee10d63e2675365`. The independent compact-export fixture repair is accepted in `verification/internal_export_fixture_20261102/REPORT.md`.

A read-only `branch.adopt` check with the actual team v5 parent retains 40 shards and now counts 40 eligible results, without creating the child directory or changing the parent checkpoint (`real_parent_check.json`). Parent `latest.pt` SHA256 is `1cdb7d00b19ec57cc7bb3a40ab504d79d655ef02c5ef3086aa5dbba2b3b6c878`; its complete `last_bc.pt` is separately identified in the original run report.

These checks accept compatible branch corpus/coverage accounting. They do not prove a new collection/training run, ordinary BC readiness, playing strength or the full loop. No collection or training was run for these checks.
