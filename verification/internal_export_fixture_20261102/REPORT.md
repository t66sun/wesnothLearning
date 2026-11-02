# Compact export size fixture

The compact model export fits under the SDK's 16 MiB package limit. The former test incorrectly assumed that its normal generated export exceeded that limit. Append 16 MiB to the allowed README file before asserting rejection. The SDK validator, internal resume acceptance and changed-weights rejection are unchanged.

Ubuntu baseline source `a44de041f3e955dc0e1c9c8f801eba7e1215e23c`: the affected assertion failed because the normal package was accepted (`baseline.log`).

Accepted source `37a6ebf86da99b6e83f458a8408dce21c1d96797`, archive SHA256 `e7d4b28a473094eefbe156095947737d430fbf5ae46bf8e20d75ef6b35edefc2`. Fresh extraction: `/home/tongshu/acceptance/internal_export_fixture_20261102`.

Command, using `/home/tongshu/venv/bin/python` with `PYTHONPATH=/home/tongshu/acceptance/team_bc_v2_20261102/.extension:.:vendor/arena` and `OMP_NUM_THREADS=1`:

```sh
python -m unittest tests.v5.test_training_failure_fixes.FailureBoundaryTests.test_internal_export_resume_keeps_weights_integrity_without_sdk_size_cap -v
```

Result: one test passed in 0.076 seconds (`ubuntu.log`). No collection or training was run. This verifies the test fixture and its existing export assertions; it adds no training acceptance.
