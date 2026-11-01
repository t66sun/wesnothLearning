# Training horizon configuration acceptance

Ubuntu acceptance on 2026-11-02. This phase repairs the declared-versus-actual
training horizon; it does not establish ordinary BC readiness or a complete loop.

## Cause and behavior

The bounded runner declared 30 turns but did not pass that limit to the run CLI.
Training map decoration imposed 60. The original all-format schedules and plan
remain unchanged; their hashes are recorded in
`../recruit_ranking_20261102/turn_limit_audit.json`.

The CLI/config now carries positive `training_max_turns` (default 60). Execution
binds the training horizon before scenario eligibility, hashing and freezing.
PPO composition retains it through map decoration. The bounded runner passes
its declared 30. Legacy manifests default to 60, frozen schedules are not
rewritten, and resume restores its frozen configuration. Evaluation stays at 30.
Review caught an opening probe sharing the training map partition; its explicit
five-turn limit is preserved using the existing opening marker.

## Source and execution

Each source was shipped by `git archive` to a new directory under
`/home/tongshu/acceptance/`, with suffix `_20261102`:

| Directory stem | Source | Result |
| --- | --- | --- |
| training_turn_red | 4a35cb6215e93d71788d0dfcafcb7fc2fd207d0d | five new cases fail: eight failures, two errors |
| training_turn_fixed | 4aa1801e18b4e13889f50acacecb91d2b1afeca1 | 49 cases: 46 pass, three fixture errors |
| training_turn_contract | 166b90c810fb13775a653364e7b97117b651b8b0 | all three corrected fixture cases pass |
| training_turn_opening | 6313b73e3bc068c3558e09d41aaac78dfe495512 | final complete affected suite: 50 pass in 7.492 seconds |

Commands, raw output and exit statuses are retained in the corresponding
`red/`, `fixed/`, `contract/` and `opening/` directories. Each command has a
180-second external ceiling. The final opening regression is also executed
against production source 166b90c through PYTHONPATH: it fails with `11 != 5`
(`opening/opening_red.log`, exit 1). The final suite exits 0 with no skips.

Two pre-existing `test_lite_default` cases were independently run on the red
source and both errored (`red/legacy_tests.log`, exit 1). Command:

```text
/home/tongshu/venv/bin/python -u -m unittest tests.v5.test_lite_default.LiteDefaultTests.test_lite_final_evaluation_has_only_astra_controls tests.v5.test_lite_default.LiteDefaultTests.test_resume_keeps_frozen_targets_workers_and_deadline -v
```

The fixtures omitted the current batch contract and wrote arbitrary bytes where
selection now reads a torch checkpoint. Fixtures now provide the batch contract
and a minimal valid checkpoint. The new resume fixture needed the same contract.
No production identity check was weakened.

Runtime: `/home/tongshu/venv/bin/python`; OMP_NUM_THREADS=1. Frozen rules are
symlinked from `/home/tongshu/myDev/wesnothLearning/WesnothLearning/rules`.
`rules.json` SHA256:
`d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`.
The accepted v2 extension comes from
`/home/tongshu/acceptance/retaliation_fixed_20261102/.extension/_engine_lite.so`,
SHA256 `ccb7c763cbce620e5d07736e6ae73df2c3891bdd9f281ab79ee10d63e2675365`.
Raw hashes are in `opening/identities.txt`.

## Scope and limits

Coverage includes CLI defaults/validation, all three formats and both engines,
teacher/PPO/DAgger schedules, scenario identities and PPO train eligibility,
evaluation and opening caps, frozen schedule reuse, manifest resume and the
manual runner's real CLI construction. Existing schedule/evaluation/worker/budget
contracts pass in the same final run. Collection is mocked; no games or training
were launched. Gates, model/loss and panel sizes are unchanged. No performance,
convergence, strength, ordinary BC or post-BC loop pass is claimed.
