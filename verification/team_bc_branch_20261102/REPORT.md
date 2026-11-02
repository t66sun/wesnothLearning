# Bounded compatible team BC branch

Ordinary BC still fails. The compatible branch reuses 40 parent teacher games, completes only the missing eight, and commits five additional batches / 272 updates. The unchanged 48-game corpus and candidate-coverage gates pass; recruit and attack imitation remain below their gates. No PPO, final evaluation or export ran.

## Frozen inputs and command

- Source commit: `bdecbbd4f9f18fc6c1b7a01bc6ff4bce5b3e5e30`.
- Source archive SHA256: `91fff00a0ae688b0392b4ddfaef730280ac1f82acc803ad4aaca233b86bfafce`.
- Fresh Ubuntu root: `/home/tongshu/acceptance/team_bc_branch_20261102`; run: `runs/team_bc_branch`.
- Parent: `/home/tongshu/acceptance/team_bc_v2_20261102/runs/team_bc_v2`, complete v5 / batch 5. Parent `latest.pt` SHA256 `1cdb7d00b19ec57cc7bb3a40ab504d79d655ef02c5ef3086aa5dbba2b3b6c878`, unchanged after the run.
- Isolated v2 extension SHA256: `ccb7c763cbce620e5d07736e6ae73df2c3891bdd9f281ab79ee10d63e2675365`; no shared environment installation.
- Lite v2 rules and teacher identities, exact CLI and source are in `observed/plan.json`. Model/shard hashes are in `input_model_hashes.json`.

Using `/home/tongshu/venv/bin/python`, the isolated extension before `.:vendor/arena` on `PYTHONPATH`, and OMP/MKL/OpenBLAS thread counts of one:

```sh
SOURCE_COMMIT=bdecbbd4f9f18fc6c1b7a01bc6ff4bce5b3e5e30 python -u verification/team_bc_branch_20261102/driver.py
python -u tests/diagnose_bc_parts.py --run runs/team_bc_branch --output verification/team_bc_branch_20261102/parts.json
```

The driver freezes team2v2, seed 20261101, eight workers, one trainer thread, 30 turns, 2048/1024 rows, original loss/sampler/gates, four epochs and minibatch 256. Optimizer is retained. Limits are five additional committed batches (absolute batch 10), 1200-second phase and 1320-second external ceiling. The task's continuing bounded-diagnostic authorization is recorded before launch.

## Observed boundary

The stage stops at the committed-batch cap after **631.25 seconds**, child exit `-15`, driver result `FAIL`. Five batches commit **272 new updates**, reaching version/batch 10 and 488 cumulative updates. No pending training or runner error remains. The version-10 periodic validation starts eight tasks before the one-second boundary poll stops the process group; none has a final result. `pending_validation = bc` is retained. This is a complete training checkpoint at an incomplete validation boundary, not normal BC completion.

The only new recorded results are **eight teacher games**, all complete, all turn-limit truncated, zero recorded gameplay faults. Terminal frame 31 follows the configured 30 completed rounds. The four later BC collection schedules are empty: the retained 48-game corpus was reused. Scheduler totals are 16 starts / eight finishes, including the eight unfinished validation tasks; no validation pass is claimed. The shutdown log records 11 semaphore objects reported by Python's resource tracker. A post-diagnosis source-directory process check finds no remaining processes. Full metadata, including schedules and job/scheduler logs, is preserved in `run_metadata.tar.gz`; `observed/` contains full stage/state/gate output.

## Unchanged gates

| Measure | Result |
| --- | --- |
| Teacher corpus | 48/48, pass |
| Candidate coverage | 11284/11978 = 94.21%, pass |
| Recruit / move / attack coverage | 88.03% / 94.17% / 92.59%, pass |
| Held-out recruit | 34/85 = 40.00%, fail |
| Held-out move | 426/667 = 63.87% |
| Held-out attack | 56/141 = 39.72%, fail |
| Overall imitation / CE | 60.95% / 1.34341; uniform CE 3.57875 |

The final exact 2048-row training read retains 37 families / 54 windows, including 126 recruits and 361 attacks. Read-only decomposition finishes in 28.92 seconds. Training recruit accuracy is 54/126 = 42.86%; attack is 162/361 = 44.88%. Training fitting remains incomplete, in addition to held-out ranking limitations.

Held-out recruit predictions choose the right action kind 83/85 times, but type only 48/85 and slot 60/85. For attacks, 56/141 predictions choose movement; even restricting the winner to attack candidates gives only 82/141 exact matches. Thus action-kind competition and within-kind ranking both remain. This diagnosis does not justify a particular loss, sampler or feature change.

## Limits and remaining work

The inherited-evidence implementation has separate 30-test Ubuntu acceptance in `verification/branch_teacher_evidence_20261102/REPORT.md`. This run additionally observes reuse of all 40 parent games and collection of exactly eight missing games. It is not a matched end-to-end performance comparison: the corpus, checkpoint and validation sample sets differ from earlier runs.

No production tuning is adopted. Existing fixed-batch original-loss/context probes remain at their original evidence paths; the rejected context inputs remain unadopted. Ordinary all-format BC, adapted teacher strength, native transfer, selected-model final evaluation and the complete bounded loop remain open. No forced gate, new seed, retry or automatic budget extension was used.
