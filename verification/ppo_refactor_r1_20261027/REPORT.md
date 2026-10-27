# R1 scenario-partition acceptance — 2026-10-27

Scope: PPO rebuild R1, issue #52, parent #48. Implementation `be0a1ca4744d235f406b2a5ba9775b6f24d03a24`, based on `e7f1beefac48b619e4a5b147b54db8c8b66fd41f`.

## Result

New schedules carry `scenario_family` and `split_rule=scenario-v2`. Scenario identity binds board/starts, factions/teams, engine/combat/rules and effective scenario settings, excluding seed, output path and job identity. The old seed-bearing `game_family` bytes remain unchanged. Both collectors propagate the new fields. Shard writing, validation and the sequence index partition on the declared rule. Legacy rows remain readable as `family-seed-v1`; an update mixing rules is rejected.

Scenario binding refreshes after actual engine/rules overrides and before schedule freezing. The 300/600/400 teacher schedules are inspected without playing games: equivalent physical scenarios never cross partitions, and holdout maps never enter these schedules. Explicit catalog identity, physical changes, legacy compatibility and opposite-legacy-partition shard/index round trips are covered.

## Local reference

- The new seed assertion first failed on missing `scenario_family`. Subsequent shard/index and mixed-rule assertions failed on zero returned rows and no raised exception. They pass after implementation.
- Local pytest command could not run: `No module named pytest`. The same unittest-based test files run through the installed standard-library runner; no dependency installation or assertion change.
- `OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 .venv/Scripts/python.exe -m unittest tests.v5.test_scenario_identity tests.v5.test_rollout_content_identity tests.test_schedule -q`: **17 PASS**, 10.904 s.
- Additional affected reader check `... -m unittest tests.v5.test_bc_fill -q`: initially **9 PASS / 1 ERROR**. Its fixture stamped an Astra sample `lite-0.1`, rejected by the current teacher contract. Running the failing case with the baseline `e7f1bee:learning/data.py` reproduced the same error. Fixture now uses supported native/lite metadata; original 5/2 bucket allocation and all other assertions stay unchanged. Final **10 PASS**, 14.171 s. No runtime validator was loosened.

## Ubuntu isolated acceptance

Directory: `/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r1_20261027_be0a1ca`. Existing frozen data is referenced through a symlink and only read. Existing `/home/tongshu/venv` dependencies are reused. Linux `7.0.0-38-generic`, Python 3.12.3, torch 2.9.1+cpu; extension path and rules hash in [environment.log](ubuntu/environment.log). Rust/Lua rule implementation is unchanged, so no rebuild.

Source-only tar: 2,027,520 bytes, SHA-256 `8cb398ae7d62f0835b38cfce8a4971e0916b349e86cdef6ee5585d9e937e12ca`. Inputs exclude data, runs, delivery, previous verification and virtual environments; one baseline maps module is included solely for the deliberate revert check.

Commands from repository root:

```powershell
scp tmp/refactor_r1_20261027/source.tar cpuServer:/tmp/wesnoth-r1-be0a1ca.tar
scp verification/ppo_refactor_r1_20261027/run_ubuntu.sh cpuServer:/tmp/wesnoth-r1-be0a1ca.sh
ssh cpuServer "bash /tmp/wesnoth-r1-be0a1ca.sh 8cb398ae7d62f0835b38cfce8a4971e0916b349e86cdef6ee5585d9e937e12ca"
```

Exact environment, test and restore commands are in [run_ubuntu.sh](run_ubuntu.sh). Neither environment has pytest, so both run the same unittest assertions.

| Check | Actual result | Evidence |
| --- | --- | --- |
| New scenario suite + unchanged rollout-content identity + schedule + affected BC reader | **27 PASS**, exit 0, 8.186 s | [targeted.log](ubuntu/targeted.log) |
| Restore baseline `learning/maps.py`, run named seed assertion | **expected failure**, exit 1, missing scenario identity | [reverted.log](ubuntu/reverted.log) |
| Restore implementation, rerun named assertion | **PASS**, exit 0 | [restored.log](ubuntu/restored.log) |
| Relevant source hashes before/after intentional revert | identical | [before](ubuntu/source_before.sha256), [after](ubuntu/source_after.sha256), [status](ubuntu/status.log) |

Rules SHA-256 remains `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`. Historical shards, catalogs, run manifests/checkpoints and evidence are untouched. Legacy run-family fixture is pinned to its pre-change hash. Existing rollout-content assertions prove changed legal inputs still reject, under their bounded fixture scope.

## Limits and next phase

R1 is accepted for identity, partition propagation and rule isolation only. R2 must remove late eligibility drops; R3–R10 remain unimplemented. No formal run, corpus re-encoding, new collection, native game, optimizer training step, strength panel or full-suite rerun occurred. Synthetic Lua decision fixtures and schedule construction do not prove training convergence or native playing strength. Existing N1, FFA4 numerical and SDK package failures remain open with unchanged gates.
