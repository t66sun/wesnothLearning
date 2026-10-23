# T5 Ubuntu BC quality and bounded FF4 repair investigation

Date: 2026-10-23. Production base: `f0b1b51` (code inherited from the accepted training repair). This report records a failed acceptance result, not permission to start formal training.

## Frozen experiment

- Ubuntu stage: `/home/tongshu/myDev/wesnothLearning/validation_training_repair_20261023_194022`; interpreter: `.venv/bin/python`, Torch 2.9.1+cpu, one trainer thread. Formal runs and the installed AI were not changed.
- Schema 5, `relational_v5`, `schema5-fixed-20000-v3`, 776,178 parameters. Rule SHA256 `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`; Astra SHA256 `2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933`.
- `identity.json` records the exact source/extension hashes; `plan.json` freezes eight physical families before collection. Each format has two training and two validation families on Clash/Isar's Cross, at most 12 turns, all four real Astra seats collected, six factions in both pools. These are family holdouts on training maps, not unseen-map tests.
- `source_equivalence.json` confirms all 25 tested production source texts match the current local checkout after UTF-8 BOM removal and newline normalization. Raw bytes differ for some Windows files; the server's original raw hashes in `identity.json` remain unchanged. `source_snapshot.json` preserves the exact tested text for this comparison.
- Two collection workers. FF4 has 723 training / 731 validation matched rows; 2v2 has 776 / 808. No read cap truncated either set. Quality excludes single-candidate rows, leaving 724 / 807 validation decisions.
- Same seed-99 initial weights (SHA256 `9ca78889c0fa7329bfc1795528628dd8aaab46eccc78e9aeb46d3713b89edf76f`), data and sampled decision-count traces in both arms. Adam 3e-4, exactly 120 updates (30 epochs × 4 updates), final checkpoint only. No checkpoint was selected by validation accuracy.
- Ablation masks seven move features and entity `next_round`, including current actor/target and replayed history scenes. Network shape and initial weights are unchanged. This also fixes the incomplete history masking of the older Windows helper.

Commands, from the isolated stage with OMP/MKL/OPENBLAS threads set to 1:

```bash
.venv/bin/python -u -m verification.bc_quality_ubuntu_20261023.quality_t5 collect
.venv/bin/python -u -m verification.bc_quality_ubuntu_20261023.quality_t5 compare
```

The first direct-script collection invocation failed to import `learning`; the module invocation above completed. Raw command outputs are `run_collect.ubuntu.txt`, `run_compare.ubuntu.txt`, and `finish_evidence.ubuntu.txt`; detailed per-faction counts and shard hashes are in `comparison_*.json`.

## Original independent T5 results

All numbers below use full-action argmax. Attack includes `move_attack`.

| Format / arm | Move | Recruit | Attack | Overall | CE |
| --- | --- | --- | --- | --- | --- |
| FF4 zeroed | 23/268 (8.58%) | 33/105 | 56/262 | 180/724 (24.86%) | 3.17638 |
| FF4 normal | 80/268 (29.85%) | 26/105 | 48/262 | 223/724 (30.80%) | 2.40772 |
| 2v2 zeroed | 79/507 (15.58%) | 24/99 | 24/106 | 199/807 (24.66%) | 2.90730 |
| 2v2 normal | 257/507 (50.69%) | 27/99 | 17/106 | 349/807 (43.25%) | 1.91819 |

Teacher movement coverage: FF4 train 253/253, validation 268/268; 2v2 train 477/480, validation 507/508. Overall coverage: FF4 723/731 and 731/743; 2v2 776/781 and 808/812. All exceed the T5 coverage conditions. Both train and validation pools contain all six factions, but this does not establish per-faction quality passing.

**T5 passes only for 2v2 movement. FF4 fails the unchanged 35% threshold.** Both models still fail the complete formal BC quality gate (especially recruit/attack). Restricted movement acceptance cannot authorize automatic PPO, establish convergence or demonstrate strength. The original failed FF4 result is preserved.

## FF4 localization and repair boundary

The original validation set became **development data** when the user authorized repair. Its subsequent scores are not independent acceptance evidence. Before any repair optimizer step, `repair_trials/holdout_plan.json` froze new independent validation families, two per format. No new holdout data has been collected or evaluated.

`analyze_ffa4.py` reuses the original final normal checkpoint without updates. Of 188 movement mistakes: 141 select another kind (94 attacks, 47 end turns), 44 select another actor, and 3 select another destination/variant for the correct actor. Train movement accuracy is 123/253 (48.62%); validation is 80/268. This shows both incomplete fitting and a generalization gap, but does not establish the root cause.

Read-only diagnostics:

- `diagnose_type_mass.py`: movement has the highest kind probability mass on 116/268 rows and is the argmax kind on 127/268. Only 13 of the 141 wrong-kind rows already have movement as the highest-mass kind. A conditional-type selector would not resolve most errors and would change the evaluated policy.
- `missing_input_diagnostic.py`: 88 of 94 erroneously selected attacks already have a combat prediction. The 16-forecast budget is therefore not the main explanation for this observed error set. Pure attacks lack the move-risk features, and attack exposure/profit is less explicit than Astra's calculation, but this remains an unproven hypothesis rather than a diagnosed defect.
- `move_priority_diagnostic.py`: conditional on a teacher move, ranking existing full-move candidates by public `move_gain + 8*own_leader` matches 236/253 training and 253/268 development labels. All teacher moves have gain >0.05; only one of 88 development end-turn rows with legal moves has a positive best move gain. This is a representation diagnostic using the known action class; **it is not full-action accuracy or a replacement policy**.

## Fixed development trials

Each trial starts from the same seed-99 production core, uses the same original FF4 training data, Adam 3e-4 and exactly 120 updates. Each runs in a temporary wrapper/monkeypatch; production sources, teacher, gates, candidates and inference are unchanged.

1. `trial_kind_objective.py`: increase just kind marginal supervision from weight 1/30 to 1, keeping exact CE and actor/destination weights. Development move 87/268 (32.46%), recruit 23/105, attack 43/262, CE 2.45294. Rejected: still below 35%, with worse other classes/overall.
2. `trial_candidate_context.py`: add a zero-initialized kind-offset head using max-pooled per-kind candidate hidden representations. Development move 83/268 (30.97%), recruit 35/105, attack 53/262, CE 2.34148. Rejected: insufficient movement improvement; the extra parameters are not adopted.
3. `trial_hard_negative.py`: retain exact CE and original auxiliary loss, adding `relu(1 + max_wrong_logit - teacher_logit)` to supervise the deployed argmax directly. Development move 79/268 (29.48%), recruit 25/105, attack 56/262, overall 220/724 (30.39%), CE 2.41362. Rejected: movement and overall accuracy do not improve.

All three repair trials failed. No production fix was adopted and the FF4 root cause remains unresolved. None of these development scores can clear T5. Scripts are retained for reproducibility; checkpoints and compressed data stay in the isolated server evidence directories, with paths/hashes in `repair_trials/artifacts.json`.

## Handoff

Keep the original failure and rejected trials. Reuse accepted 2v2 movement evidence while its production sources/data remain valid. The next diagnostic is not yet written: freeze up to 64 existing FF4 training decisions, balanced across move/recruit/attack/end-turn, retain complete raw prefixes and all legal candidates, and compare current versus empty histories at the same initialization/data/update budget (120 updates, full-action train-set accuracy and CE only). This separates history/optimization difficulties from remaining feature/generalization hypotheses without collecting games. It is a small-set fitting diagnostic, never an acceptance result; inconclusive fitting requires inspecting the actual loss/gradient trace rather than another holdout-guided tweak. Do not keep scanning weights/heads against the same development data.

Once a candidate repair is frozen, use the predeclared new holdout and the original full-argmax/coverage/update criteria. Retest 2v2 only if shared code/data changes invalidate its evidence. Formal training remains a separate user-authorized action, with all real BC/PPO gates retained. No formal training was started; the final artifact manifest confirms production hashes remain unchanged.
