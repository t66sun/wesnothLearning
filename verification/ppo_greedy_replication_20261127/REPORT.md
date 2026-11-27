# Greedy PPO replication and duel diagnosis

The four frozen policies completed all **288** approved Lite duels against Astra on Ubuntu cpuServer. Greedy PPO averaged **47.84%** of the maximum official score. Shared qualified v38 BC scored **41.67%**. The paired gain was **+6.17 percentage points**, with a crossed 95% interval of **[−3.70, +16.51] pp**. All three training histories had positive point estimates. The preregistered positive-lower-bound and +10 pp point criteria both missed. The interval contains zero, +10 pp and the original +12.04 pp. The measured direction repeated, while the size and reliability of the advantage remain unresolved. [#369 preregistration](https://github.com/t66sun/wesnothLearning/issues/369#issuecomment-7220045375) · [#352 roadmap](https://github.com/t66sun/wesnothLearning/issues/352)

## Where the result changed

| Fixed layout | #359 greedy gain (pp) | Fresh gain [95% interval] (pp) | Fresh gains by PPO history 081 / 082 / 083 (pp) |
| --- | ---: | ---: | ---: |
| Fallenstar Lake | +8.33 | +6.48 [−12.04, +23.15] | +1.39 / +11.11 / +6.94 |
| The Freelands | +1.85 | +10.65 [−5.56, +26.39] | +8.33 / +11.11 / +12.50 |
| Weldyn Channel | +25.93 | +1.39 [−16.20, +21.76] | +1.39 / −2.78 / +5.56 |
| Equal-weight mean | +12.04 | **+6.17 [−3.70, +16.51]** | **+3.70 / +6.48 / +8.33** |

The pooled estimate fell 5.86 pp. Across the same six original ordered faction pairs on Weldyn, v38 went from 10/36 to 39/72 official points (27.78% to 54.17%). The three PPO histories together went from 58/108 to 120/216 (53.70% to 55.56%). The much stronger v38 result on the new combat seeds accounts for most of the change there. It also illustrates how a shared baseline affects all three paired contrasts. Frozen weights permit this seed comparison within the three layouts. They leave transfer to new layouts and training-to-training variation beyond the three histories open. [Original matched greedy panel](../ppo_mode_interaction_result_20261115/REPORT.md)

The larger #349 greedy panel on three physical holdouts found +0.25 pp [−7.84, +8.40]. Fallenstar is the one common layout. On that map #349 gave +6.67 pp across 30 ordered rosters. A descriptive recount of its raw replies for the six #359 rosters gives −0.93 pp (12 slots, official points for BC/081/082/083 of 14/13/16/12). Its other 24 rosters give +8.56 pp (48 slots, 47/57/58/63 points). Roster composition, combat seeds and the compact #349 learner path all limit cross-panel attribution. The three panel estimates are reported separately. [#349 raw evidence](../ppo_vs_bc_acceptance_20261115/REPORT.md) · [Evaluator path comparison](../ppo_transfer_20261115/REPORT.md)

## Official game counts

Each cell gives wins/draws/losses, then turn caps and official points in parentheses. Each role played 24 games per map and 72 games overall. A win earns three points and a draw one. Each v38 result appears once in these counts.

| Layout | Qualified v38 | PPO 202611081 | PPO 202611082 | PPO 202611083 |
| --- | ---: | ---: | ---: | ---: |
| Fallenstar Lake | 4/10/10 (10, 22) | 5/8/11 (8, 23) | 6/12/6 (12, 30) | 3/18/3 (18, 27) |
| The Freelands | 9/2/13 (2, 29) | 11/2/11 (2, 35) | 12/1/11 (1, 37) | 12/2/10 (2, 38) |
| Weldyn Channel | 13/0/11 (0, 39) | 13/1/10 (1, 40) | 12/1/11 (1, 37) | 14/1/9 (1, 43) |
| All maps | 26/12/34 (12, 90) | 29/11/32 (11, 98) | 30/14/28 (14, 104) | 29/21/22 (21, 108) |

## What could improve duel PPO?

1. **Transfer across layouts is the strongest remaining training hypothesis.** All 4,368 #306 rollout games faced Astra. Arena2 supplied exactly half and three layouts supplied the rest. On the two #306 holdouts the same stock PPO checkpoints gained +7.78 pp on A Summer of Storms [+1.11, +15.00] and lost 3.52 pp on The Road to Weldyn [−9.44, +2.22]. This is evidence that PPO can learn a locally valuable policy. The separate three-map #349 panel averaged +0.25 pp [−7.84, +8.40]. In #361 the seen-to-prior-holdout change was −20.37 pp against Astra and +10.19 pp against greedy v38, with both intervals spanning zero. Its reuse of 72 #359 replies limits its independent evidence. On the fresh #369 seeds the two seen maps average +6.02 pp and the one prior holdout gives +6.48 pp. That split offers little evidence for a seen-map advantage. A future test with the clearest interpretation would replace part of the Arena2 exposure with diverse training layouts while holding the game budget, ordered matchups, seats, opponent, optimizer and v38 initializer fixed. The prediction is a gain relative to stock on layouts held out from both training and selection. Score each layout and the pooled gain, with contemporaneous stock PPO and v38 comparators. The existing evidence leaves the causal effect of training-map diversity open. A 25% v38 opponent mixture already gave only +0.93 pp versus pure Astra on its own holdouts. [Exposure and transfer](../ppo_transfer_20261115/REPORT.md) · [#306 independent holdouts](../ppo_terminal_return_20261109/REPORT.md) · [Opponent-mixture trial](../ppo_opponent_acceptance_20261115/REPORT.md)
2. **Decision quality has a measurable local opportunity and an unknown aggregate payoff.** In 17 exact restored states, substituting the v38-preferred retained action once improved one game, worsened three and tied 13. All four changes came from one training history. The net effect was −5.88 pp [−25.49, +11.76]. The sample contains no omitted actions. A particular omitted action class could matter if it is both frequent and changes paired official outcomes across histories. Witnesses of legal alternatives establish availability alone. An earlier expanded-support trial increased candidate use with an equal-wall strength interval spanning zero. That makes broadening every candidate list a poor first intervention. [Matched continuations](../ppo_action_headroom_20261115/REPORT.md) · [Expanded-support trial](../ppo_roadmap_acceptance_20261108/REPORT.md)
3. **Optimizer delivery is a real limitation with a failed score remedy.** The KL check stopped 545 of 546 archived batches. Halving the Adam rate increased visits per target from 1.258 to 1.981 and from 1.368 to 2.149 in two fresh paired pilots. Their official scores moved +6.25 and −9.38 pp. The pooled half-minus-stock change was −1.56 pp [−14.58, +11.98]. A larger visit count alone is a poor criterion for adopting an optimizer change. The prespecified gate ended the half-rate intervention at the pilot. [Archive audit](../ppo_diagnosis_20261115/REPORT.md) · [Paired online pilot](../ppo_lr_pilot_20261115/REPORT.md)
4. **The diagnostics give low priority to broad loss, critic or exploration changes.** Exact replay on 768 decisions reproduced trainer log probabilities within 6.15e−6. Two endpoint critics overpredicted realized outcomes, while the third beat the leave-one-game-out constant. GAE and realized-return advantage signs agreed on 87.3–96.6% of equal-game rows by policy and map, and equal-turn weighting reduced mean gradient alignment in all three histories. Matching policy KL across loss ablations gave inconsistent actor/critic directions and negligible pooled positive-action log-probability change from dropping entropy. Switching from greedy to sampled play shifted the PPO-over-BC advantage by −14.20 pp [−27.47, +0.93], below the prespecified +5 pp sampling-advantage threshold at the upper bound. None of these routes supplied a reproducible score intervention. The conditional quality of actions rarely represented in trajectories remains an open question. [Replay and credit](../ppo_diag_capture_20261115/REPORT.md) · [Loss attribution](../ppo_loss_attribution_20261115/REPORT.md) · [Selector experiment](../ppo_mode_interaction_result_20261115/REPORT.md)

The roadmap's one optimizer pilot reached its stopping rule. Its confirmation budget remains unreleased. A future repair would need at least +10 pp over v38 and +5 pp over contemporaneous stock PPO on independent layouts, with both paired lower bounds above zero. The fixed-checkpoint replication measures only the PPO–v38 contrast. The possible payoff from changing training-map exposure remains unknown.

## Reproduction and provenance

The original six roster blocks (0, 8, 12, 16, 24, 27) each received two fresh combat seeds on each of the three maps. Both learner seats and all four roles shared each seed. The 10,000 crossed draws used RNG seed 2026111753, resampling paired histories and six roster clusters within each fixed map. Each cluster kept both combat seeds and both seats together. The scorer averaged maps equally. The independent standard-library recount verified the full design, official winners and caps, all 12 tallies and all four pooled or map intervals. Recounting the comparisons involved the same 72 v38 games across the three contrasts.

The run used eight workers, zero optimizer updates, and 919.874 seconds of collection. Launch through scoring took 921.704 seconds of its 2,700-second budget. All terminal replies were fault-free. No confirmation or training run was launched. The archive contains the frozen and executed schedules, runtime and policy bindings, start and exit records, throughput and raw replies. [Raw evidence archive](raw-metadata.tar.gz) · [Score by role and map](score.json) · [Independent recount](recount.json)

| Item | Commit or SHA-256 |
| --- | --- |
| Pinned #306 evaluator source | `68fbf6b0b087b196526c674f28baffbfae3eb8c4` |
| Lite extension | `56dd77140411db987377d6de4ffbf562da4d0e5c76bc16d34780da67e60e5ae4` |
| Frozen training rules | `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17` |
| Astra package | `2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933` |
| [#359 identity manifest with all four checkpoints and exported weights](../ppo_mode_interaction_20261115/mode-launch.json) | `d50730235e9627d15c2eb11240ba6bd40a4b0c4d678cba8fecccbc1067c4aba5` |
| Evaluation adapter commit / Git archive | `76832850385de6703593c318fd38e83089420f43` / `9f04a22a328de9a441052174bb9e1ec41fd653eb6391618e3770329523f47150` |
| Preflight / frozen schedule | `704bce2ad1381eb1ae2d77a8fa9bacf96770f9275b50c388026bb5295f627ff9` / `9f32aab2112ad219bad9ac059f6c59b9f06191f4e7a2f4b9215fc416e1958fb7` |
| Review adapter commit / Git archive | `721df141a1c01cbe29e0aadeef31ed92cfe76f62` / `64df22ff63d001e9454e80c354c3696fcf0b6015b11762b9259c26e796f00482` |
| Raw metadata archive | `95be671325e30ef6ecc0dd07da77a42e8ef76978bb6064a0f1ffa241079f3679` |

Ubuntu used the following commands from the extracted evaluation archive. To reproduce the audit alone, run the last command alongside the archived files with Python 3.10 or later.

```bash
d=/home/tongshu/acceptance/ppo369-20261127-zohH3i
cd "$d"
adapter=verification/ppo_greedy_replication_20261127/evaluate.sh
bash "$adapter" freeze "$d/panel"
bash "$adapter" run "$d/panel" 704bce2ad1381eb1ae2d77a8fa9bacf96770f9275b50c388026bb5295f627ff9
# From the evidence directory, score the recorded replies without running games.
python3 audit.py raw-metadata.tar.gz
```
