# PPO learning-efficiency and architecture audit

Date: 2026-11-06 (Asia/Shanghai). Audited production baseline: `bfab03d58f67998f9799d59c8656cf23c511993c`.

## Decision

BC followed by PPO remains a credible route for this project. The public microRTS implementation provides a direct successful precedent; Lux and Stratego provide adjacent evidence about long-horizon policy learning. None establishes that our present representation, training distribution, critic, or CPU budget is sufficient. The [primary-source comparison](../ppo_reference_research_20261106/REPORT.md) distinguishes released code, measured results, author claims, and negative results across six projects.

The strongest local evidence concerns the system surrounding PPO, rather than a demonstrated failure of PPO's clipped-ratio formula:

1. **The PPO scenario generator contracts to a tiny, correlated faction/map distribution.** Duel's 3,608 completed training games cover only three faction pairs and six scenario families. Team covers seven scenario families and three ordered faction rosters.
2. **The rehearsal term is not preserving the Astra BC teacher.** Every completed PPO batch reports only `policy` rehearsal after the evaluation-control identity filter excludes the collected teacher labels. This is historical self-imitation, despite spending work collecting DAgger labels.
3. **Team's critic and horizon treatment require immediate investigation.** 32.33% of team PPO games reach the 60-turn cap and depend on value bootstrapping. Actual sampled late values and returns extend well below the complete-game reward range. Whether the cap is an external truncation or the task's scored terminal must be settled before choosing a remedy.
4. **A large update count conceals little independent experience and frequent KL stops.** Each batch has four focal learner games. The complete duel/team batches contain 728,533 distinct decision targets in total; 69.4%/89.6% stop early for KL. Repeated optimizer visits are not fresh experience.
5. **The existing final results did not directly measure PPO's benefit over BC.** New matched BC evaluations now supply that anchor. They find no statistically established improvement, and no statistically established regression. Team self-play coordination was already weak at the BC checkpoint.

Do not extend the same formal run or replace PPO solely on the present evidence. First make the learning distribution, target semantics and strength measurement coherent; then run bounded, separately authorized comparisons. Main training implementation was not changed by this audit.

## Scope, provenance and observed work

All execution was on Ubuntu through `ssh cpuServer`. No Windows tests, formal training, training-data collection, third-party training reproduction, native strength evaluation, checkpoint selection, or deployment were performed. Offline probes load frozen models and compute predictions or gradients without optimizer steps. The unit suites include their own synthetic optimizer checks. The only new game execution was a 120-game frozen BC evaluation, with training/shard fields removed.

Frozen input run: `/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/runs/formal_30h_scratch`.

| Identity | Value |
| --- | --- |
| Formal-run source | `d2e6da5fbd07396c0c4d13a6588f66e1796f80fd` |
| Audited production source | `bfab03d58f67998f9799d59c8656cf23c511993c`; no differences from the formal source in `learning/`, `lua/`, or `engine_lite/` |
| Run manifest SHA-256 | `6de9d81858c71c41de505db2c445bae5229fa8587db7a6d3d66d2ebc3eab3c88` |
| Rules SHA-256 | `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17` |
| Rust extension SHA-256 | `56dd77140411db987377d6de4ffbf562da4d0e5c76bc16d34780da67e60e5ae4` |
| Python | Ubuntu venv, Python 3.12.3 |
| New server evidence root | `/home/tongshu/acceptance/ppo_architecture_audit_20261106` |

The [original acceptance report](../formal_30h_scratch_20261106/REPORT.md) retains its original dates, hashes and limits. New measurements are separate files here; checkpoint/export/schedule hashes for the added match panel are in [bc_anchor/identities.json](bc_anchor/identities.json). Output digests are in [SHA256SUMS](SHA256SUMS).

| Work completed | Observed result | Evidence |
| --- | --- | --- |
| Census of frozen schedules, job results and optimizer records | Distribution, horizons, source exclusions and actual update counts | [run_distribution.json](run_distribution.json), [inspect_run.py](inspect_run.py) |
| Frozen teacher-validation probe | 2,048 identical rows per format, three checkpoints each | [offline_probe.json](offline_probe.json), [offline_probe.py](offline_probe.py) |
| Collection-probability replay | 768 sampled decisions across first/middle/last batches and two formats; maximum absolute log-probability error `4.9588e-6` | Same offline evidence |
| Loss-gradient probes | Four 64-row samples, no optimizer step; actor gradients are nonzero | [gradient_probe.json](gradient_probe.json), [gradient_probe.py](gradient_probe.py) |
| Affected contract suites | 70 tests, 18.892 seconds, `OK` | [contract_tests.log](contract_tests.log) |
| Matched BC anchor panel | 120 new games, 348.928 seconds, 8 workers; all complete, zero game faults | [bc_anchor/summary.json](bc_anchor/summary.json), [results.jsonl](bc_anchor/results.jsonl), [paired_bc_panel.py](paired_bc_panel.py) |

These are diagnostics and wiring checks, not proof of convergence or full native semantics. The first metadata census attempt encountered a null `training_shard`; only the diagnostic reader was corrected before the successful census. No production behavior was repaired to obtain the reported results.

## 1. What the open-source evidence actually supports

| Reference | Useful evidence | Transfer to this project | Limit |
| --- | --- | --- | --- |
| microRTS RAISocketAI / RAI-BC-PPO | 2023 competition winner; a later BC-to-PPO comparison reports aggregate improvement from 71% to 88% | Keep BC anchors; prepare the critic; stratify map/opponent outcomes; measure candidate restrictions | Some matchups regressed from 100% to 0%; largest-map PPO was worse than BC; competition disabled fog/randomness |
| Lux AI 2021 Toad Brigade | Winning released learner uses imitation/teacher constraints and staged reward training | Distinguish current-state teacher KL from old-data hard-label rehearsal; preserve broad action support | IMPALA/UPGO/TD-lambda, not PPO; competition-long training on a dual-GPU PC |
| Lux S2 PPO/Jux | Released account includes KL spikes, repeated-run variability and plateaus despite continued updates | Record policy movement, actual accepted updates, loss-component gradients and strength per usable sample | This author placed 31st in the cited stage, not fourth; same codebase as the microRTS reference |
| DI-star | Released supervised/RL code, value-only preparation and league engineering | Test value readiness at the BC-to-RL transition; evaluate imitation models through play | Not vanilla PPO; strong-scale compute is far beyond this run; privileged-input options cannot be copied |
| Ataraxos Stratego | Public training code/weights, turn-based hidden information, strong measured play | Hidden information is compatible with strong policy optimization; inspect legal information state and structured actions | PPO-style clipping is one part of a larger learning/search system; 163 million finished games and 208 billion steps |
| KataGo | Complete search/training system and documented efficiency improvements | Test representation and prediction targets, rather than assuming a larger network fixes them | Perfect-information search, not evidence for plain PPO or referee-state search under fog |

Sources: [microRTS paper](https://arxiv.org/html/2402.08112v1), [Lux 2021 release](https://github.com/IsaiahPressman/Kaggle_Lux_AI_2021/tree/7b79d1cf9ab28590d27bfa13a6cc1f5b4de640e9), [Lux S2 write-up](https://github.com/sgoodfriend/rl-algo-impls/blob/edc4fac96e794de34b253b9375d9bf0815a36b56/rl_algo_impls/lux/docs/lux_s2_neurips_writeup.md), [DI-star guide](https://github.com/opendilab/DI-star/blob/12b1c69350ad41e17895c602a66a52d98dd58452/docs/guidance_to_small_scale_training.md), [Ataraxos paper](https://www.nature.com/articles/s41586-026-11036-y), [KataGo paper](https://arxiv.org/abs/1902.10565). The companion report pins the inspected code and further source locations.

There is no source-backed reason to conclude that a roughly 30-hour CPU experiment should match these systems. Equally, their larger budgets do not excuse a narrow curriculum or inconsistent targets: spending more on those problems repeats them. A successful algorithm family is feasibility evidence, not an acceptance result for our current configuration.

## 2. Confirmed PPO distribution collapse

The legacy [factions generator](../../learning/schedule.py) indexes six factions with `(block * players + i) % 6`. It yields only three pairs for two-player games and three ordered rosters for four-player games. BC has a broader `teacher_factions` path; PPO's `compose_training_scenario` still resets factions through the legacy generator, then advances map and faction indexes together until the scenario's split is eligible.

This is not merely a seed-count issue. The recorded PPO schedules confirm:

| Measure | Duel | Team |
| --- | ---: | ---: |
| Completed games | 3,608 | 928 |
| Distinct scenario families | 6 | 7 |
| Ordered starting faction rosters | 3 | 3 |
| Synthetic arena games | 1,804 (50%) | 464 (50%) |
| Learner-faction counts, minimum / maximum | 600 / 602 | 115 / 193 |

Duel plays only `Drakes / Knalgan Alliance`, `Loyalists / Northerners`, and `Rebels / Undead`, approximately 1,203 times each. Six distinct non-mirror factions allow 15 unordered pairs. Every non-arena training map is tied to one of those three pairs: Weldyn Channel to Drakes/Knalgan, Sablestone Delta to Rebels/Undead, and The Freelands to Loyalists/Northerners. All six learner factions appearing equally often therefore does not imply matchup coverage.

Team's three ordered rosters occur 155, 464 and 309 times. With alternating team seats, they expose only six unordered ally-faction pairs. Learner counts range from Knalgan's 115 to Undead's 193. Seat rotations and opponent changes do not add missing map/roster combinations.

`game_family` includes seed identity; `scenario_family` describes the underlying scenario. A large unique-game counter can coexist with only six physical duel scenarios. The audit's scenario table includes four interrupted scheduled duel games; the completed-game census excludes them. Team's 928 games include the final four-game batch whose optimization was unfinished; 924 games feed the 231 complete batches.

**Implication:** PPO is being asked to generalize to broader validation matchups after optimizing on a much narrower distribution than BC. This is a confirmed sampling design limitation and a plausible contributor to slow general improvement. It does not prove that those six scenarios cannot themselves improve. A future generator change should assert cross-product coverage and split eligibility over complete cycles, while keeping validation/holdout scenarios excluded.

## 3. Rehearsal preserves historical policy labels, not the BC teacher

The [experiment coordinator](../../learning/experiment.py) reads original teacher, DAgger and historical policy pools, then supplies the evaluation-control teacher identity as a rehearsal exclusion. The [BCSampler filter](../../learning/data.py) removes matching teacher rows. The formal run has no human corpus to replace them. Every completed PPO log reports only `policy` rehearsal: 902/902 duel batches and 231/231 team batches.

The coefficient `bc_aux = 0.1` therefore does not mean that useful Astra behavior remains anchored during PPO. It trains on sampled hard actions from older student trajectories. Such replay can stabilize behavior, but may also preserve mistakes or oppose a useful new action; it is neither a frozen-BC distribution constraint nor teacher KL on current states.

The exclusion is an explicit evaluation-independence design, not a random sampler failure. Repair requires an explicit decision about the intended supervision and benchmark: train-only teacher supervision is not automatically held-out leakage, but removing an identity boundary without revising its contract would be wrong.

There is also work with no effect on this rehearsal loss. [Lite collection](../../learning/lite_host.py) queries the teacher every fourth focal learner decision, up to 32 queries per game, and writes the associated full-history DAgger stream. Those teacher labels are subsequently excluded from PPO rehearsal. This audit did not isolate the CPU/I/O cost, so it does not attach a speculative speedup to removing or using them.

### Frozen behavioral retention

The same 2,048 teacher-validation decisions per format were evaluated at the BC endpoint, selected v100 and latest complete PPO checkpoint. Duel's sample covers 50 seed/game families but only five scenario families; team's covers 22 game families and 14 scenario families. The rows are correlated and are not 2,048 independent strength observations.

| Format / checkpoint | Teacher top-1 agreement | Mean teacher CE | Mean policy entropy |
| --- | ---: | ---: | ---: |
| Duel BC v38 | 64.11% | 2.038 | 0.439 |
| Duel selected v100 | 62.06% | 2.117 | 0.505 |
| Duel latest v940 | 52.49% | 1.619 | 1.411 |
| Team BC v53 | 69.87% | 1.058 | 0.813 |
| Team selected v100 | 63.62% | 1.203 | 1.038 |
| Team latest v284 | 59.38% | 1.305 | 1.418 |

Duel agreement falls on recruitment, movement, attack and end-turn decisions. Team's recruitment agreement falls from 58.65% to 45.11%, and end-turn agreement from 87.29% to 66.67%. These show material policy drift. They do not by themselves show worse play: the duel teacher cross-entropy actually improves while top-1 agreement falls, consistent with a less concentrated distribution.

This sample differs from the original BC gate's bounded 1,024-row validation. It does not retroactively overturn either recorded BC gate. Actual-play comparisons are needed to judge whether the changed choices help.

## 4. Critic calibration and the meaning of the time limit

### What is implemented

The [reward contract](../../learning/rewards.py) uses `gamma = 1`, `gae_lambda = 0.95`, terminal outcomes in `[-1, 1]`, and potential differences with economy/control weights `0.15/0.10`. Cumulative exploration contributes at most `0.10` over a complete episode. Referee-derived reward scalars are labels, not actor inputs.

[GAE](../../learning/data.py) groups records by game and learner side and raises gamma/lambda to the elapsed own-turn span. Multiple actions in the same turn have span zero. Thus it does **not** multiply the terminal signal by 0.95 for every unit action. The lambda trace after 30 and 60 elapsed turns is approximately 0.215 and 0.046; gamma does not discount the final outcome. This remains a critic-dependent bias/variance choice on long games, not a formula error demonstrated by the audit. The recurrent eight-turn gradient suffix is separate from the full-trajectory return calculation.

At natural terminal, the final reward includes the outcome and zeroed next potentials. At a truncated cap, the final label's outcome is ignored, legal end-state potentials remain, and the frozen policy supplies a value bootstrap. The algebra probe confirms that a synthetic truncated record with terminal label +1 or -1 yields the same return 0.2 when its bootstrap is 0.2; the equivalent true terminals produce +1 and -1. This proves the distinction, not that truncation is inherently incorrect. [Time-limit semantics](https://gymnasium.farama.org/tutorials/gymnasium_basics/handling_time_limits/), [GAE paper](https://arxiv.org/abs/1506.02438).

### Why team is concerning

| Measure | Duel | Team |
| --- | ---: | ---: |
| PPO games reaching cap | 42 / 3,608 (1.16%) | 300 / 928 (32.33%) |
| Mean completed-game length | 14.23 turns | 43.24 turns |
| Latest value mean on frozen teacher-validation rows | -0.032 | -1.002 |
| Latest value minimum on those rows | -1.014 | -2.594 |

For a naturally completed duel/team trajectory at the recorded coefficients, the undiscounted shaped return is `Z - phi(start) + remaining_exploration`. Economy lies in `[-1, 1]`, control in `[0, 1]`, so a conservative lower bound is -1.25. GAE training targets can depart from this bound because they mix estimated future values; a value below the bound is therefore a calibration warning, not an impossible tensor or a proof of code corruption.

This warning also occurs on actual late training data, not only shifted teacher-validation states. In team rollout batch 283, game 1, the final decision is at turn 60, frozen value is about -2.118, and turn-61 bootstrap is about -2.103. The last immediate reward is approximately +0.00459; sampled returns reach about -2.109. Game 2 has a turn-51 last learner action and a turn-61 bootstrap near -1.180. A defeated learner whose team continues can legitimately have such a turn gap; it is not alone evidence of broken indexing.

**Inference:** a weak critic can repeatedly supply biased targets where natural terminal outcomes are absent, particularly in team. Current evidence does not distinguish poor initial calibration, insufficient terminal anchoring, function approximation, distribution shift and other causes. Clamping values or converting every truncation to a loss would conceal rather than settle that question.

The task objective needs a precise answer: is the 60-turn cutoff merely an external sampling boundary for an eventual-win objective, or is reaching a fixed horizon part of the scored game? Bootstrapping is appropriate for the former. The latter needs terminal semantics and a representation of remaining horizon. Training currently uses 60 turns while evaluation scores 30-turn games; the features contain current turn but no explicit cap/remaining-time feature. One fixed cap can be inferred from turn, but differing unobserved caps change the objective.

BC additionally fits raw terminal labels only when value-valid, whereas PPO fits shaped, bootstrapped returns against a changing opponent mixture. A good BC action classifier is not proof that this critic is ready. Measure value bias, MSE and explained variance on natural terminals separately from capped trajectories before testing value-only preparation.

## 5. Optimization, samples and throughput

| Complete PPO work | Duel | Team |
| --- | ---: | ---: |
| Batches | 902 | 231 |
| Fresh focal games per batch | 4 | 4 |
| Unique eligible decisions | 386,593 | 341,940 |
| Mean decisions per batch | 428.60 | 1,480.26 |
| Mean sequence windows per batch | 8.63 | 22.36 |
| Committed / planned optimizer steps | 6,435 / 9,020 | 3,196 / 5,460 |
| Batches ending at KL limit | 626 (69.40%) | 207 (89.61%) |
| Planned steps not executed | 28.66% | 41.47% |
| Committed decision visits, including reuse | 1,149,722 | 833,857 |

Four games can contain many actions but still supply only four outcome trajectories, with substantial within-game correlation. A 1,480-decision team batch is not equivalent to 1,480 independent strategic experiments. One learner seat supplies gradients even when other seats run the same policy. This is valid on-policy learning, but it matters for sample accounting and variance.

The [PPO updater](../../learning/ppo.py) uses normalized advantages, ratio clipping `[0.8, 1.2]`, a 0.02 approximate-KL stop and gradient norm clipping at 0.5. On CPU the update setup selects four sequence windows per logical step, with 32-row microbatches. The configured minibatch number 256 is not a guarantee of 256 independent states. Windows have equal loss weight despite varying lengths; longer games can own more windows, so the comment about long games not dominating must not be read as an equal-game objective.

The KL check rejects the next logical step based on the current selected windows, after earlier steps may have moved the policy. It is not a rollback of the whole batch or an exact global trust region. Frequent stops show that nominal epochs overstate accepted optimization, but do not prove the threshold is wrong. Raising it blindly could make instability worse. The learning rate is fixed at `1e-4`; BC's optimizer state continues into PPO, without a dedicated critic-only transition phase.

### Gradient measurements narrow the explanation

For each format, 64 uniformly sampled rows from the first and last complete PPO batches were replayed with matching model, labels and production coefficients. Gradient norms below include the loss coefficients. No optimizer step was taken.

| Sample | Actor | Value | Entropy | Historical-policy rehearsal | Rehearsal cosine with actor |
| --- | ---: | ---: | ---: | ---: | ---: |
| Duel first | 10.643 | 2.033 | 0.053 | 0.750 | +0.124 |
| Duel last | 3.845 | 2.897 | 0.044 | 0.508 | -0.116 |
| Team first | 5.682 | 0.622 | 0.059 | 0.616 | -0.107 |
| Team last | 6.770 | 1.710 | 0.061 | 0.826 | +0.200 |

Actor gradients are present. These four probes do not support a claim that entropy or rehearsal consistently overwhelms the actor. Rehearsal sometimes opposes it; the late duel value gradient is substantial. The probe is a uniform-row diagnostic, not the complete production window-weighted gradient or Adam parameter displacement, so it cannot attribute all KL stops or long-run drift to one component.

### Wall time is not usable experience

Summing scheduler job start/end intervals gives 75,973 duel, 98,761 FFA and 158,115 team worker-seconds. Across the actual approximately 25h30m run and eight global slots, that is about 45.3% occupied worker-slot wall time. It is not CPU utilization; trainer work and coordination are outside those intervals, and this measurement does not establish an attainable speedup.

FFA consumed substantial collection/evaluation capacity while never entering PPO, so a three-format 30-hour budget is not a 30-hour PPO experiment for either advancing model. In addition, duplicated histories, DAgger writes, bounded pool reads and recurrent replay are plausible costs to profile. No unmeasured item is claimed to dominate runtime. For the next learning experiment, report fresh games, scenario families, learner decisions, accepted updates and strength per wall time together.

## 6. Action support, observation and memory set the possible ceiling

The architecture has useful foundations: shared legal-visible Lua observations/candidates, explicit frozen rollout versions, candidate masks, relational entity attention, combat forecasts, raw-history reconstruction and separate models by format. The sampled probability replay found no large discrepancy in the collection/replay path: maximum absolute log-probability error was `4.9588e-6`, and value error was below `5e-7`. This substantially weakens a probability/history mismatch explanation for these sampled batches, but does not certify every path.

### A shortlist is stronger than a legal-action mask

The policy selects at most 36 retained actions plus end turn under the shared 12,000-work budget. Candidates are heuristically proposed and ranked; this is not the full legal action space with invalid actions masked. A useful move omitted from the shortlist has zero policy probability regardless of PPO training time. Coverage against Astra only measures one teacher's intents, not optimal-action coverage or the cost of the missing actions.

The current generator explicitly preserves primary moves and considers safe retreats; it would be inaccurate to say that it never permits retreats or strategic movement. Nevertheless, the cap and proposal heuristics can impose a tactical/strategic ceiling. FFA's 88.08% teacher coverage already demonstrates a separate support limitation, although FFA never ran PPO and cannot explain duel's measured PPO update behavior.

Before widening budgets, compare retained support with a broader legal-visible oracle on frozen tactical fixtures: recruitment composition, retreat, village timing, leader safety, attack sequencing and time-of-day staging. Distinguish missing actions from bad scoring of available actions. Full-state oracle labels may be used only inside referee/differential tests, never fed to the actor or teacher queries.

### Geometry and history are compressed

The model uses a 16-by-16 board with **nine** spatial channels, two 3-by-3 convolutions followed by global mean pooling, entity attention, exact candidate coordinates and a 19-hex local patch. Terrain identity is a normalized vocabulary scalar, and larger-map cells are accumulated into board bins. This can blur distant topology and creates an artificial numerical relation between terrain categories. Entity coordinates, local patches and handcrafted tactical features mitigate the loss, so no harmful input alias has been demonstrated here.

Memory uses a 128-wide GRU, 32 summary slots and an eight-own-turn differentiable suffix. Its history is based on the first committed post-action memory observation per own turn; current observations, known terrain and last-seen units remain available separately. It is wrong to equate eight-turn backpropagation with eight-turn visibility or eight-turn reward credit. Still, strategically distinct histories or map routes may become hard to distinguish after this compression. Test that possibility with paired legal-visible states before increasing network size or changing memory.

Lack of MCTS, a roughly 0.78-million-parameter model, sequential unit actions, and separate per-format weights are design choices, not independently proven root causes. Search and hierarchical/spatial action heads deserve later comparisons only after the measured distribution and target issues are controlled. Referee snapshots cannot be used as a shortcut for fogged planning.

## 7. What the new BC comparison establishes

The original final holdouts evaluated selected v100, not latest PPO v940/v284. They therefore could not directly establish the benefit of the full PPO phase. The new diagnostic reuses each latest candidate's complete frozen 12-scenario nomination schedule and its existing results, and plays the BC endpoint on exactly those maps, factions, rotations and seeds against the same frozen Astra package.

Exported BC and latest PPO tensors were checked for exact equality with their respective checkpoint model states before running. There are 24 new duel games and 96 new team games; each format has 12 complete blocks, 12 distinct scenarios, no missing games and no faults. Team includes both Astra-partner and self-team contexts. Diverging policies need not consume identical later RNG draws; the pairing controls the starting scenario and seed, not a counterfactual combat sequence.

The paired metric is each policy's official score divided by 3: win 1, draw 1/3, loss 0. It is **not win rate**. Results are scenario-cluster bootstrap intervals using the existing 5,000-resample helper.

| Format | BC model | Latest PPO model | Latest minus BC normalized score | 95% interval |
| --- | --- | --- | ---: | --- |
| Duel | v38 | v940 | -8.33 percentage points | [-31.94, +15.28] pp |
| Team | v53 | v284 | +1.74 percentage points | [-6.60, +9.38] pp |

Both intervals cross zero. There is no established PPO improvement, and no established regression. These are existing validation scenarios, not a new untouched holdout; twelve clusters also leave wide intervals. They should not be used to nominate a new checkpoint.

Absolute policy-minus-Astra official-score differences clarify the team baseline:

| Context | BC difference and 95% interval | Latest PPO difference and 95% interval |
| --- | --- | --- |
| Duel | +0.250 [-0.500, +1.000] | -0.250 [-1.375, +0.875] |
| Team overall | -0.500 [-0.813, -0.125] | -0.438 [-0.781, -0.094] |
| Team with Astra partner | 0.000 [-0.375, +0.375] | -0.125 [-0.375, +0.188] |
| Team with self partner | -1.000 [-1.500, -0.375] | -0.750 [-1.375, -0.125] |

Team self-coordination was already weak at the BC endpoint. The evidence supports "PPO did not demonstrably repair the existing weakness", not "PPO destroyed an initially strong team policy".

Other monitoring limitations remain. All 54 FFA and 26 team ordinary trend panels in the original analysis had insufficient scenario design (one block versus a three-scenario floor). Complete but inconclusive nomination panels are mislabeled as incomplete by selection reporting. The latter is a reporting defect; it does not make an inconclusive model superior. Fixed BC anchors and valid per-context trend panels are needed for an interpretable learning curve.

The duel/team evaluation comparison and signed outcome reward are not automatically misaligned merely because individual official scores use 3/1/0: policy-minus-opponent score is +3/0/-3, proportional to the signed outcome. The horizon difference, opponent mixture and team contexts are the substantive objective questions.

## 8. Architecture-wide disposition

| Layer | Finding / current evidence | What remains unproven |
| --- | --- | --- |
| Referee and information boundary | Reward labels are separated from actor tensors; shared legal-visible candidate path retained | Exhaustive absence of leaks and full native semantics were not reaccepted in this audit |
| Training distribution | Confirmed narrow, correlated PPO faction/map support | Contribution to strength can only be isolated by a controlled comparison |
| Teacher-to-PPO transition | Confirmed teacher exclusion, historical-policy rehearsal; measurable behavioral drift | Best retention objective and whether particular deviations improve play |
| Reward/GAE | Own-turn clock and terminal/truncation branch are explicit; algebra reproduces them | Correct task horizon choice and long-horizon critic calibration |
| PPO update | Frozen-version checks, clipping and nonzero gradients; sampled log-probabilities match | Whole-run KL movement, effective Adam steps and best batch/epoch schedule |
| Team/opponents | Training already includes fixed, historical and current enemies and current-policy teammates | Robust coordination across missing ally-faction pairs and stronger opponents |
| Action representation | Heuristic support is bounded; coverage is not optimality | Cost of omitted tactical and strategic actions |
| Observation/memory | Legal history, entities and local geometry exist; compressed distant board/history | Harmful aliasing, useful auxiliary targets, or need for a larger model |
| Evaluation/selection | New BC anchor finds no demonstrated gain; some old trend panels lack sufficient design | Fresh-holdout PPO benefit and stable improvement across training seeds |
| Runtime | Actual sample/update counts and worker-slot occupancy measured | CPU/I/O attribution and attainable throughput improvement |
| Deployment/native transfer | Existing shared Lua/export contracts remain untouched | Native strength, tournament constraints under trained play, and simulation exploitation |

Potential-based shaping and the adaptive controller were also reviewed. The original run retained reward version 0; reported shaping-component scales alone do not show reward domination. There is no evidence here that blindly removing shaping or increasing terminal magnitude would fix the problem. Approximate Lite training and native acceptance remain separate claims.

## 9. Recommended order of subsequent work

These are proposals, not executed training or authorization to collect new training data. Keep each implementation behavior isolated, with a failing-when-reverted assertion and Ubuntu evidence.

1. **Make strength observable before further tuning.** Retain BC, selected and latest checkpoints as distinct anchors; ensure each trend panel meets its declared scenario floor; report actual completeness separately from statistical outcome. Preserve independent final holdouts. Use fixed scenario/seed pairing and cluster intervals for comparisons.
2. **Correct or explicitly narrow the PPO curriculum.** Enumerate intended map/faction/seat/team combinations and assert coverage, eligibility and balance over a full cycle. Either train a deliberately limited specialist and evaluate that scope, or expose the distribution expected at validation. Seed diversity cannot substitute for faction coverage.
3. **Settle the reward horizon and test the critic.** On frozen natural-terminal and capped games, separately measure prediction bias, target variance, explained variance and out-of-range values. Test handwritten own-turn trajectories. Decide the scored horizon before changing bootstrap rules; only then compare critic preparation or target changes, one behavior at a time.
4. **Give rehearsal an explicit purpose.** Choose whether the intended anchor is the frozen BC policy, an independent teacher, or historical self-imitation. Preserve split boundaries and document the evaluator relationship. Compare retention, gradient interaction and actual strength; do not merely increase the current coefficient.
5. **Run a bounded duel learning experiment before another three-format campaign.** Start from the same frozen BC checkpoint; vary one confirmed issue per comparison, keep opponents/evaluation fixed, match fresh learner decisions as well as wall time, and use multiple training seeds. Predeclare improvement and retention criteria; do not promote on a single favorable small panel. Team then needs its own context-stratified experiment.
6. **Investigate support/representation and throughput only with discriminating evidence.** Use frozen tactical fixtures to separate missing candidates from ranking failures, paired public states to test aliases, and profiling to separate game simulation, recurrent learning, decoding and discarded DAgger work. Broader actions, larger networks, search, auxiliary targets or a distributed league are later options, not required assumptions.

The present highest-confidence implementation issue is the PPO distribution. The highest-risk unresolved learning issue is team critic/horizon behavior. Rehearsal and evaluation are confirmed contract/measurement gaps. Their effects can interact, so the report does not assign a fabricated percentage of the failed run to each cause.

## Reproduction and source shipment

Each diagnostic version was committed, packaged with `git archive`, copied to Ubuntu, and extracted into a fresh directory. The host does not need git. Source archives remain on the server; large archives are not added to this evidence directory.

| Directory / archive | Source commit | Archive SHA-256 |
| --- | --- | --- |
| `source/`, `source.tar.gz` | `277b3612d6340cec6715d87f299663fe0aa655cb` | `504eb051cb7bd6b422a13f414d2000b3cbc97ffc7831c4e83a0de076c61ecf49` |
| `v2/`, `source-v2.tar.gz` | `cb8eecbff11e6950861118e689de3b124d963763` | `b21b4d10421ea4ede1251c227178f83d90a34604447e670e77c8beb88f61d135` |
| `v3/`, `source-v3.tar.gz` | `2f0ebc9e3a71a8c9f1e24c403e7d97c0c1c74955` | `2f8253bb32cee5489e38eba3fcb5e6d79656be6879eab34e405b1a7e70f0927e` |
| `v4/`, `source-v4.tar.gz` | `695c4abef824c225c793c47d783d242ef95a7aed` | `61a1aa19c5ff1e3cb5845420fb6afbd48a46969d14a14746f15900836a60591c` |

Successful census, offline probe and unit suites used v2; BC matches used v3; gradient/occupancy measurements used v4. All have identical production implementation. Commands below describe the successful runs; for a rerun choose a new results directory because recorded evidence is immutable.

```bash
audit=/home/tongshu/acceptance/ppo_architecture_audit_20261106
formal=/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source
run=$formal/runs/formal_30h_scratch
python=/home/tongshu/venv/bin/python
export PYTHONDONTWRITEBYTECODE=1
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

cd "$audit/v2"
export PYTHONPATH="$PWD:$formal/.extension"
probe=verification/ppo_architecture_audit_20261106
"$python" "$probe/inspect_run.py" "$run" "$audit/results/run_distribution.json"
"$python" "$probe/offline_probe.py" "$run" "$audit/results/offline_probe.json"
"$python" -m unittest tests.v5.test_ppo_plan tests.v5.test_ppo_resume_counters \
  tests.v5.test_rehearsal_source tests.v5.test_reward_row_schema \
  tests.v5.test_learning_core tests.v5.test_window_memory_cost tests.test_schedule

cd "$audit/v3"
export PYTHONPATH="$PWD:$formal/.extension"
"$python" "$probe/paired_bc_panel.py" "$run" "$audit/results/bc_anchor"

cd "$audit/v4"
export PYTHONPATH="$PWD:$formal/.extension"
"$python" "$probe/gradient_probe.py" "$run" "$audit/results/gradient_probe.json"
```

The report changes no acceptance threshold and does not close existing native/convergence blockers. Resident architecture documentation now links this evidence and corrects its spatial-channel description from ten to the nine channels actually implemented; no tensor or model changed.
