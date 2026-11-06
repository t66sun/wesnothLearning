# Acceptance plan

> Language: English | [中文](TEST_zh.md)

## F2. Ordinary BC and critic calibration under the finite task

- **Status/reason:** The new task has no trained-policy acceptance. Earlier 30-turn BC evidence used continuation semantics; the historical 60-turn formal run failed FFA overall coverage at 88.08% and is not relabelled.
- **Minimal Ubuntu inputs/procedure:** After separate training authorization, create a new finite-task BC run from scratch or an explicitly identified weights-only initializer, with fresh compatible data and unchanged gates. Audit initializer exposure before selecting independent validation/holdout scenes. Reuse this task's boundary fixtures; compare independent completed MC returns with critic predictions after BC and bounded PPO.
- **Pass criteria:** Every existing corpus/coverage/imitation/design gate passes, task-compatible checkpoints and rows are observed, and scored-terminal MC calibration is reported separately from external-cut bootstrap consistency. Do not claim improvement from GAE self-consistency or a small panel.
- **Evidence:** Planned new dated evidence for the separately authorized experiment; [historical formal run](../verification/formal_30h_scratch_20261106/REPORT.md) and [objective diagnosis](../verification/team_critic_horizon_20261106/REPORT.md) retain their original scope. The new-task training/calibration run is not yet performed.
- **Training blocker:** Blocks claims of finite-task BC readiness, PPO benefit or convergence; it does not authorize the experiment.

These items do not authorize collection or training.
