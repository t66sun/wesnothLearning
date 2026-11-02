# Incomplete NI evidence reports inconclusive

Ubuntu cpuServer, 2026-11-03. Review correction to the optional NI reporter: aggregate status is inconclusive if any required format is inconclusive, passed only if all three pass, and not_passed otherwise. The no-pass gate is unchanged; incomplete evidence is distinguished from a statistical failure.

Source: `caedafda5440a417e3a07fc5cca28fa0b16ac9f4`.

Archive: `/home/tongshu/acceptance/teacher-ni-inconclusive.tar`, SHA256 `db668ed6c8cbd7fd9ea0d7143800980bb1f2237ff0ff430154107fb0a1d80707`.

Fresh Ubuntu extraction: `/home/tongshu/acceptance/teacher_ni_inconclusive_20261103`. Same accepted extension/rules environment as `verification/teacher_ni_reporter_20261103/`.

```sh
export PYTHONPATH="$PWD/.extension:$PWD:$PWD/vendor/arena" OMP_NUM_THREADS=1
/home/tongshu/venv/bin/python -m unittest \
  tests.v5.test_teacher_strength_acceptance.TeacherStrengthAcceptanceTests.test_small_negative_superiority_result_can_pass_ni \
  tests.v5.test_teacher_strength_acceptance.TeacherStrengthAcceptanceTests.test_exact_margin_never_passes_and_all_formats_are_required \
  tests.v5.test_teacher_strength_acceptance.TeacherStrengthAcceptanceTests.test_missing_faulted_or_incomplete_design_cannot_pass -v
```

Three affected classifier tests pass, exit 0. Raw output: `unit.log`, `unit.exit`. The original eight-test run is retained read-only in `verification/teacher_ni_reporter_20261103/`; the other five checks are unchanged and reused. No panel preparation, native games or teacher changes.