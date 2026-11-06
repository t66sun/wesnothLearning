# Configuration and schedule test extraction

The existing `ConfigScheduleTests` class moved verbatim from
`tests/v5/test_pipeline_contract.py` into `tests/v5/test_pipeline_schedule.py`.
The original grandfathered file shrinks from 1710 to 1504 lines. No assertion,
fixture or production behavior changes. This isolates the configuration contracts
before the #222 validation-budget change.

Source: `0d96ffb9f5e2a79cbccc047e8c0203aed9695385`.
Archive SHA-256: `9e7541f8b945de89ec0a7a6b22dc92be8dd600c6010648085e53ae7a0ee9d67d`.
Ubuntu source directory: `/home/tongshu/acceptance/issue222_config_extract_20261106`.
The moved class body was compared byte for byte before committing.

Command: `/home/tongshu/venv/bin/python -m unittest tests.v5.test_pipeline_schedule`.
Result: 15 tests passed in 0.013 seconds; see [acceptance.log](acceptance.log).
No Windows tests, training or new game collection ran.
