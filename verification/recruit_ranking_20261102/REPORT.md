# Recruit ranking diagnosis and exposure probe

2026-11-02, Ubuntu. **Ordinary BC remains FAIL. No production sampler, loss, model or gate change is adopted.**

## Frozen identity and read-only diagnosis

Parent: `/home/tongshu/acceptance/team_bc_readiness_20261102/runs/team_bc`, team2v2 `last_bc.pt`, SHA-256 `ffb554ca152ac93e3602bd45c98841238ef7ee59640b5bf7fb4ba64ba8148a97`. It remains unchanged after fitting.

The old data/checkpoint are evaluated using their v1 runtime at `/home/tongshu/acceptance/recruit_label_full_20261102`, source `d1c56453a55b251cbf4f6cb0aac6fe92238db0c8`, through explicit PYTHONPATH. No v1 record is relabelled or accepted by the current v2 runtime. Python is `/home/tongshu/venv/bin/python`, one CPU thread. The existing frozen rules link is reused.

Diagnostic source `809dd81d765b4eb8dc2c27990830d87148be5367` was shipped by git archive into fresh `recruit_ranking_fixed_20261102`. The script verifies the checkpoint/teacher hashes and reconstructs exactly the previous JSON recruit audit from the same 2048/1024 row reads (seeds 20261103/20261101). It also reproduces 24/98 training and 11/59 validation exact predictions. Runtime file hashes, label-audit hash and detailed classifications are in `fixed/ranking.json`.

The 180-second-capped read-only diagnostic exits 0 in 18.89 seconds. No optimizer or game runs in this step. Initial source `427b667c2b89ed484fd155484266e879eabd6da8` failed before prediction because Python coordinate tuples were compared directly with JSON lists; the correction normalizes that comparison through JSON. Original failure and both exact commands are preserved in `initial/` and `fixed/`.

| Validation recruit classification | Count / 59 |
| --- | ---: |
| Exact teacher action | 11 |
| Inferior type under reconstructed teacher preference | 33 |
| Predicted another action kind | 6 |
| Inferior placement | 5 |
| Same type and equally preferred placement | 4 |

All validation rows have complete own-unit counts and matching enemy counts in the existing audit. No label has another candidate with identical candidate-varying tensors consumed by Policy (actions, local/geometry and actor/target features, types, indices and masks). This excludes that specific within-row information collision, not all possible representation limits. Four tied-placement mistakes cannot account for the 48 exact errors. Twenty-one of the 33 inferior-type cases have matching coarse recruitment contexts somewhere in the full training corpus, but only four in the selected training batch. These are type-count/boost/available-type contexts, not equal full policy inputs.

## Fixed-family recruit exposure arm

Source `9ab42656e957016cd52aabe8e20c7ecb341a6132`, fresh archive at `/home/tongshu/acceptance/recruit_retention_fit_20261102`; same frozen v1 runtime and parent. Each original family's exact row quota is preserved. Up to one quarter is reserved for distinct recruit labels from that same family, keeping existing recruits and filling with baseline non-recruit rows. Selection uses training rows only; raw recurrent histories remain attached. No new games or checkpoint writes.

The control is the completed original-loss experiment in `verification/bc_learning_curve_20261102/REPORT.md` (source `27d2b4b99822fc3950bdcf85f9f13082b1a24a58`). Between that source and the chosen runtime, the only changed `learning/` file is `experiment.py`; the direct curve uses identical model, BC, data sampler, sequence and update implementations. Restored Adam/Python/Torch RNG and validation inputs are unchanged. Initial held-out metrics reproduce the control. No redundant control fit was launched.

- Total target rows: **2048 -> 2048**; families: **12 -> 12**, with every family's quota unchanged.
- Recruit labels: **98 -> 230**; attack: 339 -> 310; move: 1382 -> 1291; end turn: 229 -> 217.
- Selected-family compressed bytes: 67,943,528, below the unchanged 96 MiB budget. New retained estimate: 342,745,272 bytes, below 768 MiB. This is an estimate, not measured RSS; the diagnostic rereads families and is not a production cost optimization.
- Prepared windows: 37 -> 49. Expected recruit loss share in the alternative is 22.40%; selecting additional targets also changes their window exposure. This is a retention experiment, not a pure loss-weight comparison.
- Predeclared cap: at most 600 updates / 900 fitting seconds, 1080-second outer limit. Existing complete-epoch planning yields **598 updates**, 46 epochs, 104,227 decision visits; all 49 windows are visited. No interruption or deadline extension.
- Fitting/evaluation: **566.76 seconds**, total process **615.88 seconds**, exit 0. Different decision counts prevent interpreting this as an equal-work speedup.

The first shell setup in `recruit_retention_probe_20261102` stopped before Python because the hash list mistakenly named nonexistent `learning/sampling.py`. The actual sampler is in `learning/data.py`; a fresh directory ran the same committed archive with that corrected command. The setup command/partial hash output remain in `setup/`; actual command, runtime hashes, selection and complete learning curve are in `fit/`.

| Held-out metric | Original retention, 600 updates | Recruit reserve, 598 updates |
| --- | ---: | ---: |
| Recruit exact | 24/59 (40.68%) | 28/59 (47.46%) |
| Recruit type | 32/59 | 33/59 |
| Recruit slot | 46/59 | 54/59 |
| Attack exact | 80/216 (37.04%) | 78/216 (36.11%) |
| Move exact | 277/584 (47.43%) | 279/584 (47.77%) |
| Overall accuracy | 49.25% | 49.25% |
| Cross-entropy | 2.78427 | 2.79207 |
| Ordinary imitation gate | FAIL | FAIL |

At the common 300-update checkpoint, recruit exact improves from 15/59 to 24/59, but the final difference is mostly placement, not type selection. Training recruitment reaches 166/230 exact and 173/230 correct type. More retained recruitment is insufficient to establish the required type generalization. Do not adopt this reader change or claim ordinary readiness from it. All helper changes are diagnostic-only; no formal training implementation acquired assertions or exception wrappers.

## Concrete bounded-loop cost mismatch

The current manual runner declares `turn_limit=30` but does not pass a configurable training limit. `learning/maps.py:decorate` sets training jobs to 60 turns. Read-only inspection of the historical frozen plan and first eight-job BC schedule for **each of duel/ffa4/team2v2** confirms **declared 30, actual 60**. Paths and file hashes are in `turn_limit_audit.json`; `audit_loop_limit.py` reproduces the read. Historical reports and schedules were not rewritten.

Next concrete repair: make the requested manual training-turn limit reach the frozen teacher/PPO jobs while preserving the ordinary default, evaluation schedules, scenario identities, resume and gate requirements. Verify configuration-to-schedule wiring before spending another full-loop budget. Recruit type generalization remains open independently.
