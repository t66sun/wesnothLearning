# Acceptance plan

> Language: English | [中文](TEST_zh.md)

## F1. Finite official-score task boundaries

- **Status/reason:** Implemented; Ubuntu acceptance pending. New runs use `official-score-30-v1` with true 30-round terminal scoring, gamma 1 and zero exploration.
- **Minimal Ubuntu inputs/procedure:** Ship a committed source archive; run `tests.v5.test_finite_score`, `tests.v5.test_finite_score_identity`, the reward/horizon/branch/turn-limit affected suites and source-line checks. Fixtures use the existing Rust extension with synthetic boards and the actual native Lua runtime, without collection or training runs.
- **Pass criteria:** Formal-score affine equivalence, complete round 30, natural terminals, early external cuts, eliminated teammates, BC/PPO targets, rowpack propagation and old-task rejection pass; a targeted reverted behavior fails its assertion.
- **Evidence:** New output under `verification/finite_score_20261106/`; preserve all failed attempts. Test implementations exist.
- **Training blocker:** Blocks new finite-task experiments until these boundaries pass.

## F2. Ordinary BC and critic calibration under the finite task

- **Status/reason:** The new task has no trained-policy acceptance. Earlier 30-turn BC evidence used continuation semantics; the historical 60-turn formal run failed FFA overall coverage at 88.08% and is not relabelled.
- **Minimal Ubuntu inputs/procedure:** After separate training authorization, create a new finite-task BC run from scratch or an explicitly identified weights-only initializer, with fresh compatible data and unchanged gates. Audit initializer exposure before selecting independent validation/holdout scenes. Reuse this task's boundary fixtures; compare independent completed MC returns with critic predictions after BC and bounded PPO.
- **Pass criteria:** Every existing corpus/coverage/imitation/design gate passes, task-compatible checkpoints and rows are observed, and scored-terminal MC calibration is reported separately from external-cut bootstrap consistency. Do not claim improvement from GAE self-consistency or a small panel.
- **Evidence:** Planned new dated evidence for the separately authorized experiment; [historical formal run](../verification/formal_30h_scratch_20261106/REPORT.md) and [objective diagnosis](../verification/team_critic_horizon_20261106/REPORT.md) retain their original scope. The new-task training/calibration run is not yet performed.
- **Training blocker:** Blocks claims of finite-task BC readiness, PPO benefit or convergence; it does not authorize the experiment.

These items do not authorize collection or training.
