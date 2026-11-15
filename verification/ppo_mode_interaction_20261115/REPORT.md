# PPO sampled versus greedy mode audit and frozen panel

Ubuntu cpuServer, 2026-11-15. [#359](https://github.com/t66sun/wesnothLearning/issues/359) · [#352](https://github.com/t66sun/wesnothLearning/issues/352)

## Archived mode evidence

The three #306 PPO checkpoints were less concentrated than v38 on their respective archived sampled trajectories. A sampled choice differed from the same policy’s greedy choice in **201/576** PPO probes (34.90%) and **35/192** v38 probes (18.23%). In 172 of the 201 PPO disagreements, both choices belonged to the same action type. The largest PPO–BC difference in within-policy disagreement was in turns 6–15. Running all four checkpoints on identical public v38 rows also gave 48, 58 and 53 PPO greedy choices different from v38 out of 192 per history.

The existing 96 sampled games gave PPO 31.48% and v38 34.72%, a paired **−3.24 pp** contrast with 95% interval [−16.67, +9.72] on this sampled block set. The action distribution and sampled scores leave the matched mode interaction open. The same-cohort #349 greedy panel used different combat seeds. The join checked 16 historical score schedules with 5,984 jobs from #227, #272, #306, #322, #349 and the online step-size pilot, with zero overlapping combat seeds. The 96 sampled captures are the available exact replies. [Archive schedule join](archive-join.json) · [Prior sampled score recount](../ppo_diag_capture_20261115/REPORT.md)

| Role | Archived sampled W/D/L | Official sampled score | Entropy, nats | Top-two logit margin | Sampled differs from own greedy | Greedy differs from v38 on v38 rows |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| v38 BC | 6/7/11 (7 caps) | 34.72% | 0.477 | 4.792 | 35/192 | 0/192 |
| 202611081 | 6/4/14 (4 caps) | 30.56% | 1.187 | 1.827 | 71/192 | 48/192 |
| 202611082 | 6/6/12 (6 caps) | 33.33% | 1.056 | 1.977 | 65/192 | 58/192 |
| 202611083 | 5/7/12 (7 caps) | 30.56% | 0.931 | 2.388 | 65/192 | 53/192 |

The audit used the same eight chronological visible-state probes per game and replayed the production float64 model with the original recurrent prefixes and candidate order. The maximum absolute chosen-action log-probability error was **1.04e−6** over 768 rows. Margin excludes forced moves. Entropy and disagreement use equal game weight within each turn band. PPO columns average the three history means. The own-policy rows are sampled from each role’s own trajectories. The last column above uses the fixed v38 observations and prefixes for all four roles.

| Learner turn | v38 entropy | PPO entropy | v38 margin | PPO margin | v38 sampling disagreement | PPO sampling disagreement |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 01-05 | 0.238 | 0.490 | 6.404 | 3.148 | 11.46% | 12.38% |
| 06-15 | 0.579 | 1.242 | 4.022 | 1.544 | 22.22% | 41.97% |
| 16-30 | 0.497 | 1.116 | 3.790 | 1.722 | 20.15% | 38.38% |

The action strata were fixed before replay. Combat combines attack and move-attack. Probability mass and greedy shares are measured on identical archived rows within each role. Per-turn strata and individual replay probes are in the archived output.

| Action type | v38 sampled mass | v38 greedy share | PPO sampled mass | PPO greedy share |
| --- | ---: | ---: | ---: | ---: |
| end_turn | 18.14% | 18.75% | 16.27% | 16.49% |
| recruit | 20.77% | 20.83% | 18.56% | 18.75% |
| movement | 28.72% | 28.65% | 33.43% | 32.29% |
| combat | 32.37% | 31.77% | 31.74% | 32.47% |

## Frozen paired panel awaiting authorization

Use the same four weight sets, three physical Lite layouts, full-candidate learner path, frozen Astra and official 30-round task. Every scenario uses both learner seats. Compare exactly the stock categorical sampler and first-index argmax on the legal candidate order. The four greedy exports are copies of the sampled addons and tensor files with only the selection mode in `lua/config.lua` changed. New jobs keep the same learner settings and omit only the terminal shard write. Their official replies are the only new game evidence.

| Block | Ordered factions | The Freelands combat seed | Weldyn Channel combat seed | Fallenstar Lake combat seed | Sampled games |
| --- | --- | ---: | ---: | ---: | --- |
| 0 | Drakes / Knalgan Alliance | 2026111740 | 2026111744 | 2026111748 | Reused |
| 8 | Knalgan Alliance / Rebels | 2026111741 | 2026111745 | 2026111749 | Reused |
| 12 | Loyalists / Northerners | 2026111870 | 2026111872 | 2026111874 | New |
| 16 | Northerners / Knalgan Alliance | 2026111742 | 2026111746 | 2026111750 | Reused |
| 24 | Rebels / Undead | 2026111743 | 2026111747 | 2026111751 | Reused |
| 27 | Undead / Loyalists | 2026111871 | 2026111873 | 2026111875 | New |

The two new faction pairs give each faction one first roster position across the six blocks. The six added seeds were checked against the historical score schedules and both #306 and #322 rollout schedules. The learner sampling seed is combat seed plus 100003 times the learner seat. Each map-by-block binding shares combat seed, ordered factions, scorer and physical board across modes and weights. Both seats stay in one resampling block.

| Work | Games |
| --- | ---: |
| Archived sampled replies reused by exact identity | 96 |
| New sampled | 48 |
| New greedy | 144 |
| Total new | **192** |
| Complete matrix | **288** |

Allow **30 active cpuServer minutes**, with eight workers and caps of five minutes for launch checks, 20 minutes for games and five minutes for recount. Training and optimizer updates are zero. The three independent confirmation layouts stay outside this panel.

Require exactly one valid reply for each of 288 cells, zero faults and terminal official score under `official-score-30-v1`. Audit wins, draws, losses and round caps by map, history and mode. A broken identity, missing reply or time overrun leaves the panel incomplete. Estimate `(PPO−BC) sampled − (PPO−BC) greedy` using official 3/1/0, divided by three. Use 10,000 paired draws across within-map roster blocks and training histories, resampling both seats and all roles together and sharing the same v38 result. Report sampled minus greedy by role and the interaction by history, map and pooled.

A PPO-specific gap earns a follow-on causal test if the pooled interaction is at least **+5 pp**, its paired 95% lower bound is above zero, at least two PPO histories have positive interactions, and pooled PPO beats v38 in sampled mode. A 95% upper bound below **+5 pp** excludes the prespecified actionable gap within this matrix. Other results are inconclusive at this precision. The 5 pp threshold is the roadmap’s minimum incremental effect over stock PPO, applied here as a diagnostic effect size for the interaction.

## Evidence and release

The read-only action audit took 54.836 seconds. The 4.835-second Ubuntu freeze verified all 288 cells and reproduced the recorded first action for each role with the actual categorical selector. Maximum first-choice log-probability error was 4.44e−8. The no-game fixture also checked the sign and scale of the interaction. **Zero new games and zero updates** were observed. [Preflight](mode-preflight.json)

- Launch SHA-256 `d50730235e9627d15c2eb11240ba6bd40a4b0c4d678cba8fecccbc1067c4aba5`. Plain schedule SHA-256 `ea7a2468b53f6d78df1090fc7dc5a1a2d90b7e84c7cd13f183dc63d2ea9fe3ea`. [Launch manifest](mode-launch.json) · [Complete schedule](mode-schedule.json.gz)
- Read-only output SHA-256 `e0fa1c894e6a746e99a11028581bd3bf1d260daaf284b9d5b5b73f061226b4ff` before gzip. [Action audit](action-audit.json.gz) · [Replay code](actions.py)
- Code Git archive commit `af0b86f9819fddaf4ccb6f85397556e67af1e9b6` and tar SHA-256 `2b7c12713f74c364edc5a6720ad49e0a88a6986007e2a6e91ef786121c7b9068`. [Panel code](panel.py)

```bash
set -eu -o pipefail
base=/home/tongshu/acceptance
source="$base/ppo306_20261108_Miwoyq/source"
extension=/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension
audit=/home/tongshu/acceptance/ppo-mode-interaction-20261115-sgUXX6
python=/home/tongshu/venv/bin/python
export WESNOTH_RULES_DIR="$base/filters_compiled_20261103/data/rules/1.18.8-combat-filtered"
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTHONPATH="$source:$extension:$audit/verification/ppo_diag_capture_20261115:$audit/verification/ppo_diagnosis_20261115"
cd "$source"
# Execute only after separate authorization of this manifest digest.
timeout --signal=TERM --kill-after=5s 1795 "$python" -u \
    "$audit/verification/ppo_mode_interaction_20261115/panel.py" run "$audit/freeze" \
    d50730235e9627d15c2eb11240ba6bd40a4b0c4d678cba8fecccbc1067c4aba5
```
