# Optional teacher noninferiority reporter

Ubuntu cpuServer, 2026-11-03. This validates the declared runner/reporter extension only. No real panel was prepared or run, and no teacher strategy changed.

## Behavior

Default superiority preparation and the original `comparison` result/status remain intact. `prepare --noninferiority --source-archive <tar>` selects seed 20261104, format seed offsets 0 / 100003 / 200006, 960 / 300 / 180 full rotation blocks, all 15 scenario families repeated 64 / 20 / 12 times, 4560 games, eight workers, six hours, 30 turns and the original teammate contexts. The schedule retains the existing interleaving order.

The optional report normalizes the original official-score CI by 3 / 1 / 3 and requires each lower endpoint strictly above -0.05. Complete declared games, blocks, at least 15 identified families and zero faults are prerequisites for all three formats; the combined team comparison stays primary and contexts remain descriptive. An original superiority `not_passed` from a small negative interval can pass NI. Decimal conversion of the reported endpoints keeps the exact -0.15 / 3 boundary at -0.05; this does not alter upstream bootstrap arithmetic.

NI stages a separate `astra_control_compatible` package using the accepted ambush helper. The original parent package remains untouched. Helper file hashes and old/new patch metadata, parent and derived package hashes, and the actual shipped source archive path/hash are frozen in the identity/plan records. The existing run artifact-hash validation covers the archive and helper. NI preparation rejects a missing archive before creating its output directory. Default mode does not apply the control transform.

## Verification

Source commit: `10c2e2b9956b06e363333eae5debdbcca1594d58`, based on `41fd33c` (merged control compatibility helper).

Source archive: `/home/tongshu/acceptance/teacher-ni-acceptance.tar`.

Archive SHA256: `d0277f278fcdeadff9f762920a4cd1a5a8b7641efff8f25769ce0dacf571b23e`.

Fresh extraction: `/home/tongshu/acceptance/teacher_ni_reporter_20261103`.

```sh
export PYTHONPATH="$PWD/.extension:$PWD:$PWD/vendor/arena" OMP_NUM_THREADS=1
/home/tongshu/venv/bin/python -m unittest tests.v5.test_teacher_strength_acceptance -v
```

Eight tests pass, exit 0, 1.954 seconds. Raw output: `unit.log`, `unit.exit`.

Coverage: CLI mode selection and report-time override rejection; missing source archive before output creation; the actual scheduler's full job/family/repetition/context/seed design and unchanged default counts; small negative superiority results; strict boundary/all-format requirements; incomplete, faulted or deficient designs; original comparison retained by report; NI-only compatibility invocation. Scheduler checks use a fixed map fixture and synthetic report outcomes; no native games are implied.

The acceptance environment reused the v6 extension at `/home/tongshu/acceptance/teacher_immunity_checked_20261103/.extension` and the read-only combat-filtered rules at `/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered`. The helper's unchanged six-test/byte-identity evidence is in `verification/teacher_control_compatibility_20261103/` and was not repeated.

Only `tests/acceptance_teacher_strength.py` (269 lines) and its focused test file (168 lines) changed. Production `learning/evaluate.py` and teacher scoring are unchanged. Real NI acceptance remains a separate, predeclared panel.