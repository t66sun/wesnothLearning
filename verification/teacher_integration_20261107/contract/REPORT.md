# Frozen teacher-set contract acceptance

The contract-only phase passes 24 Ubuntu checks at source `d730b5b5ad31a05c05b9dba2a9d39a9a7a177e7e`. No sampling, games or training loop was started. Mixed runtime startup remains rejected and the default remains Astra until the later integration acceptance.

The frozen set pins the delivered selected package `6b461de4e99303321b0119a7b88babd575c2d786500b28da4cb45d3c2bdabdb3` for duel/team and maintained Astra for FFA. Supervision, opponent, evaluation and reward-reference roles have independent descriptors. Parent/child execution identities must match before supervision is inherited; only weights-only initialization may change them. Reproducible Astra packaging ignores source extraction timestamps.

## Commands and outcomes

| Source | Command | Result |
| --- | --- | --- |
| `18622e5cef34984d36de6eca812deb2f6344e9b0` | `python -m unittest tests.test_teacher_set tests.v5.test_lite_default tests.v5.test_training_turn_limit -v` | 21 tests, four errors |
| `5dd440d274a5e57610372eac08d553342af338ca` (unchanged parent) | `python -m unittest tests.v5.test_lite_default tests.v5.test_training_turn_limit -v` | Same four errors in 14 tests |
| `d730b5b5ad31a05c05b9dba2a9d39a9a7a177e7e` | `python -m unittest tests.test_teacher_set tests.v5.test_lite_default tests.v5.test_training_turn_limit -v` | 24 tests passed in 1.634 seconds |

The paired failures identify two missing default-rule-directory errors and two older test fixtures missing the finite-task identity/configuration. The final archive links the existing frozen `1.18.8-combat-filtered` inventory from `/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered`; no inventory was edited or recaptured. The two fixtures now provide current task metadata, preserving their assertions. The expected `FAIL BC execution or bounded batch/time limit` stdout belongs to a bounded-loop failure-path unit test which passes; it is not a sampling result.

Exact source trees, commands, outputs and exit codes are copied byte-for-byte in the three adjacent check directories. Both independent review findings (mtime-sensitive packaging assertion and same-name teacher source changes on branches) were fixed and re-reviewed with no remaining findings.

## Limits

This phase verifies selection, identity, hashing, branch restrictions and existing defaults only. It does not accept Native/Lite teacher execution, data integration, strength, throughput or default activation. Those remain pending in TEST.md.
