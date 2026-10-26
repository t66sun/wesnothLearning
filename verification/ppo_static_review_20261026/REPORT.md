# PPO initial static review — 2026-10-26

Scope: current source review and local parsing of previously downloaded evidence. Baseline checkout `08c1a32615b6798dbe265149a81df50129c6e43f`; training source `822082d654cd19a6474aa36f837137c1ec7cb83c`, run `v5_lite30h_20261025`. The runtime owners cited below have no diff between these revisions, checked separately from unrelated packaging/documentation changes.

No SSH, model load/inference, optimizer execution, new tests, games or training. Source was located with CodeGraph before code reads. This is static diagnosis, **not root-cause confirmation or Ubuntu acceptance**. Maintained next steps: [English plan](../../docs/ppo_diagnosis_plan.md), [中文方案](../../docs/ppo_diagnosis_plan_zh.md).

## Evidence and fresh local calculation

- [Completed-run/export report](../lite_export_20261026/REPORT.md): original selected identities and final panels. [Installation](../lite_export_20261026/INSTALLATION.md) separately preserves the authorized local-trial exception and FFA4's failed 1e-5 parity gate. Nothing here closes that gate.
- Local `delivery/lite_final_20261026_draft/summary.json`: SHA-256 `07ff69ebc0bb406e8fe985ddf38b61f83ca6a88b464fb7266f84e3438affd788`.
- Local manifest: SHA-256 `aabd9fac77292a5234a5995eed71d8d9d3a12bfd92c24e115a098655f210b437`.
- Reproduce from repository root: `python verification/ppo_static_review_20261026/summarize_existing.py`. It reads only existing JSON. Exit 0; captured derived output: [observations.json](observations.json). The algorithm finds the smallest period by exact equality across all 30 original numeric scores.

| Format | Candidate / selected | Final difference, original 95% interval | BC overall / recruit | Score period / distinct scores |
| --- | --- | --- | --- | --- |
| Duel | 470 / 400 | -1.75, [-2.25, -1.25] | 99.19% / 240 of 248 | 6 / 3 |
| FFA4 | 213 / 100 | +0.0138889, [-0.0166667, +0.0444444] | 91.27% / 90 of 119 | 3 / 3 |
| 2v2 | 136 / 100 | -1.625, [-1.9875, -1.275] | 86.63% / 40 of 43 | 3 / 3 |

All panels have 30 blocks, zero missing and zero fault games. Score cycles: Duel `[-3, 0, -3, -1.5, 0, -3]`, FFA4 `[0, 0.125, -0.0833333]`, 2v2 `[-0.75, -1.125, -3]` (rounded here only). **Equal scores do not prove equal trajectories.** These intervals are copied historical results, not newly established independent-scenario intervals. The BC gate sample is not post-PPO accuracy or native strength.

## Static source anchors

Line numbers refer to baseline source; repository-relative links open the current file.

| Lead | Source and symbols | Supported fact / missing proof |
| --- | --- | --- |
| H1: independence | [schedule.py](../../learning/schedule.py) `factions:11`, `evaluation_jobs:22`; [maps.py](../../learning/maps.py) `decorate:63`; [data.py](../../learning/data.py) `split:12`; [lite_policy.py](../../learning/lite_policy.py) `game_spec:13`; [state.rs](../../engine_lite/src/state.rs) `new:28`; [combat.rs](../../engine_lite/src/combat.rs) `expected_damage:44` | Fixed initial specifications, deterministic core, repeating map/faction schedules and seed-bearing family split. Actual cross-split input/trajectory collisions remain untested; preserve stochastic student sampling and other consequential context when comparing |
| H2: update dynamics | [ppo.py](../../learning/ppo.py) `update:47`; [experiment.py](../../learning/experiment.py) `finish_train:321`; [model.py](../../learning/model.py) `Policy:29` | Shared PG/value/BC/entropy gradients; pre-step batch KL gate; retained Adam at BC transition. Need zero-step behavior parity, then bounded gradient/step diagnosis |
| H3: credit/weight | [data.py](../../learning/data.py) `advantages:219`; [rewards.py](../../learning/rewards.py) `RewardConfig:11`, `transition_reward:78`; [updates.py](../../learning/updates.py) `prepare:13`, `setup:32` | Own-turn GAE, terminal/truncation and decision-normalization versus window-weighting. Manual oracle and complete trajectories required before asserting a defect |
| H4: teacher/action space | [four.lua](../../learning/teachers/gpt6astra/lua/four.lua) `recruit:119`; [data.py](../../learning/data.py) `BCSampler:164`; [candidates.lua](../../lua/candidates.lua) `generate:209` | Fixed recruit heuristics, continued BC anchoring and bounded candidates. Distinguish teacher errors, student errors and absent candidates. 43 recruit validation targets do not establish broad generalization |
| H5: selection/domain | [evaluate.py](../../learning/evaluate.py) `bootstrap:17`, `selection_key:88`; [experiment.py](../../learning/experiment.py) `validate_model:378`, `_select_final:612`, `final_evaluation:642` | Bootstrap resamples supplied blocks; negative-score champion possible; selected differs from latest. Need matched-panel lineage; native strength unmeasured |

The [2026-10-24 investigation](../training_stall_20261024_1544/REPORT.md) discusses limited learning/KL stops and then-unfixed metrics/controller issues on its own run. It does not replace a complete current-run PPO history audit. Existing rolling-window and V1–V6 repairs are not reopened without new counterexamples. `_read_all` in `sequences.py:403` decodes all families: bounded BC admission is not evidence of PPO prefix truncation.

`FrozenPolicies.choose` (`lite_policy.py:60`) uses frozen PyTorch weights for lite student decisions. Lua export accumulation error therefore does not establish an online lite PPO error; S2 still checks actual behavior/learner parity.

## Stock RCA decision and capability gap

The user supersedes Astra-only future operation; implementation remains unchanged this turn.

- `experiment.py:275` substitutes Astra for lite baseline; `lite_host.py:126` rejects official baseline. `teacher_jobs` (`schedule.py:66`) and `manifest.freeze` (`manifest.py:35`) enforce Astra.
- Native teacher querying (`native_rpc.lua:87`) still loads Astra; `sample.py` stamps Astra/DAgger provenance, and `data.validate_record` requires it. Merely switching to native is insufficient.
- Stock baseline uses native `--controller <side>:ai` (`vendor/arena/match.py:102`). Astra's use of the RCA evaluation-loop stage name does not make it stock default AI.
- `collector.wrap` (`collector.lua:48`) intercepts Lua action functions. Complete capture of C++ RCA actions and a legal read-only next-action query are **unproven**. Resolve these before claiming complete BC/DAgger replacement.
- Replace all new active teacher/opponent/partner/DAgger/rehearsal/reference/validation/final/config/provenance dependencies. Preserve history and student self-play roles. Never relabel native-Astra as RCA. Native randomness/throughput differ from lite; a portable RCA implementation is not established.

## Status and limits

PASS, local static calculation only: parsing, hashes, original panel/gate extraction and score periods. Documentation/link/diff checks accompany this change. Existing acceptance is REUSED only as historical context: [V1–V6](../refactor_repairs_20261025/REPORT.md), [budget/startup](../final_review_lite30h_20261025/REPORT.md) and export/installation above; no new runtime acceptance.

Local documentation validation: `git diff --check` exited 0. A UTF-8/Markdown relative-link check inspected nine new/updated document/evidence files and 129 relative links, with zero missing targets, replacement characters or unclosed code fences. JSON sanity assertions confirmed periods 6/3/3, recruit denominators 248/119/43 and all three recorded BC gates. `git diff --exit-code 822082d... 08c1a326... -- <cited runtime owners>` exited 0. These validate the report inputs and documentation only; they are not training tests.

NOT RUN / unwritten: full current-run exposure inventory, scenario/trajectory deduplication, behavior replay, gradient ablation, new GAE oracle, RCA action/query probes, replacement implementation, N1 acceptance, new games, training and native strength. H1–H5 are ranked hypotheses with discriminators, not five proven defects. Proposed checks stay in the plan rather than becoming passing TEST items; the plan does not authorize server execution or a new run.
