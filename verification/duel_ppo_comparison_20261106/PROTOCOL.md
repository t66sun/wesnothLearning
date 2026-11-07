# Bounded duel PPO comparison

Issue [#227](https://github.com/t66sun/wesnothLearning/issues/227). This protocol is frozen before execution. Its implementation, fixture acceptance and launch command require root review before the first game. It authorizes no extension beyond the agreed eight-hour experiment.

## Question and common inputs

Starting from one newly qualified `official-score-30-v1` BC endpoint, compare `historical_action` (A) with `frozen_bc_kl` (B). The auxiliary target is the sole arm difference. Both arms use a fixed Astra opponent for every non-learning seat. A small evidence-only adapter calls production `rollout_jobs` with `history=[Astra]`, `fixed=[Astra]`, and `current=Astra`; the learning policy remains the current arm policy. This is a fixed-opponent experiment, not self-play.

The base production source is `eadad5de2f47cd9f7a1299f8212e833146eb7797`, containing accepted #235/#239/#240. Exact frozen source, checkpoint, rules, opponent and physical board identities are in `inputs.json`. The archived execution source SHA is recorded separately before launch; implementation may add only this experiment's evidence tools. Production training, candidate generation, model, gates, no-drop eligibility and KL settlement remain unchanged.

The old duel BC actor (v38) initializes a fresh finite-task BC run. Critic, Adam, corpus, controller, counters and gates reset. Old data are not relabelled. The new BC uses seed `202611060`, 300 valid teacher games, and all ordinary corpus/imitation/coverage/scenario gates. Human input is an explicitly empty directory. BC must qualify within 150 minutes; otherwise the experiment stops with `prerequisite_failed`, without forced PPO or a replacement seed.

Before creating any PPO arm, record the new complete `last_bc.pt`, matching latest weights, manifest, gate and model-weight hashes in a new `bc-endpoint.json`. All six ordinary same-task branches use this same actor and critic, reset Adam, and inherit its valid BC qualification and compatible corpus. A KL arm pins this exact qualified endpoint as its immutable anchor.

Common settings: CPU; eight global game workers; one trainer thread; one active cell at a time; four rollout games; four epochs; logical minibatch 256; BC/rehearsal pool 2048; validation pool 1024; PPO learning rate `1e-4`; original clip and KL guard `0.02`; `bc_aux=.10`, entropy `.01`. Reward mode is fixed: economy `.15`, control `.10`, exploration `0`, gamma `1`, lambda `.95`. Teacher, DAgger and PPO use the same complete 30-round task. No reward adaptation or tuning is allowed.

## Budget and order

The outer clock starts when the reviewed experiment driver enters preflight, before BC setup. It includes BC preparation, all six cells, selection, evaluation and reporting. Stage ceilings total eight hours; stages may finish early and their unused allocation is not added to another cell.

| Stage | Ceiling |
| --- | ---: |
| Input and environment preflight | 15 minutes |
| New finite-task BC | 150 minutes |
| Six PPO cells | 35 minutes each, 210 minutes total |
| Selection and shared evaluation | 90 minutes |
| Final accounting/report | 15 minutes |

PPO seeds are `202611061`, `202611062`, `202611063`. The frozen cell order is A1, B1, B2, A2, A3, B3. Paired arms share their training seed; no cell is rerun, reseeded or reordered after observing results. A cell admits new batches for at most 30 minutes and has five further minutes for existing training and due validation to settle. Its absolute limit is 35 minutes, including setup. Processes and commands are recorded in a persistent tmux session; only this experiment's owned process groups may be stopped at its deadlines.

Each cell targets **10,000 fresh eligible learner decisions**. Count `planned_targets` once per settled current-policy batch, including zero-step KL-rejected batches. DAgger copies, rehearsal rows and repeated epochs do not count. At the first complete boundary reaching the target, admit no next batch. Keep the full final batch and report its overshoot. Do not truncate a rollout to make integer budgets equal, and do not substitute an equal batch count.

The evidence-only subclass changes the next-batch admission deadline. Pending training and pending validation retain the existing hard deadline. If a hard limit leaves a pending update, preserve its shards, plan and checkpoint, report it as unsettled, and use only the last complete checkpoint for comparison. No optimization resumes beyond that cell's ceiling. A cell below target remains `budget_incomplete`; if fewer than all three pairs meet the target, the primary decision-budget comparison is incomplete even if a descriptive score interval looks favorable.

The #226 duel samples contain 447/536/724 targets per four-game batch, implying roughly 23/19/14 batches for 10k (92/76/56 games). Preparation plus four measured fixed-weight epochs plus ideal four-worker game time was approximately 48/84/89 seconds per sample. Allowing for the additional frozen-anchor forward places the target near 21–30 minutes, with no throughput guarantee. Six thousand targets would require only about 12 median batches/48 games, below the 72-game scenario cycle. Actual coverage is reported; no extra coverage collection is added. The eight-hour budget is not a power guarantee.

## Physical isolation

The initializer's 300 retained teacher shards plus four DAgger shards were traced to their frozen schedules; it has no policy shards or ancestor lineage. Every retained shard uses arena2, the_freelands, weldyn_channel or sablestone_delta. Canonical terrain, starts and dimensions have no overlap with the two planned holdout boards. This audit is repeated from read-only inputs at preflight, and the new optimization inputs are audited before evaluation.

Keep the repository's physical map groups: training maps above, validation `hamlets`, and final holdout `caves_of_the_basilisk`/`ruined_passage`. Task identity does not establish unseen layouts: the existing scenario hash includes the cap, so 60-to-30 changes may repartition internal BC scenarios previously exposed to the initializer. Those internal splits are not claimed as independent generalization evidence. Neither old nor new optimization may use final holdout boards.

## Roles and panels

BC means the shared newly qualified endpoint. Latest means each cell's last complete checkpoint; an interrupted newer checkpoint is listed separately. Selected is frozen by the existing `_select_final` rule, without changing its gates or treating it as latest. All selections freeze before any holdout result is read. A selection may equal BC or latest; equal-weight roles are explicit aliases of one actual evaluation, not independent repeats.

Use the production exporter, `evaluation_jobs`, collector and official score. Common validation seed is `202611067`: hamlets, all 15 distinct faction pairs and complete two-seat rotations (30 games per distinct policy). Common holdout seed is `202611068`: both held-out maps times 15 pairs, 30 distinct scenarios, complete rotations (60 games per distinct policy). Astra's frozen hash is the sole opponent. All roles use the same physical scenes and combat seeds. Interleave policies by scenario/seat to avoid deadline starvation of a whole arm. Missing/faulted blocks remain incomplete; do not replace them with another seed or board.

At most 13 different weight sets are possible (one BC, six latest, six selected): at most 390 validation games and 780 holdout games, plus at most 288 games from the existing nomination procedure. All count against 90 minutes. Reserve the last 60 minutes for holdout; selection and shared validation share the first 30. If an earlier panel is incomplete, report it rather than borrow the holdout reserve. Checkpoint aliases reduce actual games and are disclosed in the role-to-result mapping.

## Estimands and uncertainty

Primary: B minus A **latest** normalized own score on final holdout, at the frozen 10k-target stopping rule. Secondary: latest A minus BC, latest B minus BC, and selected-role results. A duel score is official points `0/1/3` divided by three. Average the complete two-seat rotation first; weight physical scenario clusters equally within each map, maps equally, and training seeds equally. Fresh-decision overshoots and any underfilled cell are shown beside its score; do not interpolate model weights or rescale scores to invent an exact common integer budget.

Use 10,000 paired crossed bootstrap replicates with analysis seed `202611069`. Each replicate draws one list of training-seed indices and one common list of scenario indices **per map**. Every drawn training seed and both arms use that same scenario draw; the shared BC has one observation per scenario and is never treated as an independent BC run for each seed. Report 95% percentile intervals, all three per-seed effects, and the limited training-seed sample size. Decision rows, epochs, aliases and repeated seeds are not extra independent observations.

Report separate predicates, without one hiding another:

- Superior to A: the B-minus-A interval is wholly above zero. Inferior to A: wholly below zero. Otherwise no demonstrated difference; crossing zero is not equivalence.
- Superior to BC: the B-minus-BC interval is wholly above zero.
- Noninferior to BC at the preregistered five-point margin: B-minus-BC lower endpoint is above `-.05`. Clear degradation beyond that margin: its upper endpoint is below `-.05`. Otherwise retention is uncertain.
- Overall positive benefit requires complete budgets/panels, superiority to A and superiority to BC. A B arm can be noninferior to BC while inferior to A; both findings must be reported. No favorable label is issued for an incomplete design.

Only budget exhaustion, failed BC prerequisites, identity errors, nonfinite computation or infrastructure failures stop execution. Intermediate scores do not trigger early stopping, reruns, parameter changes, added seeds or expanded formats.

## Accounting and critic diagnosis

Record sampled eligible decisions, settled fresh targets, unsettled rows, full-batch overshoot, distinct physical scenarios, actual wall time, planned/committed/rejected/never-attempted steps, and inspected/committed/rejected decision visits. Zero-step batches retain their sampled-budget and rejected-work contribution. Do not label unattempted work as CPU waste.

MC diagnosis reuses complete task trajectories already recorded by this experiment. Prefer the first PPO trajectories under the new BC behavior and each arm's late recorded rollouts. Compute independent complete return sums, not GAE-derived targets, and label the actual behavior version. Deduplicate identical A/B trajectories. These are training/on-policy-at-that-time diagnostics; they are not automatically calibration of the final checkpoint. Teacher continuation returns are not BC's own on-policy ground truth. External cuts are a separate table, and no additional evaluation collection matrix is created for calibration.

All commands, PID ownership, source/input hashes, stage exits, raw results, failed attempts and derived reports go into new artifacts under this evidence directory and the new run roots. Protocol and frozen input records remain unchanged after execution starts. No historical evidence is rewritten, and no strength or convergence conclusion follows merely from a successful process exit.
