# Exact 37-candidate numerical boundary

Ubuntu, 2026-10-31. Source `0f7e141`, shipped by git archive to `/home/tongshu/acceptance/candidate_budget_20261031_v3` on cpuServer. Same Python and frozen-rule setup as `../candidate_budget_20261031/REPORT.md`.

The preceding report described its named 37-candidate test as covering that exact boundary. Review found that the existing pad helper only extends lists, so the original synthetic list could exceed 37. This report corrects that interpretation without editing the historical result. The test now explicitly truncates/pads each row to 37 and asserts the exact length before numerical verification; production code is byte-identical to the earlier tested version.

Command:

```sh
PYTHONPATH=.:vendor/arena /home/tongshu/venv/bin/python -m unittest tests.v5.test_learning_core.AuditExportTests.test_verify_numerics_37_candidates_two_turns -v
```

Result: one test passed, 1.564 seconds, Python/Lua error <= 1e-5. See `exact37.log`. Reuse the preceding 54 passing affected checks, two revert-sensitive failures and baseline-only planned_steps fixture failure with their stated limits. No additional training or native games. Native timing acceptance remains open.
