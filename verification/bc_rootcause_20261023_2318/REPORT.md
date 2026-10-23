# FF4 bottom-up investigation, state-reuse fixes and T5 acceptance

Started 2026-10-23 23:18 Asia/Shanghai; acceptance completed after midnight on 2026-10-24, within the additional hour authorized by the user. Stage: `/home/tongshu/myDev/wesnothLearning/validation_training_repair_20261023_194022`, `.venv/bin/python`, Ubuntu CPU. No formal run or installed game AI was changed. The original failed [T5 report](../bc_quality_ubuntu_20261023/REPORT.md) is preserved.

## Outcome

**T5 restricted movement acceptance now passes.** Reuse the accepted 2v2 result, 257/507 (50.69%) versus zeroed 79/507 (15.58%). FF4, trained on four independent families and tested once on the two previously frozen fresh families, reaches **126/257 (49.03%)** versus zeroed **28/257 (10.89%)**. Both arms use the same seed-99 initialization, data, sampled decision count (24,788) and exactly 120 updates, Adam 3e-4. No model/loss/default training parameter changed, and no checkpoint was selected on the fresh holdout.

The original two-family FF4 training corpus was insufficient for this restricted early-generalization check. Adding two independent training trajectories, while keeping approximately the same decision exposure and exactly the same optimizer-step budget, increases old-development movement from 80/268 (29.85%) to 110/268 (41.04%); the fresh holdout confirms the gain. This identifies limited training diversity as an important cause in this small experiment, not proof that every future FF4 accuracy problem has the same cause. The formal default already targets 600 FF4 teacher games and is unchanged.

Two separately reproduced runtime defects were also fixed: teacher queries after JSON snapshot restoration, and duplicate Lua-host installation during adapter reset. These defects did not occur in the original fresh-game T5 experiment and do not explain its low accuracy.

## Fresh acceptance details

The original FF4 validation set was development data throughout this investigation. Fresh families `50837296b2749c70e02e28088e0085f92fe92bed484a1637fc2c79c8ce8017c8` and `9baeaccad27e16c5cf0fc7826b574e5dda8e53e743a31b720712dac540ac313a` were frozen before the previous repair trials and were neither collected nor evaluated until the four-family candidate and both final checkpoints were fixed. No fresh result was used for tuning.

- Four training families, 1,443 matched rows, all six factions. The two added families/maps/seeds/faction rotations are frozen in `diversity_plan.json`; they are disjoint from development and fresh holdout. Each game is at most 12 turns, all four Astra seats collected.
- Training coverage: movement 523/523; overall 1,443/1,454 (99.24%). Fresh coverage: movement 257/257; overall 730/742 (98.38%); recruit 105/105, attack 272/284.
- Fresh quality excludes eight single-candidate rows, leaving 722 decisions. Both validation families and all six factions are represented. This is family holdout on existing training maps, not unseen-map or per-faction strength acceptance.

| Fresh FF4 arm | Move | Recruit | Attack (including move_attack) | Overall | CE |
| --- | --- | --- | --- | --- | --- |
| Normal tactical inputs | 126/257 (49.03%) | 31/105 (29.52%) | 44/272 (16.18%) | 262/722 (36.29%) | 2.22406 |
| Zeroed tactical inputs | 28/257 (10.89%) | 28/105 (26.67%) | 48/272 (17.65%) | 173/722 (23.96%) | 3.04228 |

**All real formal BC gates remain enforced.** Recruit, attack and overall quality do not all pass; T5 only accepts the previously specified movement-input benefit. This is not convergence, play strength, permission to force PPO, or authorization to start formal training. Candidate/forecast caps remain 128/16, schema 5/v3 and 776,178 parameters remain unchanged.

## Bottom-up evidence and rejected routes

`PLAN.md` was written before the detailed investigation. `RESULTS.json` contains compact measurements; `manifest.json` links full server artifacts/checkpoints by path, size and SHA256.

| Route | Result and interpretation |
| --- | --- |
| Labels/features/candidate collisions | No duplicate candidate inputs or ambiguous teacher-input rows in either format's train/development pools; action one-hot kind matches metadata. No widespread tactical clipping. Original full-action FF4 failure reproduced exactly. |
| Batch, candidate/entity permutation, grad/no-grad | Eight fixed decisions: maximum tested numerical difference about 1.91e-6; gradient-enabled versus no-grad context gives zero difference. No implementation inconsistency found in this scope. |
| Fixed 64-row fitting | Four balanced classes, original complete prefixes, 120 updates at 3e-4: full-history 60/64 (93.75%), empty-history 59/64 (92.19%), movement 16/16 in both. Production window sampling gives 50/64, still 16/16 moves. Capacity/gradient flow can fit the actual examples. |
| Remove BC terminal-value supervision | 73/268 moves (27.24%); not an improvement. The original FF4 corpus has 95 valid negative terminal targets, all Undead; 2v2 has none. This difference does not explain the failure by itself. |
| Detach value gradients from shared features | 81/268 (30.22%); insufficient. Not adopted. |
| Remove history on full corpus | 62/268 (23.13%); worse. Not adopted. |
| Extend unchanged optimization to 480 updates | Train move 236/253 (93.28%), train CE 0.49674, development move 100/268 (37.31%), development CE 3.52814. Initial underfitting gives way to strong overfitting; extra updates are diagnostic only and do not satisfy the original 120-update acceptance cap. |
| Increase LR to 1e-3, fixed final 120 | 63/268 (23.51%). Intermediate scores fluctuate; no best-checkpoint substitution. Not adopted. |
| Random/Top-3/Top-5 | Original development move random top-1 expectation 3.37/268 (1.26%); actual top-1 80/268, top-3 163/268, top-5 188/268. The model learns a substantial preference but ranking remains imperfect. These diagnostics never replace argmax acceptance. |
| Teacher wall-time instability | Twelve existing later movement states, three unchanged queries each: actions agree with recorded intents; instrumented scans report no wall/simulation cutoff. This excludes timing as the explanation for those sampled states, not every dense late-game state. |
| Explicit public combat-economics estimate | 74/88 wrongly selected predicted attacks are uneconomic under the estimate; 186/210 teacher attacks are economic. A fixed experimental input substitution improves attack 48→66/262 and CE, but movement only 81/268. No new feature/schema was adopted. |
| BC-only shared-context dropout | 77/268 (28.73%); not adopted. |
| Independent decision draws | 82/268 (30.60%), 23,040 decisions, about 256 seconds; not adopted. This exploratory route preserves the per-microbatch loss formula but mixes valid-value targets differently, so it is not a clean causal isolation of sampling variance. |
| Two additional training families | Fixed 120 updates, unchanged production learning path: development 110/268 (41.04%), fresh 126/257 (49.03%). Accepted bounded data remedy; no default or architecture change. |

The original three unsuccessful kind/ranking/context-head experiments were reused from the prior report, not rerun. The user-provided checklist's small-set, metric, class and baseline questions were answered with existing/new minimal evidence; no 100-row rerun, network expansion, full performance matrix or BC→PPO→final matrix was added.

## Concrete runtime fixes

1. `engine_lite/lua/host.lua:copy`: serde-restored arrays can expose a protected boolean through `getmetatable`. Passing that to `setmetatable` crashes the next teacher query. Copy ordinary data without the marker while retaining actual table metatables for unit methods.
2. `learning/adapters.py:LiteAdapter.reset`: Rust already creates the new Lua VM and reinstalls saved modules. Python's second installation consumes already-cleared bridge/clock globals and fails. Remove the duplicate installation.

`tests/v5/test_teacher_state_reuse.py` exercises the real Rust/Lua API: FFA4 and 2v2 teacher snapshot round-trips, repeated serialization/restore, unchanged game state, and reset versus a fresh configured engine. Before changes, two tests produced three errors; after the fixes and a release rebuild, both tests pass. The original real-game failure at validation decision 113 was then replayed without the diagnostic workaround: restored teacher intent matches the original and the game state is unchanged. Passed unrelated tests were reused.

```bash
/home/tongshu/venv/bin/maturin develop --release --manifest-path engine_lite/Cargo.toml
.venv/bin/python -m unittest tests.v5.test_teacher_state_reuse -v
.venv/bin/python -u - < verification/bc_rootcause_20261023_2318/restore_real_case.py
```

The build used the isolated venv and existing Rust cache; Rust embeds host.lua, so rebuilding the extension is required. `state_fix_identity.json` records before/after sources and the new extension hash. Local versus tested source text was checked after UTF-8 BOM, line-ending and final-newline normalization; raw tested hashes and transport source copies are retained. The main server checkout and historical runs were not deployed or resumed.

## Reproduction and handoff

Diagnostics run from the isolated stage via `.venv/bin/python -u - < verification/bc_rootcause_20261023_2318/<script>.py`, with OMP/MKL/OPENBLAS threads 1; experiments use at most two workers per script. The recorded order is diagnose → optimization_routes → learning_regime / teacher_replay → trade_diagnostic / trade_probe → generalization_routes → diversity_trial → fresh_holdout. Some first payload invocations exposed import/setup issues before their corrected run; final outputs and the dedicated red regression remain explicit.

Use existing reports and frozen weights for review; do not rerun passed acceptance for bookkeeping. `fresh_holdout.py` is the one-time acceptance entry, not a repeatable tuning loop. A later code/data change that invalidates this holdout needs newly frozen families, never tuning on these results and calling them independent again. Formal startup remains a separate user instruction and must preserve all BC/PPO gates. Native terminal observation capture (T6) remains pending and is unrelated to the default lite movement acceptance.
