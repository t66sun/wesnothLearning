# Acceptance plan

> Language: English | [中文](TEST_zh.md)

## P1. Frozen BC auxiliary target

- **Status/reason:** Implemented; Ubuntu checks pending. The historical-action baseline and optional frozen distribution target share sampling and stopping.
- **Minimal Ubuntu inputs/procedure:** Run `tests.v5.test_frozen_bc_loss`, `tests.v5.test_frozen_bc_anchor`, rehearsal-source, PPO plan/resume/phase and branch restart suites from a shipped commit with the compiled rules/extension. Fixtures use temporary checkpoints and synthetic existing-state rows; no collection or training run is authorized.
- **Pass criteria:** Forward KL direction and numerical zero at BC, finite padded support, frozen parameters, independent complete histories, equal-window weighting, real runner/export/load/branch/resume identity and coefficient wiring, missing/replaced endpoint failure before updating, and unchanged control/no-drop/stop behavior.
- **Evidence:** New `verification/frozen_bc_anchor_20261106/REPORT.md` after execution; no strength or retention claim from implementation checks.
- **Training blocker:** Blocks use of `frozen_bc_kl`; comparison benefits remain for the separately authorized #227 experiment under #235's task.

## F1. Ordinary FFA BC readiness at the default 60-turn cap

- **Status/reason:** Failed in the formal from-scratch run. FFA collected 960/600 teacher games and passed imitation, per-class coverage, corpus and design gates, but overall candidate coverage was 242,124/274,888 = 88.08%, below 90%; no PPO occurred. The earlier accepted 30-turn, 48-game scope remains valid.
- **Minimal Ubuntu inputs/procedure:** Reuse the frozen formal run's 960 teacher shards and source identity. Diagnose existing missing teacher actions by map, turn and candidate-exclusion reason; after a separately authorized repair, check fixed examples and their unchanged candidate/work limits. A new ordinary 60-turn BC run requires separate training authorization.
- **Pass criteria:** Overall candidate coverage at least 90%, every existing per-class/imitation/corpus/design gate passes, and ordinary transition to PPO is observed without an override. Do not lower the gate or present an offline first-30-turn slice as a new accepted run.
- **Evidence:** [Formal acceptance and analysis](../verification/formal_30h_scratch_20261106/REPORT.md). A regression for the diagnosed long-game candidate omissions is not yet written; no repair is included in this report.
- **Training blocker:** Blocks a claim of three-format default-configuration BC readiness. Duel/team passing BC does not establish improved strength.

These items are plans for the affected behavior only. They do not authorize collection, repair or training.
