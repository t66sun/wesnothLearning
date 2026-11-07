# Bounded duel PPO comparison acceptance

The preregistered experiment completed in **4h 1m 30.05s**, within its eight-hour ceiling. All six cells crossed 10,000 fresh learning decisions at complete batch boundaries, and both common evaluation panels completed. The result is **inconclusive for playing-strength benefit**: frozen-BC KL minus historical-action CE was **−2.59 percentage points**, with a paired crossed 95% interval of **[−14.63, +7.78]** on the independent holdout. Neither arm showed a significant improvement over BC. The −5-point noninferiority criterion for B relative to BC was also not established. This is neither an equivalence result nor evidence of significant degradation.

The accepted scope is new finite-task **duel BC readiness**, execution of the bounded comparison, and recorded-behavior MC diagnostics. It does not establish convergence, final-checkpoint critic calibration, native strength, FFA/team readiness, or a reason to change the default retention target. No training, collection or new evaluation games were run during this acceptance.

## 1. Frozen experiment and provenance

- Issue: [#227](https://github.com/t66sun/wesnothLearning/issues/227), part of #221.
- Preregistration: [PROTOCOL.md](../duel_ppo_comparison_20261106/PROTOCOL.md), committed at `0c5cfa2a69f160610ab92032c0a6e72deccfca22`; file SHA-256 `a81988b01f57d9002dcc97132eb7f410a67dcacb71f5f2c38bac8f15f077bc7e`.
- Frozen [inputs.json](../duel_ppo_comparison_20261106/inputs.json) SHA-256 `564ba623db85f7e9e754fed95b3a6c4d54df06cb82771c3028f912c781539797`.
- **Executed source:** `43325b33696de4db8ee546e1c6bedb7230a73b37`, based on production `eadad5de2f47cd9f7a1299f8212e833146eb7797`. Its original source tar SHA-256 is `62f97a406854c27241d0a558067c6858b1133ad9ab092ea29d08bdd7e395aef5`.
- Report branch integrates master `602700d` to preserve later teacher work. That integration is **not** the source that trained these policies. The independent search teacher delivered afterward was not used here.
- Host: `cpuServer`, Ubuntu, eight logical CPUs/four cores, about 15 GB RAM; Python `/home/tongshu/venv/bin/python`; eight workers, single trainer thread, `OMP_NUM_THREADS=MKL_NUM_THREADS=OPENBLAS_NUM_THREADS=1`.
- Rules SHA-256 `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`; Lite extension SHA-256 `56dd77140411db987377d6de4ffbf562da4d0e5c76bc16d34780da67e60e5ae4`.
- Frozen Astra package SHA-256 `2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933`; teacher profile `probabilistic_combat_v6`, source SHA-256 `d64e1178c0a8af9b1b10e2626f03e7cb8ed70a5a368d3c38860d40723a903eb5`.

The unchanged relational-v5 model, `work-12000-v8` candidates, rules and feature schema are pinned in the byte-preserved [input audit](recorded/input-audit.json) and [BC endpoint](recorded/bc-endpoint.json). The new task is `official-score-30-v1`: own duel points 3/1/0 map to +1/−1/3/−1; gamma=1, lambda=.95, economy/control potentials=.15/.10, exploration=0. Both natural finishes and the complete 30th round zero terminal potential and bootstrap. The model, candidate support, reward coefficients, PPO clip/KL policy and evaluation-control exclusions were not tuned.

All six branches started with the same new qualified BC actor **and critic**, with Adam reset. The single comparison variable was `ppo_aux_target`: A=`historical_action`, B=`frozen_bc_kl`, both at `bc_aux=.10`; entropy=.01, PPO learning rate=1e−4, four epochs, minibatch=256, rehearsal=2048, validation=1024, four rollout games per batch. Seeds were `202611061`, `202611062`, `202611063`, with fixed order **a1,b1,b2,a2,a3,b3**. All non-learning seats used the same frozen Astra package, including schedule entries labelled history/current; learner policies continued to update. This is a fixed-opponent experiment, not dynamic self-play.

## 2. New BC qualification and physical exposure

The old three-format formal run supplied only the duel `last_bc.pt` actor initializer. Its manifest SHA-256 was `6de9d81858c71c41de505db2c445bae5229fa8587db7a6d3d66d2ebc3eab3c88`, and source checkpoint SHA-256 was `05908d7f972148ccc7b39b8df0cc00435e2176861654a632de44c379b94953ab`. The weights-only path selected duel, reset the critic, optimizer, corpus, controller and gates, and did not relabel or import old data. The old human-data directory had no duel shards.

New BC used seed `202611060` and passed the unchanged corpus, coverage, imitation and scenario-design gates after **300 new teacher games** and **32 distinct scenario families**. Overall coverage was **90.5854%**. It reached v38 in **3,859.09s** (64.32 minutes), below the 150-minute allowance. The opening probe remained nonblocking and did not supply qualification. No `--force` or lowered gate was used.

| Shared endpoint identity | SHA-256 |
| --- | --- |
| New BC weights | `d9d694f04d4179a5c65bbc29307a8e425a245d650d47f55a36ec04abeb206801` |
| New `last_bc.pt` | `8fc61bbb0be5c2ad8d2ec5b56760ce3dbfa08eed008c490e9b2233624ea91ebe` |
| New manifest | `bb9915fd2ed1e3d2375c4732b604a5a1d2b3ebb8441bc2976c3b4d74ad76dd48` |
| New gate | `9cf9239a19c4d5713fe9158df43de618572474016f37e85c017b4a41700744c1` |

Both the old initialization corpus and new BC corpus had 304 retained shards (300 teacher plus four DAgger), all on `arena2`, `the_freelands`, `weldyn_channel`, and `sablestone_delta`. Physical terrain/start/dimension identities had no intersection with the final holdout maps. The six PPO exposure audits also reported no holdout overlap. The old 60-turn cap participates in the scenario hash, so changing to 30 turns can reassign the internal BC split on a previously seen layout; this report does **not** call that internal validation unseen-layout generalization. The common validation map `hamlets` and final maps `caves_of_the_basilisk` / `ruined_passage` remain separate from optimization layouts. Final holdout was not used for tuning or checkpoint selection.

## 3. Decision budgets and observed cost

The clock began at **2026-11-06 09:33:25.060534 UTC**, with the unchanged hard deadline **17:33:25.060534 UTC**. The driver exited zero after **14,490.0527s**, approximately **13:34:55 UTC**. Pausing interactive monitoring did not pause or restart the clock. The user subsequently confirmed the same eight-hour ceiling.

Each PPO cell admitted new batches for at most 30 minutes and reserved up to five further minutes for pending settlement. All six reached the decision target before the admission deadline. Full final batches were retained; no rollout tail was discarded and no extra batch was admitted after reaching the target. Saved time was not transferred to another cell.

| Cell | Seed suffix | Fresh decisions | Overshoot | Settled batches / policy games | Scenario families | Wall seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| a1 | 061 | 10,054 | 54 | 26 / 104 | 60 | 1,511.28 |
| b1 | 061 | 10,313 | 313 | 28 / 112 | 63 | 1,655.20 |
| b2 | 062 | 10,083 | 83 | 27 / 108 | 62 | 1,621.92 |
| a2 | 062 | 10,201 | 201 | 25 / 100 | 58 | 1,499.82 |
| a3 | 063 | 10,142 | 142 | 27 / 108 | 62 | 1,539.36 |
| b3 | 063 | 10,150 | 150 | 26 / 104 | 60 | 1,581.95 |

The actual exposure was **60,943 fresh decisions in 636 completed policy games**, not an equal-batch comparison. Each cell visited all four training maps. The scenario-family counts describe observed exposure, not exhaustive scene coverage. All pending training/validation fields and unsettled eligible-decision counts were empty/zero. DAgger, replay and epoch revisits did not count toward fresh targets. No zero-step batch occurred in this realization; the frozen driver fixture explicitly verifies that such a batch still consumes its fresh sampling budget.

| Cell | Planned steps | Committed | KL-rejected | Never attempted | Inspected decision visits | Committed visits | Rejected visits |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| a1 | 256 | 122 | 25 | 109 | 23,885 | 20,094 | 3,791 |
| b1 | 276 | 132 | 27 | 117 | 24,398 | 20,476 | 3,922 |
| b2 | 252 | 117 | 26 | 109 | 23,519 | 19,479 | 4,040 |
| a2 | 256 | 113 | 25 | 118 | 22,439 | 18,530 | 3,909 |
| a3 | 252 | 118 | 27 | 107 | 23,677 | 19,417 | 4,260 |
| b3 | 252 | 114 | 26 | 112 | 23,883 | 19,813 | 4,070 |

There were 716 committed, 156 rejected and 672 never-attempted steps. KL stopped 156 of 159 batches, but the actual rejected decision visits were **23,992 / 141,801 = 16.92%** of inspected visits. Unattempted planned steps did not perform optimizer work. These are different denominators and are not interchangeable with a percentage of wall time wasted. Wall times include each cell's collection, rehearsal, optimization and due validation. B's observed cost cannot be attributed solely to an extra anchor forward: realized trajectories, batches and overshoot differ.

Selection plus the common validation/holdout phase took **1,207.42s**, below its 90-minute limit. No cell needed a deadline extension or replacement seed. Full histories, process deadlines, event logs and schedules are preserved in [the raw metadata archive](raw-metadata.tar.gz); the original [result.json](recorded/result.json) retains each complete ledger.

## 4. Roles, panels and matched scores

There are thirteen named roles but only **seven unique weight sets**: shared BC and six PPO endpoints. Every selected checkpoint is byte-identical to that cell's latest complete `last_ppo.pt`, through the existing `no retained champion` fallback. Selection was frozen before holdout. This supplies no separate evidence that checkpoint selection improves strength; aliases reuse the same actual evaluation games. Complete checkpoint/weight hashes are in [roles.json](recorded/evaluation/roles.json).

The common validation panel had 15 faction-pair scenarios on `hamlets`, two seats per policy and seven unique policies: **210/210 games**. The final holdout had 15 scenarios per map on two independent maps, both seats, and seven policies: **420/420 games**. All roles used matched scenario/combat seeds. There were 186 natural finishes plus 24 completed-round-30 terminals in validation, and 333 plus 87 respectively in holdout. Every row was a completed finite-task result, with no external cut or contestant fault. Lite's cap result has `turns=31` after finishing round 30; `game.truncated` alone is not the external-cut contract.

Score is the learner's official points divided by three, averaged over seats, equally over scenarios/maps, and then equally over training seeds. The shared BC score is measured once per scenario rather than treated as three independent baselines.

| Endpoint (`selected` = `latest`) | Version | Holdout W / D / L | Normalized holdout score |
| --- | ---: | ---: | ---: |
| Shared BC | 38 | 17 / 16 / 27 | 0.37222 |
| a1 | 64 | 25 / 11 / 24 | 0.47778 |
| b1 | 66 | 17 / 12 / 31 | 0.35000 |
| a2 | 63 | 21 / 10 / 29 | 0.40556 |
| b2 | 65 | 22 / 10 / 28 | 0.42222 |
| a3 | 65 | 16 / 17 / 27 | 0.36111 |
| b3 | 64 | 20 / 11 / 29 | 0.39444 |

The three-seed mean is 0.41481 for A and 0.38889 for B. The preregistered bootstrap used 10,000 draws with seed `202611069`. Each draw samples the training-seed axis once and scenario indices once within each map; those same scenario draws apply to all sampled seeds, both arms and shared BC. The unit is a matched scenario with its seat rotations, not independent decisions or duplicated role aliases.

| Contrast | Holdout change, percentage points | Crossed 95% interval | Common validation change [95% interval] |
| --- | ---: | --- | --- |
| **B − A (primary)** | **−2.59** | **[−14.63, +7.78]** | −5.56 [−19.63, +9.63] |
| A − BC | +4.26 | [−5.56, +15.19] | +11.85 [−7.78, +30.00] |
| B − BC | +1.67 | [−6.67, +11.11] | +6.30 [−11.11, +24.44] |

Per-seed holdout B−A is **−12.78, +1.67, +3.33 points** for 061/062/063. No seed was rerun or omitted. All three aggregate intervals cross zero. B superiority to A, B superiority to BC, and significant B inferiority to A are each unestablished. B's BC-relative lower bound is below −5 points, so the specified noninferiority criterion fails to establish preservation; its upper bound is above −5 points, so degradation beyond that margin is also unestablished. A likewise has no significant BC improvement and its lower bound is below −5 points. The positive-result rule was not met. No automatic team/three-format expansion or target switch follows.

The complete original [panel summary](recorded/evaluation/summary.json) and independently recomputed [scores, outcomes and intervals](independent_review/results.json) agree. Selected-role statistics are identical to latest-role statistics because they are aliases, not additional trials.

## 5. Complete-return critic diagnostics

The frozen driver reused the first PPO batch from each cell (shared BC behavior) and each cell's final collected PPO batch. It sampled no new MC games and used no teacher continuation return as BC's own-policy truth. A separate implementation recomputed the undiscounted same-side sum of all future `reward_step` values from each recorded decision, without using GAE targets.

Forty-eight requested trajectory references reduce to **35 unique trajectories plus 13 aliases**, with **2,933 scored decisions**, no missing files and no external cuts. Deduplication uses complete semantic trajectory content; duplicate A/B first-batch trajectories and a repeated trajectory across seeds do not count as independent observations. The first-batch behavior was BC v38. Late behavior versions were a1 v63, b1 v65, b2 v64, a2 v62, a3 v64 and b3 v63, each **before** its final optimization update.

| Behavior group | Unique trajectories | Decisions | Decision-weighted bias (`value − MC`) | MSE |
| --- | ---: | ---: | ---: | ---: |
| Shared BC first-PPO behavior | 11 | 751 | +0.31227 | 0.58072 |
| Late PPO behavior, six cells | 24 | 2,182 | −0.24399 | 0.72879 |
| All unique trajectories | 35 | 2,933 | −0.10156 | 0.69087 |

Pooled explained variance is **0.19757**. The original scenario-mean bias interval is **[−0.20448, +0.43087]**. Phase rows are decision-weighted summaries of the independently verified per-trajectory metrics. The early and late samples differ in behavior weights and realized states, so their MSE difference is not a matched causal effect of training or retention mode. These measurements do not establish calibration of final latest/selected weights; those weights had a further update after the recorded late trajectories. No calibration-quality threshold or converged-critic claim is introduced after seeing the results. [Original MC records and actual behavior hashes](recorded/mc-diagnostics.json)

## 6. Acceptance commands, retained failures and archives

The original launch and ten responsibility fixtures are recorded in [LAUNCH_ACCEPTANCE.md](../duel_ppo_comparison_20261106/LAUNCH_ACCEPTANCE.md). The controlled counter reversion produced a numeric assertion failure (`5000 != 11001`) rather than a missing-module error; see [reverted-budget-test.log](../duel_ppo_comparison_20261106/reverted-budget-test.log). That evidence remains unchanged.

For post-run acceptance, source `95a53dfde4de96c8a68d6e4170a20d91601f015e` was archived to `/home/tongshu/acceptance/duel_ppo_review_20261107_95a53df/source`. Its tar SHA-256 is `eb1893cef92848fb92e5ee3cf0adca01f279ecce5f94a48380cd7329933e355f`. The independent implementation checks all 630 actual scores, crossed intervals/per-seed results, thirteen role files and parameter identities, B anchors, real non-learning opponents, all six budgets and threshold-crossing final batches, and every MC trajectory/alias plus pooled moments. [Review log](independent_review/review.log) reports exit zero. The original ten driver fixtures also passed on this integrated source in **0.023s**; see [integrated-fixtures.log](independent_review/integrated-fixtures.log). No unchanged test suite was rerun afterward.

Executed read-only command, with `PYTHONDONTWRITEBYTECODE=1`, the recorded extension on `PYTHONPATH`, and one numerical-library thread:

```sh
/home/tongshu/venv/bin/python \
  /home/tongshu/acceptance/duel_ppo_review_20261107_95a53df/source/verification/duel_ppo_acceptance_20261107/independent_review.py \
  /home/tongshu/acceptance/duel_comparison_20261106_43325b3/source/runs/duel_ppo_comparison_20261106 \
  /home/tongshu/acceptance/duel_ppo_review_20261107_95a53df/results.json

# From the integrated review source directory, with the same environment:
/home/tongshu/venv/bin/python -m unittest -v \
  verification.duel_ppo_comparison_20261106.test_contract
```

The first independent audit (`3dc36bd`) stopped because its assertion treated the engine's raw `game.truncated` cap marker as an external cut. [The failure log](independent_review/first-attempt.log) is retained. The corrected audit requires `task_terminal=True`, outer `truncated=False`, and distinguishes natural victory from `reason=turn_limit`, `turns=31`, `winner=0`. No production behavior or recorded result changed. A preliminary field-read probe also used the wrong level for `history`; its [captured failure](read-only-probe-failure.log) is distinct from experiment/test outcomes.

Archiver source `5600b1f92bba30c47b52d931ee30bc1e12fd2e7e` ran from a separate fresh source archive:

```sh
/home/tongshu/venv/bin/python \
  /home/tongshu/acceptance/duel_ppo_archive_20261107_5600b1f/source/verification/duel_ppo_acceptance_20261107/archive_results.py \
  /home/tongshu/acceptance/duel_comparison_20261106_43325b3 \
  /home/tongshu/acceptance/duel_ppo_archive_20261107_5600b1f/evidence
```

[ARCHIVES.json](ARCHIVES.json) identifies both archives and the unchanged executed-source tar. [RUN_FILES_SHA256.json](RUN_FILES_SHA256.json) lists **8,894 original files / 5,529,366,323 bytes**. The complete run, including checkpoints, exports, raw rows and indexes, remains on the server at `/home/tongshu/acceptance/duel_ppo_archive_20261107_5600b1f/evidence/complete-run.tar.gz`: **4,857,602,811 bytes**, SHA-256 `55b8571a2f68757d90e156a46f0f3aa050c3d9474a2a4bf9d4ab08e183bf1141`. The repository's byte-preserved [raw-metadata.tar.gz](raw-metadata.tar.gz) includes all run JSON/JSONL/log files, full plans, per-game results, schedules, manifests and selection records: **6,408,518 bytes**, SHA-256 `424d3167a8fff6d6e672f7dd709c415ef0e82304fc4844abc9f6071d71ad2087`. Readable `recorded/` files are copies of original outputs; original manifests and dated 20261106 material were not rewritten. [Archive command output](archive.log)

This closes the bounded experimental question with an inconclusive strength result. Further training, final-policy calibration, native comparisons or expansion to other formats require a new explicitly authorized experiment and retain the remaining acceptance limits.

[SHA256SUMS.json](SHA256SUMS.json) identifies the local acceptance files, including this report, the independent audit source/results and byte-preserved downloaded evidence.
