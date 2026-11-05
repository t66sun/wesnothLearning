# Open-source game reinforcement-learning evidence for the PPO architecture review

Date: 2026-11-06 (Asia/Shanghai). Local baseline: `bfab03d58f67998f9799d59c8656cf23c511993c`.

Scope: primary-source research and source inspection. No local or server training, collection, or third-party reproduction was performed for this report. No training implementation or frozen input was changed. Published results below belong to their authors; they are not acceptance evidence for WesnothLearning.

## Decision supported by the evidence

BC followed by PPO has enough demonstrated potential to justify diagnosing the present implementation before replacing its algorithm. The closest direct precedent is microRTS: it includes actual competition success and a measured BC-to-PPO improvement. The strongest newer adjacent precedent is Ataraxos, a turn-based hidden-information wargame with public training code and weights. Its learning loop includes clipped policy ratios, but it is a more elaborate system than plain PPO.

This does **not** establish that the present candidate space, observations, rewards, credit assignment, opponent distribution, and compute budget are adequate. Those are separate empirical questions. Nor does it imply that a model must improve on every matchup: the direct microRTS precedent contains severe regressions after PPO.

The useful comparison unit is completed games, actual learner decisions, retained training targets, optimizer updates, and measured strength per compute. Comparing a 30-hour run with another project's wall time without those denominators is inconclusive.

## Evidence map

| Project | What is actually available | Evidence and relevance | Main limitation |
| --- | --- | --- | --- |
| [RAISocketAI / RAI-BC-PPO](https://github.com/sgoodfriend/rl-algo-impls/tree/edc4fac96e794de34b253b9375d9bf0815a36b56) | PPO and BC code, configurations, checkpoints, paper | Closest direct BC-to-PPO example; multi-unit economy/combat | Two-player microRTS; competition fog and randomness disabled |
| [Toad Brigade, Lux AI 2021](https://github.com/IsaiahPressman/Kaggle_Lux_AI_2021/tree/7b79d1cf9ab28590d27bfa13a6cc1f5b4de640e9) | Training/inference source and historical submitted agents | Competition winner; long economic horizon and coordinated unit control | IMPALA/UPGO/TD-lambda, not PPO; simultaneous orders |
| [Lux S2 PPO/Jux](https://github.com/sgoodfriend/rl-algo-impls/tree/edc4fac96e794de34b253b9375d9bf0815a36b56/rl_algo_impls/lux) | PPO/JAX environment integration, write-ups, model | Detailed learning failures and diagnostics in a similar resource game | Not a championship-strength result; same codebase as RAI, not independent corroboration |
| [DI-star](https://github.com/opendilab/DI-star/tree/12b1c69350ad41e17895c602a66a52d98dd58452) | Supervised/RL training, league, pretrained Zerg agents | Full-game partial-observation strategy with imitation warm start | AlphaStar-style actor-critic; strong results require large resources |
| [Ataraxos Stratego](https://github.com/AtaraxosAI/stratego/tree/92db29e8ffc323b1b8a2804b5c3f84695d036b05) | GPU simulator, training, policy weights, source tests | Alternating turns, hidden information, long strategic horizon | No recruitment economy; research system combines learning and search |
| [KataGo](https://github.com/lightvector/KataGo/tree/d91ea855110dae533f0aada947b2b7d78cc8a4e1) | Complete training/search engine and distributed training ecosystem | Evidence about learning efficiency and auxiliary prediction | Perfect-information, deterministic game; AlphaZero-style search, not PPO |

Selection used demonstrated outcomes, inspectable learning code, and relevant failure modes, not repository popularity. The comparisons below distinguish source inspection from reproduction.

## 1. microRTS: the strongest direct precedent, including negative results

The author's paper reports RAISocketAI winning the 2023 competition among eligible submissions. Its seven models used about 70 GPU-days and 1.5 billion steps. Later BC plus value fitting followed by sparse-win/loss PPO raised the reported aggregate benchmark from 71% to 88%. This is direct evidence for the route, with important bounds: the BC comparison used 20 games per opponent/map, and PPO reduced one matchup from 100% to 0%; on the largest map it was worse than BC. The paper reports 23.3 GPU-days for BC and another 49.1 for PPO, with 33.9 PPO GPU-days on the largest map to little benefit. Competition fog and stochasticity were disabled. [Paper, sections 1, 3.5, 4.3, 5.2 and appendices G/H](https://arxiv.org/html/2402.08112v1)

The source makes several comparisons concrete:

- The [BC configuration](https://github.com/sgoodfriend/rl-algo-impls/blob/edc4fac96e794de34b253b9375d9bf0815a36b56/rl_algo_impls/hyperparams/acbc-Microrts.yml#L8) fits a value target as well as imitation and includes action-count loss scaling. Value readiness is therefore part of the warm start, not a consequence that can be assumed from acceptable action accuracy.
- The [BC-to-PPO configurations](https://github.com/sgoodfriend/rl-algo-impls/blob/edc4fac96e794de34b253b9375d9bf0815a36b56/rl_algo_impls/hyperparams/ppo-Microrts.yml#L1337) are explicit experiments, with schedules and a large-map phase that freezes the policy/backbone. The current source snapshot is not interchangeable with every historical paper table.
- The [self-play wrapper](https://github.com/sgoodfriend/rl-algo-impls/blob/edc4fac96e794de34b253b9375d9bf0815a36b56/rl_algo_impls/wrappers/self_play_wrapper.py#L81) tracks learner seats separately from frozen opponents, rotates checkpoint assignments, and returns rewards for the original learner indexes. Seat bookkeeping is a correctness issue, not merely a sampling preference.
- The [technical description](https://github.com/sgoodfriend/rl-algo-impls/blob/edc4fac96e794de34b253b9375d9bf0815a36b56/rl_algo_impls/microrts/technical-description.md) exposes spatial actor heads, invalid-action masks, three value heads for distinct rewards, and later sparse-result emphasis. It also makes the inference budget a first-class constraint.

**Inference for Wesnoth:** retain the last BC model as an evaluation anchor. Inspect each format, opponent, map family and seat separately before accepting an aggregate gain. Candidate retention and critic calibration deserve investigation before changing PPO coefficients. A legal-action mask in microRTS is not evidence that deleting strategically useful legal Wesnoth moves is harmless. In particular, 90% teacher-action coverage measures agreement with one teacher distribution; it neither measures optimal-action coverage nor bounds losses on the omitted tactical states.

## 2. Lux AI 2021: strong policy learning on a personal machine, not a PPO proof

The competition identifies Toad Brigade as first place. Its released account describes IMPALA with UPGO and TD-lambda, frozen-teacher KL regularization, and 20 million shaped-reward steps before sparse-result training. A single spatial network coordinated the fleet; the final model had approximately 20 million parameters. Training used an 8-core/16-thread, dual-GPU PC over the competition, not a claimed single-day run. Its action representation retained broad legal choices, with transfer amounts discretized. [Competition write-up](https://www.kaggle.com/c/lux-ai-2021/discussion/294993), [released account](https://github.com/IsaiahPressman/Kaggle_Lux_AI_2021/blob/7b79d1cf9ab28590d27bfa13a6cc1f5b4de640e9/README.md)

The [final-phase configuration](https://github.com/IsaiahPressman/Kaggle_Lux_AI_2021/blob/7b79d1cf9ab28590d27bfa13a6cc1f5b4de640e9/conf/conv_phase5%2B_final_model.yaml) specifies result rewards, discount 0.999, entropy cost 0.0002, teacher-KL cost 0.005, and separate actor/learner GPUs. These numbers describe that phase and that action clock; they are not suggested Wesnoth defaults.

**Inference for Wesnoth:** a teacher constraint can stabilize RL, but its form, gradient magnitude, schedule and state distribution matter. Hard-label rehearsal on old teacher states and teacher-distribution KL on current states are different objectives. Measure their effect instead of describing either as automatically preserving useful skill. This example supports broad actor-critic potential, not superiority of a particular PPO implementation.

## 3. Lux AI Season 2 PPO/Jux: useful failure evidence

The later NeurIPS Stage 2 solution is labeled 31st place. It is not the fourth-place FLG solution and must not be presented as such. The competition host separately identifies the fourth-place RL entry; this review did not establish a complete inspectable training release for that entry. [Author submission](https://www.kaggle.com/competitions/lux-ai-season-2-neurips-stage-2/writeups/scott-goodfriend-ppo-using-jux-lux-ai-season-2-neu), [host resource index](https://www.kaggle.com/competitions/lux-ai-season-2-neurips-stage-2/discussion/438939)

The [Jux write-up](https://github.com/sgoodfriend/rl-algo-impls/blob/edc4fac96e794de34b253b9375d9bf0815a36b56/rl_algo_impls/lux/docs/lux_s2_neurips_writeup.md) reports 1,024 environments on smaller maps and 512 on the largest, 32,768-step rollout batches, and two epochs. Training was scheduled for 80 million steps per map stage, with early stopping on stalled runs. It documents KL spikes, synchronous episode-end loss spikes, diminishing progress despite continuing optimization, and restrictive action heuristics. This is evidence that running more PPO updates can coexist with little useful learning.

The [earlier write-up](https://github.com/sgoodfriend/rl-algo-impls/blob/edc4fac96e794de34b253b9375d9bf0815a36b56/rl_algo_impls/lux/docs/lux_s2_writeup.md) also reports substantially different learning curves for repeated runs of nominally the same code/configuration. It separates survival and resource-generation milestones from competitive ability.

The shared [PPO implementation](https://github.com/sgoodfriend/rl-algo-impls/blob/edc4fac96e794de34b253b9375d9bf0815a36b56/rl_algo_impls/ppo/ppo.py#L349) computes sampled-action ratios and clipped loss, records approximate KL and clip fraction, tracks gradient norms and explained variance, and optionally suppresses the policy-loss coefficient after a KL cutoff. That cutoff still allows other loss components to update shared weights. It is not an exact whole-policy trust-region guarantee.

**Inference for Wesnoth:** report accepted optimization work and policy movement, not scheduled batches alone. Audit whether value, entropy and rehearsal gradients dominate the actor update. Plot fixed-opponent strength against actual usable decisions and compute; a low loss or stable KL cannot substitute for that plot.

## 4. DI-star: useful warm-start and league engineering, expensive strength

DI-star releases supervised/RL training and downloadable Zerg-versus-Zerg models. Its README describes stronger pretrained agents as master/grandmaster level; this report treats that as an author claim with published play demonstrations, not a fresh independent ranking measurement. [Pinned README](https://github.com/opendilab/DI-star/blob/12b1c69350ad41e17895c602a66a52d98dd58452/README.md)

The [training guide](https://github.com/opendilab/DI-star/blob/12b1c69350ad41e17895c602a66a52d98dd58452/docs/guidance_to_small_scale_training.md) distinguishes a one-PC baseline from the strong-scale effort: 128 A100s, approximately 10,000 CPU cores, and about two months for RL. It recommends value-only preparation at the supervised-to-RL transition, judges supervised models through actual play, and narrows the small-scale curriculum. The guide's privileged opponent information is **not compatible** with this repository's rule that referee truth never reaches a policy.

The [loss source](https://github.com/opendilab/DI-star/blob/12b1c69350ad41e17895c602a66a52d98dd58452/distar/agent/default/rl_training/rl_loss.py) has multiple action heads, clipped importance corrections, policy-gradient/UPGO/TD-lambda terms, teacher KL, and an `only_update_value` path. It is not vanilla PPO. The [default loss settings](https://github.com/opendilab/DI-star/blob/12b1c69350ad41e17895c602a66a52d98dd58452/distar/agent/default/rl_training/default_reinforcement_loss.yaml) give win/loss its own value and policy coefficients and use discount 1 for that head.

**Inference for Wesnoth:** diagnose whether BC's value target and PPO's shaped-return target agree before assuming a good BC actor is a good PPO initial actor-critic. Opponent diversity is useful, but a full distributed league is not justified before proving ordinary improvement against a fixed opponent.

## 5. Ataraxos: the closest current hidden-information board-game reference

The 2026 paper reports 15 wins, one loss and four draws against Pim Niemeijer. Its move/set-up policies were trained on 16 H100s for a week; belief training used four H100s for four days. The RL run comprised 163 million finished games and 208 billion environment steps. Strong match play additionally used belief-conditioned search. The paper reports benefits from controlled update sizes, learning-rate and regularization schedules, and advantage filtering. These are not guarantees for other games; the match involved one opponent and twenty games. [Paper, Methods and evaluation](https://pmc.ncbi.nlm.nih.gov/articles/PMC13626944/)

The [public repository](https://github.com/AtaraxosAI/stratego/tree/92db29e8ffc323b1b8a2804b5c3f84695d036b05) contains training, a GPU engine, and pretrained policy files. It was inspected, not built or reproduced here.

In [the actual learner](https://github.com/AtaraxosAI/stratego/blob/92db29e8ffc323b1b8a2804b5c3f84695d036b05/pyengine/core/rl.py#L484), the actor loss is the clipped-ratio minimum; additional terms include reverse KL to the collection policy and regularization towards a structured reference distribution. The value target can be categorical over outcomes. Value-return lambda and advantage lambda are distinct, and explicit counters distinguish environment steps, finished games and trained transitions. Current defaults are code evidence, not proof that the exact released match model used every default.

The [move transformer](https://github.com/AtaraxosAI/stratego/blob/92db29e8ffc323b1b8a2804b5c3f84695d036b05/pyengine/networks/move_transformer.py#L94) consumes information-state tensors and legal masks and scores source/destination combinations through learned projections. This is a useful contrast to selecting from a small hand-ranked shortlist. It does not prove Wesnoth should expose every raw move or use this exact architecture.

**Inference for Wesnoth:** partial observability does not make useful policy optimization hopeless. First verify that public history and candidate features retain the facts needed to distinguish strategic choices. Ataraxos does not authorize hidden-state features or literal snapshot search in the Wesnoth actor. Its advantage filtering also conflicts with the present no-drop rollout contract; adopting it would be a separate behavior/contract decision, not a diagnostic shortcut.

## 6. KataGo: a contrast for sample efficiency and representation

KataGo's paper reports learning improvements from global context, auxiliary policy/ownership/score prediction, and altered self-play search allocation. Its reported comparison to ELF OpenGo used roughly 27 V100s for 19 days. The central mechanism is neural-network-guided search; it is not evidence that PPO alone attains the same efficiency. [Original paper](https://arxiv.org/abs/1902.10565)

The maintained [methods document](https://github.com/lightvector/KataGo/blob/d91ea855110dae533f0aada947b2b7d78cc8a4e1/docs/KataGoMethods.md#training-on-multiple-board-sizes-via-masking) explains how exact board geometry can be preserved across board sizes using padding masks and size-aware pooling. This is more relevant to a representation audit than copying Go-specific territory targets. The same document explicitly records superseded methods, so older prescriptions should not be assumed to describe current training.

**Inference for Wesnoth:** test whether spatial compression, missing global context or missing public history creates observation aliases before increasing model size. Auxiliary targets are a later experiment if existing representations and returns are shown to be correct. Standard perfect-information MCTS cannot be transplanted into fogged Wesnoth using referee truth.

## Alternatives whose release scope is often overstated

- **Official AlphaStar:** the [released README](https://github.com/google-deepmind/alphastar/blob/700b1e74364ed5dfc66f6cd2574c5ffac2fa474e/README.md#quickstart) explicitly says online RL training code is not provided. The package offers architectures and offline training/evaluation; it is not the complete original league-training system.
- **DeepNash / OpenSpiel RNaD:** DeepNash is strong feasibility evidence for hidden-information play. But the [historical reference README](https://github.com/google-deepmind/open_spiel/blob/d1dcdf5dc9c0a98a0ff0a6b476236d0cc91bf2d5/open_spiel/python/algorithms/rnad/README.md) says its small MLP implementation only handles smaller games and is unmaintained. [Commit e165bbd](https://github.com/google-deepmind/open_spiel/commit/e165bbddc218a4346d6c75704ed6117ce45f4623) removed it on 2025-05-27. It should not be proposed as a currently maintained drop-in PPO replacement.
- **mini-AlphaStar:** useful research at reduced scale, but its [paper](https://arxiv.org/abs/2209.11553) concerns curriculum-based training on four GPUs/48 CPU threads. A smaller reproduction is not proof that the original AlphaStar strength is obtainable at that scale.

## Concrete questions to take into the Wesnoth audit

These are falsifiable audit questions, not findings that a defect has already been established. The local baseline documentation is [architecture.md at bfab03d](https://github.com/t66sun/wesnothLearning/blob/bfab03d58f67998f9799d59c8656cf23c511993c/docs/architecture.md). Its shared candidate contract, legal-visible observation boundary, current-batch PPO and held-out evaluation are useful foundations.

| Question | Why this comparison matters | Evidence that would discriminate causes |
| --- | --- | --- |
| Do stored rollout probabilities describe the actions actually sampled? | PPO's importance ratio is only meaningful on the collection distribution | Recompute logits/log-probabilities before updating, using identical histories, candidates, masks and stochastic sampling settings; ratio must be approximately one |
| What is one discount/GAE step? | Wesnoth has many unit actions inside a turn; other games' step counts and discount values are not comparable | Hand-computable trajectory including several same-turn moves, opponent turns, true terminal and truncation; report terminal-reward attenuation by turns and by learner decisions |
| Does the critic predict the target used by PPO? | BC fit and shaped PPO return can differ in meaning and scale | At the BC checkpoint, compare value bias, MSE, target variance and explained variance by phase/outcome; separately quantify value and actor gradients |
| Does rehearsal preserve or resist useful policy change? | Current-state teacher KL and old-data hard-label BC are different | On the same frozen batch, measure PPO/BC gradient norms and cosine similarity, and the combined predicted change in chosen-action probabilities |
| Are good actions unreachable? | Legal masking and heuristic pruning define different policy classes | Measure coverage by tactical intent, actor, recruitment type, destination and weapon; inspect matched low-probability mistakes separately from absent candidates |
| Can the inputs distinguish positions with different correct actions? | More capacity cannot recover information omitted before the network | Construct public legal pairs differing in time of day, terrain routes, threat or remembered enemy; test whether model inputs differ meaningfully |
| Does a batch count imply learning work? | Scheduled/committed batches can contain different numbers of useful targets or accepted steps | Count unique games, learner decisions, retained targets, repeated window visits, accepted optimizer steps, KL stops and full elapsed-time split |
| Is the optimizer moving the actor usefully? | Stable losses and gradient clipping alone do not prove policy improvement | KL/ratio/clip-fraction distributions, entropy by action kind, gradient norms before clipping, and frozen-batch actor changes |
| Is self-play improving only against its own weaknesses? | A moving opponent and aggregate score can hide cycling or regression | Cross-play current versus BC, champion, historical snapshots and fixed scripted controls on the same map/seat strata |
| Is selection hiding progress or protecting against actual regression? | Published work reports both genuine growth and catastrophic matchup losses | Evaluate BC, selected, latest and intermediate checkpoints on an identical independent panel; distinguish model learning from nomination/selection errors |
| Does Lite success transfer to native play? | Simulator speed is useful only if learned incentives survive the rules boundary | Compare behavior and official outcomes on matched native/Lite tactical and game panels; fixed-position parity is insufficient for complete strength transfer |

The [reference GAE source](https://github.com/sgoodfriend/rl-algo-impls/blob/edc4fac96e794de34b253b9375d9bf0815a36b56/rl_algo_impls/shared/gae.py#L97) is useful for a small recurrence check: it keeps value bootstrapping, terminal masks and trace propagation explicit. Its fixed-step recurrence is not itself a solution to Wesnoth's variable-duration turn semantics.

## Recommended order after diagnosis

1. Resolve demonstrated distribution, return, seat, truncation or selection defects first. These can invalidate later tuning results.
2. Establish one bounded duel comparison in which PPO is assessed against its own BC starting point and fixed controls at equal source/rule identity. Require actual strength evidence, not lower loss.
3. If correctness holds but learning is weak, compare one change at a time: critic preparation, reward/discount horizon, rehearsal strength, or opponent mixture. Choose using measured diagnostics.
4. Only then spend on larger networks, action-space redesign, richer curricula, auxiliary targets, or search. Extend to FFA and teams after the mechanism has evidence in the simpler format; their equilibrium and credit-assignment problems are not identical to duel.

These are proposed later experiments. This report starts no collection or training and grants no execution authorization. It does not claim a final cause for the failed Wesnoth run; the repository/Ubuntu audit must establish that separately.

## Source identity and verification limits

All pinned file links above were fetched from the corresponding public repository. Their commit identities were resolved through GitHub on 2026-11-06. Historical result sources remain historical; current source snapshots can contain later changes.

| Source | Inspected revision |
| --- | --- |
| rl-algo-impls | `edc4fac96e794de34b253b9375d9bf0815a36b56` |
| Kaggle_Lux_AI_2021 | `7b79d1cf9ab28590d27bfa13a6cc1f5b4de640e9` |
| DI-star | `12b1c69350ad41e17895c602a66a52d98dd58452` |
| Ataraxos Stratego | `92db29e8ffc323b1b8a2804b5c3f84695d036b05` |
| KataGo | `d91ea855110dae533f0aada947b2b7d78cc8a4e1` |
| Official AlphaStar | `700b1e74364ed5dfc66f6cd2574c5ffac2fa474e` |
| Historical RNaD | `d1dcdf5dc9c0a98a0ff0a6b476236d0cc91bf2d5`; removal `e165bbddc218a4346d6c75704ed6117ce45f4623` |

Validation for this artifact is source/link inspection and documentation diff review. Third-party training, checkpoint execution, published-strength replication, and Wesnoth acceptance tests were **not run** in this research workstream.
