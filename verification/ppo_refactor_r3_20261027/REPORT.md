# R3 explicit KL work accounting — 2026-10-27

Issue #56, parent #48. Implementation `3983cd0b4d5520628a7f6079b08c1754b542e9fe`, based on `f0646246887d805adc88897082a3a4e6e34a02e0`.

## Approved contract

The original R3 guarantee was not implementable under fixed weights, frozen behavior probabilities and the unchanged pre-step KL gate. The [five-row probe](../ppo_refactor_r3_probe_20261027/REPORT.md) reproduces identical rejection on two resumes. The user explicitly approved this correction: terminate KL-stopped batches and record their remaining work as `stopped_by_kl`; retain pending only for deadline/interruption.

Results now report planned, committed, deferred and KL-stopped optimizer steps, plus window-visit counts across all requested epochs. Interrupted results carry `scope=deferred` in their cursor and remain pending without global settlement. Terminal results settle cumulative planned/committed/KL-stopped counts once, including zero-update rejection. Partial commitment increases version once; zero-update KL does not. No loss, gradient, probability, KL threshold, reward or scale changes.

## Local reference

The new stopped-work assertion first failed with `KeyError: stopped_by_kl_steps`. After implementation, 13 checks passed (14.088 s): three initial R3 tests, two resume-counter tests and eight existing PPO-plan tests. Adding the partial-KL real-checkpoint case and new cumulative-counter assertions required three focused checks, all passed (6.357 s). The new R3 file now has four tests. Previously passed checks were reused without another full local rerun.

## Ubuntu isolated acceptance

Directory `/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r3_20261027_3983cd0`; existing dependencies and read-only frozen data reused. [Environment](ubuntu/environment.log): Python 3.12.3, torch 2.9.1+cpu, rule SHA-256 `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`. No Rust/Lua changes or rebuild.

Source-only archive: 2,048,000 bytes, SHA-256 `c0f30a93e315189c93db8027f84f6532a562f45206412c6290760a6da0d87a8d`. Includes a baseline PPO module solely for deliberate revert; excludes data, runs and dependencies.

```powershell
scp tmp/refactor_r3_20261027/source.tar cpuServer:/tmp/wesnoth-r3-3983cd0.tar
scp verification/ppo_refactor_r3_20261027/run_ubuntu.sh cpuServer:/tmp/wesnoth-r3-3983cd0.sh
ssh cpuServer "bash /tmp/wesnoth-r3-3983cd0.sh c0f30a93e315189c93db8027f84f6532a562f45206412c6290760a6da0d87a8d"
```

[run_ubuntu.sh](run_ubuntu.sh) runs `python -m unittest tests.v5.test_kl_defer tests.v5.test_ppo_resume_counters tests.v5.test_ppo_plan -v`. The standard-library runner preserves the planned assertions; pytest is unavailable in the existing environments.

| Check | Observed | Evidence |
| --- | --- | --- |
| Revised R3, resume and original PPO plan | 14 PASS, 7.802 s | [targeted](ubuntu/targeted.log) |
| Restore baseline PPO; run stopped-work assertion | Expected failure: missing `stopped_by_kl_steps` | [reverted](ubuntu/reverted.log) |
| Restore fixed PPO; repeat assertion | PASS | [restored](ubuntu/restored.log) |
| Source hashes before/after revert | Identical | [before](ubuntu/source_before.sha256), [after](ubuntu/source_after.sha256), [status](ubuntu/status.log) |

## Limits

Synthetic optimizer steps and recorded-shard responses establish update/checkpoint accounting only. No real game, collection, corpus changes, full suite, promotion/final panel or formal training occurred. No convergence or strength acceptance is claimed. R1/R2 evidence remains reused. R4–R10 are not accepted here; native N1, teacher tactical coverage and existing numerical/package failures remain open. Historical manifests, checkpoints and evidence are unchanged. New cumulative work fields start at zero when absent; they do not reconstruct past work.
