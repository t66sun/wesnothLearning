# Refactor acceptance — P1–P5b, P7a–P7b

**Date:** 2026-10-25
**Source identity:** acceptance panel `master` at `e1181ea` (the merged refactor plus the learner-parity test fix; PRs #19–#24); the reduced L1 run uses `34cbe94`, which adds the empty-read fix #25 and the interrupted-job retry fixes #26–#29
**Environment:** Ubuntu CPU server, Python 3.12.3 / PyTorch 2.9.1+cpu, Rust 1.99.1; isolated tree `/home/tongshu/myDev/wesnothLearning/acceptance_refactor_20261025/master`
**Rules:** `data/rules/1.18.8-training` — hash `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`
**Engine identity:** `lite-0.2`, `deterministic-expected_damage_v1`, `expected_damage_v1`
**Scope:** P1 learner split, P2 bounded BC filling, P3 PPO traversal/recovery, P4 logical-batch stopping, P5a atomic checkpoints/branching, P5b final selection, P7a deterministic lite combat, P7b adapted Astra teacher. P6 external inference stays unimplemented. No formal training, no strength claim, and no gate was lowered.

## Method

The tree was produced from `git archive origin/master` into a fresh directory, with `data/rules`, `humanData_curated` and `.runtime` symlinked to the existing read-only provisions. The extension was built in that tree:

```bash
export PATH=/home/tongshu/.cargo/bin:$PATH
export VIRTUAL_ENV=/home/tongshu/venv PYO3_PYTHON=/home/tongshu/venv/bin/python
cd engine_lite && /home/tongshu/venv/bin/maturin develop --release
```

All commands ran with `OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1`, dummy SDL video/audio, the 1.18.8 `wesnoth` binary on `WESNOTH_EXE`, and `PYTHONPATH` set to the isolated tree.

## Results

| Check | Command (module list abbreviated) | Result | Log |
| --- | --- | --- | --- |
| Learner, loader, engine, PPO, checkpoint, selection, teacher, memory, scheduler | `python -m unittest tests.v5.test_engine_contract … tests.test_experiment tests.test_worker_limit` | 273 tests, OK | `acceptance_master.log` |
| Stage chain, forced phase, terminal truth, reward controller | `python -m unittest tests.v5.test_training_failure_fixes` | 17 tests, OK | `acceptance_stage.log` |
| Deterministic Rust resolver/status/forecast | `cargo test --release` | 13 tests, OK | `acceptance_rust.log` |
| Imported extension identity | `python -c 'import _engine_lite …'` | `lite-0.2 deterministic-expected_damage_v1 expected_damage_v1` | `engine_identity.txt` |
| Empty bounded read (#25, post-panel) | `python -m unittest tests.v5.test_bc_fill` | 9 tests, OK; empty index returns `rows=0`, full deficit, `insufficient_data` | local; L1 exercised the path |
| Interrupted-job retry (#26–#29, post-panel) | `python -m unittest tests.test_experiment tests.v5.test_bc_fill` | 15 tests, OK; retries discard the shard, its indexed rows, and tolerate shardless or truncated jobs | local; L1 exercised the path |

The 273-test run includes: `test_engine_contract`, `test_rule_abilities_completion`, `test_rule_weapons_completion`, `test_candidate_provenance`, `test_real_rules_smoke`, `test_coverage_audit_regressions`, `test_pipeline_contract`, `test_training_revision`, `test_learning_core`, `test_learner_extraction`, `test_ppo_plan`, `test_checkpoint_ops`, `test_selection`, `test_bc_fill`, `test_collection_memory`, `test_astra_adaptation`, `test_four_player_teacher`, `test_differential_runner`, `test_experiment`, `test_worker_limit`.

## Item coverage

| Item | Evidence | Scope |
| --- | --- | --- |
| C1 public inputs/routing/memory | `test_policy_actor_input_excludes_teacher_and_reward_fields`, query/bootstrap and sequence-write tests, `test_collection_memory` | Public-field and memory slices pass; no additional cross-boundary composite scene was added. |
| C2 learner extraction | `test_learner_extraction` (4 tests), `test_learning_core` parity | Seeded BC/PPO losses and parameter digests match the pre-split baseline within four decimals; BC `4.353553771972656`, PPO `0.9339113235473633`. |
| C3 bounded BC filling | `test_bc_fill` (9 tests after #25), `test_training_revision` | Metadata-first admission, one decode per family, fair first allocation plus same-bucket backfill, explicit deficit/stop reason. The admission plan may admit more families than the first fair quota when the requested row count needs them; budget-excluded families are not decoded. |
| C4 PPO traversal | `test_ppo_plan` (8 tests) | One target per window per epoch, shuffled once, no replacement, disjoint supervised intervals, saved-boundary resume. |
| C5 logical-batch KL | `test_ppo_plan` | Window-equal KL aggregation, pre-step rejection and gradient clearing, distinct committed/inspected counts, deterministic exits. |
| C6 checkpoints/branching | `test_checkpoint_ops` (4 tests), `test_branch` coverage in `test_experiment` | Atomic replace, latest resume, explicit branch lineage, identity rejection before update. |
| C7 stage chain/controller/terminal | `test_training_failure_fixes` (17 tests) | BC gate, forced phase, pending method, metric exception, terminal versus truncation, evaluation holdout. |
| C8 storage/worker shutdown | `test_collection_memory`, `test_worker_limit` | Streaming writes, budget cleanup, child-process cap; no default eight-worker rerun. |
| C9 final selection | `test_selection` (5 tests) | 12-block eligibility, champion fallback, frozen selection hash before holdout, resume idempotence. |
| R1 deterministic strikes/statuses | Rust resolver tests, `test_engine_contract`, rule completion tests | Exact 10@60%=7, 10@100%=11, slowed 8→6, zero/0% boundaries, poison tick 6 at the own-turn boundary, firststrike/death/drain, status immunity/precedence. Old RNG/injection paths are absent. |
| R2 forecast/identity | `test_engine_contract`, `test_candidate_provenance`, `test_pipeline_contract` | Point-mass forecast, effective samples 1, fixed-state seed independence, snapshot/restore identity, profile propagation and mismatch rejection. |
| R3 Astra adaptation | `test_astra_adaptation` (3 tests), `test_four_player_teacher` (2 tests) | Six public **value-level** tactical positions with old-teacher counterexamples, source/profile/parent hashes, frozen original package preserved, derived package built. This is not a full legal-board per-position trace, and teacher strength remains unverified. |

## Exclusions and limits

- `test_lite_default.test_lite_final_evaluation_has_only_astra_controls` was not run: it needs an archived checkpoint artifact that is not part of the source package; the file fails before evaluation logic.
- `tests.test_core.test_capacity_and_cuda_defaults` retains the pre-existing `768066` versus `771714` capacity mismatch seen on unmodified `master`. It is unrelated to this refactor and is not counted as a pass.
- The native differential game run was not executed. `test_differential_runner` (5 tests) passed, but no native 1.18.8 corpus comparison was claimed.
- No native gameplay, packaging, Windows acceptance, or stochastic native semantics were re-validated.
- P6 external inference is not implemented; D1 remains pending.
- R3 remains a value-level tactical check; a full-board six-position query trace and any adapted-teacher strength comparison remain unrun.
- `test_core` and native adapter tests that need an installed runtime are outside this lite acceptance panel.

## Reuse

The earlier state/replay, reward-window, phase-chain and memory evidence is not repeated here; this panel exercises the changed owners only. The reduced end-to-end run (L1) is recorded below. It is wiring evidence only; the panel's numeric and gate claims do not depend on it.


## L1 reduced full-loop run

**Source identity:** `master` at `34cbe94` (this panel plus #25–#29), archived to `/home/tongshu/myDev/wesnothLearning/l1_refactor_20261025/source`. The extension was not rebuilt; `_engine_lite` reported `lite-0.2` and the run manifest recorded `engine_version lite-0.2`, `rng_version deterministic-expected_damage_v1`, `combat_version expected_damage_v1`, teacher profile `expected_damage_v1`.

**Configuration:** one format (`duel`), `bc-games 1`, `bc-batch-games 1`, `bc-records 128`, `bc-validation-records 128`, `validation-interval 100`, `final-blocks 30`, `workers 2`, `trainer-threads 1`, CPU, seed `20261025`, lite for play and evaluation. The BC phase was requested for `0.02 h`; PPO for `0.08 h` with the recorded reason `L1 reduced full-loop acceptance; BC gate not claimed`; evaluation for `0.3 h` with `L1 reduced final-evaluation entry; strength not claimed`.

**Commands:**

```bash
python -m learning run --run-dir .../runs/l1_reduced_20261025e --engine lite --evaluation-engine lite \
  --formats duel --bc-games 1 1 1 --native-bc-games 0 0 0 --device cpu --workers 2 \
  --trainer-threads 1 --hours 0.02 --phase bc --final-blocks 30 --validation-interval 100 \
  --bc-batch-games 1 --bc-records 128 --bc-validation-records 128 --seed 20261025 \
  --wesnoth .../.runtime/install/bin/wesnoth
python -m learning phase ppo --run-dir .../runs/l1_reduced_20261025e --formats duel --force \
  --reason "L1 reduced full-loop acceptance; BC gate not claimed" --hours 0.08
python -m learning run --resume .../runs/l1_reduced_20261025e
python -m learning phase evaluate --run-dir .../runs/l1_reduced_20261025e --formats duel \
  --reason "L1 reduced final-evaluation entry; strength not claimed" --hours 0.3
python -m learning run --resume .../runs/l1_reduced_20261025e
```

**Observed run:**

- BC committed 12 batches (versions 0–11), 4 optimizer updates each, reaching `bc_complete` at version 11 with the BC gate not claimed.
- PPO committed 5 batches at versions 12–16: updates `6 (kl_stop, 1262 committed decisions)`, `4 (kl_stop, 510)`, `8 (completed, 796)`, `7 (kl_stop, 852)`, `4 (completed, 84)`. Two or more PPO updates were applied before the deadline.
- Checkpoint recovery: after batch 12 committed at version 13, the trainer process was killed with `SIGKILL` while batch 13 had three complete rollout jobs and one incomplete shard. Resume retried the unlogged rollout job, committed batch 13 (`4` updates, `kl_stop`, `510` decisions), then continued through versions 14–16 and stopped at the PPO deadline with stage `ppo_complete`.
- Final entry: stage `final` selected `last_ppo.pt` at version 17 as a fallback (`reason: no retained champion`), wrote `selection.json` with `frozen_before_holdout: true` and `selected_sha256 b9a40e3eead8adf9b69a722e93364769289615e2af79582e4ecf25d584766006`, ran 30 complete control blocks / 60 games, and finished at stage `finished`. The summary status is `not_passed` (policy `0.75` versus Astra `2.25`, difference `-1.5`, 95% interval `[-2.0, -1.0]`); this reduced panel is not a strength claim.
- Checkpoint identities: `latest.pt` `6921e07a3cffa51e8ce315d60962b40b8783f0d8140ba804a8a7d0efdae1e06d`; selected `b9a40e3eead8adf9b69a722e93364769289615e2af79582e4ecf25d584766006`.

**Interpretation and limits:**

- This run proves the reduced chain reaches BC, forced PPO, checkpoint resume after a kill, and final evaluation on lite. It does not prove convergence, strength, native semantics or gate passage.
- The resume was not compared against a separate uninterrupted control run of the same future. Exact future equality at a committed boundary remains evidenced by the C4/C6 unit tests; L1 itself shows correct continuation after the interrupted job was retried.
- Status checks: the 30-minute cron entry `*/30 * * * * .../status_check.sh` was installed and logged manual checks at `01:50:53` and `02:01:09`. The run finished at about `02:26`; the scheduled tick at `02:30:01` fired and logged `process: stopped`, `summary.status: finished`. The scheduler is verified, but no scheduled mid-run tick is claimed.
- L1 remains an open acceptance item in `docs/TEST.md` for the exact uninterrupted-control comparison and a scheduled mid-run check; it is not recorded as passed here.

## Evidence

- `acceptance_master.log` — 273-test run.
- `acceptance_stage.log` — 17 stage/controller/terminal tests.
- `acceptance_rust.log` — `cargo test --release`.
- `engine_identity.txt` — imported lite profile.
