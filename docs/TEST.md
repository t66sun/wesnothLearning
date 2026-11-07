# Acceptance plan

> Language: English | [中文](TEST_zh.md)

## S1. Independent search teacher strength

- **Status/reason:** Beam, PVS, UCT and hybrid search are implemented. The bounded experiment completed all 524 holdout games without faults. Duel and 2v2 passed both horizons; FFA gains were +0.0389 / +0.1083 for 30 / 100 turns, with both 95% intervals crossing zero. The overall six-cell strength requirement remains unaccepted.
- **Minimal Ubuntu inputs/procedure:** Reuse the recorded 67 correctness checks and eight-case native query audit for unchanged source. Further strength work requires separate authorization, committed source shipped with `python -m learning.teacher_remote`, and a new dated experiment with frozen validation/holdout designs and complete native seat rotations. Existing holdout results and selected strategies remain immutable. Correctness tests are written; the remaining gap is FFA strength evidence.
- **Pass criteria:** Complete paired seat rotations with at least 12 physical scenarios per format/horizon, zero contestant faults, normalized improvement at least 0.10 and clustered 95% lower bound above zero in all six cells. Report natural finishes, capped draws, interruptions and timing separately. Do not relax the criterion at the deadline.
- **Evidence:** [Completed experiment and delivery](../verification/teacher_search_20261107/REPORT.md): five-hour exploration, 84-game validation, 524-game holdout, selected package identities, timing and preserved failures. The current independent delivery is in `delivery/search_teacher_20261107/`.
- **Training blocker:** Blocks an overall six-cell strength claim and automatic training integration. Duel/2v2 acceptance is limited to the reported maps, scenes and unequal action budgets; the active Astra teacher is unchanged.

## F2. Ordinary BC and critic calibration under the finite task

- **Status/reason:** The new task has no trained-policy acceptance. Earlier 30-turn BC evidence used continuation semantics; the historical 60-turn formal run failed FFA overall coverage at 88.08% and is not relabelled.
- **Minimal Ubuntu inputs/procedure:** After separate training authorization, create a new finite-task BC run from scratch or an explicitly identified weights-only initializer, with fresh compatible data and unchanged gates. Audit initializer exposure before selecting independent validation/holdout scenes. Reuse this task's boundary fixtures; compare independent completed MC returns with critic predictions after BC and bounded PPO.
- **Pass criteria:** Every existing corpus/coverage/imitation/design gate passes, task-compatible checkpoints and rows are observed, and scored-terminal MC calibration is reported separately from external-cut bootstrap consistency. Do not claim improvement from GAE self-consistency or a small panel.
- **Evidence:** Planned new dated evidence for the separately authorized experiment; [historical formal run](../verification/formal_30h_scratch_20261106/REPORT.md) and [objective diagnosis](../verification/team_critic_horizon_20261106/REPORT.md) retain their original scope. The new-task training/calibration run is not yet performed.
- **Training blocker:** Blocks claims of finite-task BC readiness, PPO benefit or convergence; it does not authorize the experiment.

These items do not authorize collection or training.
