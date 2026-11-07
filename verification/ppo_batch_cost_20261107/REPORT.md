# Frozen duel PPO batch costs

[PPO-A1 issue #270](https://github.com/t66sun/wesnothLearning/issues/270) under [roadmap #269](https://github.com/t66sun/wesnothLearning/issues/269), measured on Ubuntu on 2026-11-07.

## Result

With rehearsal held fixed, the 4→8 comparison reduced preparation per game from 3.09 s to 1.72 s (44.3%) and per fresh decision from 43.81 ms to 25.36 ms (42.1%). Whole measured batch time increased from 16.95 s to 22.83 s for preparation plus one fixed-weight epoch. Peak probe RSS rose from 811 to 874 MiB. Eight games remain a viable candidate for the paired A2 contract and the first authorized A3 batch. That batch will establish online collection and settlement cost. A3 owns the learning and score comparison.

## Information in the settled batches

The [#227 acceptance](../duel_ppo_acceptance_20261107/REPORT.md) already verified the completed jobs, budgets and semantic trajectory aliases. [This census](census.json.gz) joins its six ledgers and histories with the manifests, schedules, job logs, scheduler intervals and retained policy shard paths. It reuses the [#226 settlement accounting](../ppo_efficiency_20261106/census.py). Every settled batch has four eligible, scored games from four game families. The 636 game entries are exposure across arms, with matched scenario streams and aliases across cells. They include 602 natural finishes and 34 scored turn caps.

| Cell | Fresh games | Fresh decisions | Fresh windows | Scenario families | Committed visits | Rejected visits | KL stops / batches |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| a1 | 104 | 10,054 | 221 | 60 | 20,094 | 3,791 | 25 / 26 |
| b1 | 112 | 10,313 | 230 | 63 | 20,476 | 3,922 | 27 / 28 |
| b2 | 108 | 10,083 | 218 | 62 | 19,479 | 4,040 | 26 / 27 |
| a2 | 100 | 10,201 | 222 | 58 | 18,530 | 3,909 | 25 / 25 |
| a3 | 108 | 10,142 | 217 | 62 | 19,417 | 4,260 | 27 / 27 |
| b3 | 104 | 10,150 | 209 | 60 | 19,813 | 4,070 | 26 / 26 |
| Total | 636 | 60,943 | 1,317 | 63 distinct | 117,809 | 23,992 | 156 / 159 |

The 117,809 committed and 23,992 rejected decision visits span 2,522 and 539 window visits, respectively. Of 1,544 planned optimizer steps, 716 committed, 156 were evaluated and rejected by KL, and 672 went unattempted. Rejected decision visits were 16.92% of inspected visits. The 1,317 fresh windows contain correlated decisions within trajectories. Replaying those windows across epochs creates compute visits. Across the first batches specifically, the 24 game references reduce to 11 distinct semantic trajectories and four scenario families. The full census counts game-family and scenario exposure from indexes, with semantic deduplication for the independently audited first-batch cohort.

## Inputs and method

The timed historical-action CE batches are the first in run order, a1 batch 38, and the last, a3 batch 64. Their behavior weights come from the recorded PPO sampling exports. The 8-game case takes the first eight distinct semantic trajectories in #227's execution order, the four a1 games plus the four b2 games whose a2 counterparts are recorded aliases. All eight share the scored 30-turn duel task, BC v38 policy and frozen Astra opponent. This doubles distinct trajectories within the same four public scenario families. The later a3 weights stay separate.

The paired cases use the same a1 rehearsal corpus, production reader quota and seed. The added four games go only into the current-rollout side of the diagnostic. Their original job IDs collide across cells. The diagnostic gives their decoded rows a cell-qualified game ID in memory, so PPO target keys and GAE sequences remain separate. Each game's complete decoded history and terminal reward are retained. A real 8-game runner will also admit its new policy and DAgger shards to the rehearsal pool under the existing quota.

[The timer](timing.py) follows the post-#240 order of a single full rollout read, bounded rehearsal read, eligibility, both content identities, prepare validation, window setup and one complete fixed-weight epoch. It calls the [#226 fixed-weight epoch](../ppo_efficiency_20261106/probe.py) with CPU groups of four windows, 32-row microbatches and equal window weights. Historical rehearsal reader statistics, retained sources and exclusion counts are checked against the recorded runner. Rehearsal draws and epoch order use the #226 diagnostic seeds. Model digests match the recorded behavior weights after each pass. The [#240 once-only runner regression](../rollout_read_once_20261106/REPORT.md) already verified the actual runner boundary. Here each raw timing record has one full read and no preliminary-read phase.

Each case has a separate process with one Torch intra-op/inter-op thread, one full warmup and two measured repetitions, with ordinary OS cache reuse. Times are two-run means. Peak RSS is the process high-water mark including the warmup, setup and both repetitions. It covers this fixed-weight CPU probe. Optimizer state, exports, checkpoint I/O, collection, scheduler latency and validation are outside the timed batch. The same fixed-weight backward pass runs through all windows, so actual KL-dependent settlement and parameter movement require the original histories or a new authorized run.

## CPU timings

| Case | Distinct games / decisions / windows | Median / max raw prefix turns | Preparation, wall / CPU s | Fixed epoch, wall / CPU s | Prep + epoch, wall / CPU s | Peak RSS, MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| [First CE, a1 batch 38](first.json) | 4 / 282 / 8 | 6 / 14 | 12.35 / 12.35 | 4.60 / 4.60 | 16.95 / 16.95 | 811 |
| [Last CE, a3 batch 64](last.json) | 4 / 216 / 6 | 4 / 11 | 25.42 / 25.41 | 4.11 / 4.11 | 29.53 / 29.52 | 1,201 |
| [Paired shared-BC 8](paired8.json) | 8 / 543 / 16 | 6 / 14 | 13.77 / 13.77 | 9.06 / 9.06 | 22.83 / 22.82 | 874 |

| Component, wall s unless indicated | First CE | Last CE | Paired 8 |
| --- | ---: | ---: | ---: |
| Full rollout read | 0.45 | 0.35 | 0.88 |
| Rehearsal read | 6.41 | 17.12 | 6.43 |
| Rollout content identity | 0.71 | 0.55 | 1.39 |
| Rehearsal content identity | 3.29 | 5.26 | 3.35 |
| Prepare validation | 1.50 | 2.13 | 1.73 |
| PPO forward / rehearsal forward / joint backward | 0.41 / 0.72 / 3.37 | 0.31 / 0.96 / 2.77 | 0.80 / 1.37 / 6.72 |
| Preparation per game, s | 3.09 | 6.35 | 1.72 |
| Preparation per fresh decision, ms | 43.81 | 117.67 | 25.36 |

The same rehearsal reader and hash take 9.70 s and 9.77 s in the paired cases, while current-rollout reading and hashing rise from 1.15 s to 2.27 s. The full fixed-weight epoch nearly doubles, following the doubling of windows and the rehearsal forward/backward work performed for those windows. In the late real batch, the rehearsal read and hash alone cost 22.38 s. Rehearsal returned 2,048 rows from 111 decoded families there versus 1,306 rows from 37 decoded families early, even though the late current-rollout batch had fewer decisions and shorter prefixes.

The [#226 old-task diagnosis](../ppo_efficiency_20261106/REPORT.md) measured 14.16–38.24 s of preparation and 5.79–22.24 s per fixed-weight epoch for 60-turn duel/team workloads with a different rehearsal history and terminal semantics. Its preparation includes the bounded preliminary read subsequently removed by #240. The [post-#240 paired evidence](../rollout_read_once_20261106/REPORT.md) measured 13.13–34.82 s of single-read preparation on those old inputs. This 30-turn probe measures the remaining preparation directly and uses its own stage totals.

## A2 and A3 budget

- **A2 first integrated observation.** With the same early rehearsal pool, preparation plus one to four complete fixed-weight epochs budgets 17–31 s for four games and 23–50 s for eight. For a sampling reference, each four-job source group in the synthetic pair spanned about 9.6 s on the recorded scheduler. Across all historical CE batches, four-job spans ranged from 5.4 to 30.7 s. An 8-worker start offers one slot per game for an 8-game batch, with contention and straggler costs still to measure. Use A3's first actual 8-game batch to record collection span, preparation/update wall time and trainer/worker memory with the unchanged optimizer and pending-train path. The 874 MiB probe measures process RSS, which differs from the trainer's virtual-address limit.
- **A3 admission budget.** The three historical CE arms spent 4,550 s for 30,397 fresh decisions in 312 games over 78 batches, or 58.34 s per batch and 97.43 decisions per game. At that density the proposed 10k/30k checkpoints would take about 26/77 complete 4-game batches or 13/39 complete 8-game batches. With 85 minutes of admission and five minutes for settlement, 30k therefore budgets about 66 s per 4-game batch or 131 s per 8-game batch, inclusive of collection and trainer overhead. At historical CE throughput, 30k corresponds to about 75 minutes. The 8-game ceiling is a planning threshold under the same density assumption. The early synthetic cases use a small rehearsal pool, and its read and hash grow by 12.68 s in the late real case. Retain that headroom and use actual settled endpoints at the frozen wall limit. Count each arm's own fresh decisions, rejected visits and official score at the prespecified endpoints.

## Reproduction and identities

| Input | Identity |
| --- | --- |
| Ubuntu acceptance source | `24fe25c786b7ea91a6ede375435b3baa32d8a36d` |
| Source archive SHA-256 | `a0a42f8b40d617c12cd9a86c325f3c887cde6f6aace5d1486a93821a18a5f0e7` |
| Ubuntu acceptance directory | `/home/tongshu/acceptance/ppo_batch_cost_20261107_24fe25c` |
| #227 production / launcher | `eadad5d` / `43325b33696de4db8ee546e1c6bedb7230a73b37` |
| Frozen rules SHA-256 | `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17` |
| Fixed Astra package SHA-256 | `2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933` |
| Shared BC behavior weights SHA-256 | `d9d694f04d4179a5c65bbc29307a8e425a245d650d47f55a36ec04abeb206801` |
| Host | [Ubuntu Intel i3-13100F, 4 cores / 8 logical CPUs](host.txt) |

[The census](census.json.gz) records the selected schedule, job and shard indexes. The census is compressed and decompresses to the original JSON. The three raw timing records preserve wall and CPU observations, read statistics, row counts, history lengths and source digests. Existing frozen files are read in place. The execution uses no new games, optimizer updates or training artifacts.

From the committed source archive extracted into a fresh Ubuntu directory:

```sh
python=/home/tongshu/venv/bin/python
run=/home/tongshu/acceptance/duel_comparison_20261106_43325b3/source/runs/duel_ppo_comparison_20261106
diag=verification/ppo_batch_cost_20261107
out=/path/to/new/evidence
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$PWD"
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

mkdir "$out"
"$python" "$diag/test_diagnostic.py" -v
"$python" "$diag/inventory.py" "$run" "$out/census.json"
for sample in first last paired8; do
    "$python" "$diag/timing.py" "$out/census.json" "$sample" "$out/$sample.json"
done
```

[The single trajectory isolation assertion](passing.txt) passed. The same command in a separate extracted copy, overlaid with only `timing.py` archived from mutation commit `f833a5d95d8507558f31a8f62356c307f825f2a7`, [failed at the expected duplicate PPO target key](reverted.txt). The mutation preserves the unqualified ID in place of the cell-qualified ID. Existing no-drop, window weighting and PPO settlement checks are reused through the production readers, the fixed-weight diagnostic and the recorded acceptance evidence.
