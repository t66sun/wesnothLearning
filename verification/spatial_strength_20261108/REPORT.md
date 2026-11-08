# PPO-C3 public spatial information and duel strength

C1+C2 restore the two public distinctions isolated by #229. All three trained C wall checkpoints respond to both witness pairs, with small probability shifts and the same top-ranked action within each pair. On equal PPO wall budgets, C scored **+0.74 percentage points** over base on Hamlets and **+2.78 points** on Silverhead Crossing. Both paired 95% intervals cross zero, as do both wall contrasts against C's own BC. The formal result leaves the strength benefit unestablished. C remains experimental. [#278](https://github.com/t66sun/wesnothLearning/issues/278), [#269](https://github.com/t66sun/wesnothLearning/issues/269)

## Scope and implementation evidence

The experiment compared base's 16×16 bin means and global mean pooling with C's native public grid and position-weighted readout. Both arms used `work-12000-v8` candidate retention, four games per PPO batch, eight game workers, one trainer thread, `official-score-30-v1`, fixed Astra, historical-action CE and the same KL 0.02 gate. The common source freezes the optimizer, rewards, scenario stream and evaluation design. C includes only the two accepted spatial changes. [Frozen design and inputs](../ppo_batch_comparison_20261107/PROTOCOL.md)

- C1 distinguishes the original hill-location collision with a nonzero position coefficient. Reverting to mean pooling fails that assertion. The 30 focused Ubuntu checks cover identity initialization, gradients, recovery of an interrupted weights-only child and export. Saved and reloaded position weights gave maximum Python/Lua error `5.69e-14` on 220 replay decisions. [Accepted C1 report](https://github.com/t66sun/wesnothLearning/blob/64413c72208b7cc9fd944f699558de2b83123b6b/verification/spatial_position_readout_20261107/REPORT.md)
- C2 recovers the 24-step and unreachable public route distinction, keeps the public visibility controls and masks padding in mixed-size batches. Restoring bin averaging and removing the first convolution mask fail their respective assertions. The 42 focused Ubuntu checks include mixed-board batching, schema checks, checkpoint recovery and export. Replaying 44 fixture rows, including a 40-write prefix, gave maximum Python/Lua error `2.13e-14`. [Accepted C2 report](https://github.com/t66sun/wesnothLearning/blob/2e6be1838b46423b74eaf7d91932f5e0914ac047/verification/spatial_native_grid_20261107/REPORT.md)

## BC qualification and first live batches

Both arms used the same frozen original v38 actor initializer and BC seed `202611060`. C's weights-only path transferred compatible actor tensors, initialized the added readout to `[I,0,0]`, reset the critic and Adam, and acquired fresh rows under feature/row schemas 7/8. Base reused the accepted #227 v38 BC endpoint under schemas 5/6. The common qualification work allowance was 300 valid teacher games with a 150-minute cap. Each PPO seed loaded its arm's qualified v38 actor and critic with Adam reset. [BC qualification design](../ppo_batch_comparison_20261107/QUALIFICATION.md), [Historical base](../duel_ppo_acceptance_20261107/REPORT.md)

| BC qualification | Base | C |
| --- | ---: | ---: |
| Valid teacher games | 300 historical | 300 fresh |
| Distinct scenario families at gate | 32 | 33 |
| Qualification wall seconds | 3,859.09 historical | 3,959.08 |
| Teacher action coverage, all | 29,693/32,779 (90.59%) | 29,693/32,779 (90.59%) |
| Coverage, recruit / move / attack | 87.73% / 91.73% / 87.06% | 87.73% / 91.73% / 87.06% |
| Held-out imitation top-1, 925 labels | 74.70% | 74.38% |
| Held-out imitation cross-entropy | 1.56594 | 1.92098 |
| v38 gate | Passed | Passed |

The gate's uniform reference was 2.93% top-1 and 3.55509 cross-entropy for each arm. The opening check remained nonblocking in both. Each BC endpoint had 304 retained training shards, including 300 teacher shards, with no Silverhead overlap. Base's historical BC cost is included when comparing total work across routes and was already paid at launch.

- **First C BC batch.** `bc-batch-000000.json` scheduled eight Astra teacher games. All eight jobs completed with training-eligible shards. The first stored teacher row in `teacher-00000-duel-t0.jsonl.gz` has schema 8 and a 15×13 native grid. The BC state records 722 sampled training rows and 116 validation rows for this update, with 16 optimizer updates and 2,801 decision visits. The first trained BC validation export, `policies/v000010-greedy/export.json`, carries feature 7 and the `native_cells` / `mean_xy` architecture.
- **First C PPO batch.** Seed `202611071` loaded the qualified BC checkpoint, exported v38, and settled four complete games at ordinals 0–3 from `ppo-batch-000038.json`. The first retained rollout uses schema 8. The first update settled 447 fresh targets, committed three optimizer steps and stopped on the existing KL gate. Its input weights hash `b69187ab…e550` matches the C BC endpoint. The next rollout export carries v39 with the same feature and architecture identities. All three C seeds completed with recorded final checkpoints and both fresh-decision checkpoints.
- These are observations of the live write/read, branch and export paths. Forced interruption and recovery are covered by the accepted implementation checks above. The formal run reached its checkpoints without an injected interruption.

| Checkpoint or export | SHA-256 |
| --- | --- |
| Common actor initializer | `05908d7f972148ccc7b39b8df0cc00435e2176861654a632de44c379b94953ab` |
| Base v38 BC checkpoint | `8fc61bbb0be5c2ad8d2ec5b56760ce3dbfa08eed008c490e9b2233624ea91ebe` |
| C v38 BC checkpoint | `e63ae1b2dff468de3426036882e692612b8e38105d04efb272c5db9e118cfa0e` |
| C v10 BC export manifest | `2051d48be412784154f5b18e48185a67b93c2e287e980790b5fa8a0267155ae9` |
| C seed 071 PPO v38 → v39 export manifests | `b4784f16c4e941d38c540c6a9418068719a57dfa96de94ab69d9001bfa3f8de3` → `9158c2fd8b114f7cd49ae2d88343558bbd021697290a44e50d6c73cb43a6e549` |

## Official duel scores

Scores are percentages of the official three-point maximum, averaged over seat rotations and scenario blocks. The common PPO budget was 90 minutes per cell, including initialization, with new batches admitted for 85 minutes and complete batches settled before the hard limit. The wall role is the last complete checkpoint within that budget. Fresh-decision roles use the first complete crossing of 10,000 or 30,000 eligible fresh targets.

| Panel | Base BC | C BC | Base wall, seeds 071 / 072 / 073 | C wall, seeds 071 / 072 / 073 | Wall mean, base → C |
| --- | ---: | ---: | ---: | ---: | ---: |
| Hamlets validation | 41.11 | 50.00 | 47.78 / 53.33 / 26.67 | 47.78 / 47.78 / 34.44 | 42.59 → 43.33 |
| Silverhead holdout | 35.00 | 42.22 | 43.89 / 45.00 / 38.33 | 36.11 / 48.89 / 50.56 | 42.41 → 45.19 |

| Panel | Paired contrast | 071 / 072 / 073, pp | Mean, pp | 95% interval, pp |
| --- | --- | ---: | ---: | ---: |
| Hamlets wall | C − base | 0.00 / −5.56 / +7.78 | +0.74 | [−12.59, +16.30] |
| Hamlets wall | C − C BC | −2.22 / −2.22 / −15.56 | −6.67 | [−24.07, +8.89] |
| Hamlets wall | Base − base BC | +6.67 / +12.22 / −14.44 | +1.48 | [−19.26, +21.48] |
| Silverhead wall | C − base | −7.78 / +3.89 / +12.22 | +2.78 | [−10.74, +16.11] |
| Silverhead wall | C − C BC | −6.11 / +6.67 / +8.33 | +2.96 | [−11.11, +17.22] |
| Silverhead wall | Base − base BC | +8.89 / +10.00 / +3.33 | +7.41 | [−4.07, +19.81] |

| Hamlets secondary role | Base score, 071 / 072 / 073 | C score, 071 / 072 / 073 | C − base, mean [95% interval] pp | C − C BC, mean [95% interval] pp |
| --- | ---: | ---: | ---: | ---: |
| First ≥10k | 27.78 / 58.33 / 61.11 | 61.11 / 41.67 / 33.33 | −3.70 [−38.89, +33.33] | −12.96 [−38.89, +13.89] |
| First ≥30k | 32.22 / 48.89 / 40.00 | 35.56 / 51.11 / 43.33 | +2.96 [−15.19, +22.22] | −6.67 [−23.33, +11.11] |
| Production-selected | 44.44 / 42.22 / 36.67 | 27.78 / 28.89 / 23.33 | −14.44 [−31.48, +1.85] | −23.33 [−39.63, −8.52] |

The small 10k panel used six frozen Hamlets blocks, where base BC and C BC scored 52.78 and 58.33. The full validation used 15 blocks. Silverhead used 30 ordered faction blocks on one physical held-out Lite duel map. Each block has both seat rotations. Each full wall role therefore had 30 actual games on Hamlets or 60 on Silverhead. Across the whole comparison, Hamlets ran 1,314 unique games after alias reuse (336 under C, 642 shared by base and A, and 336 under B). Silverhead ran 900 (240 under C, 420 shared by base and A, and 240 under B). Both panels had complete score coverage. Intervals use the frozen paired crossed bootstrap with 10,000 draws, seed `202611079`, and matching training seeds and scenario blocks within the map. The counts describe actual games. The bootstrap respects the paired design and Silverhead supports inference on a single map.

C's BC started ahead in both panels. Its small final base-relative score difference came with a lower own-BC change than base in both. The selected Hamlets weights scored below C's own BC, while the preregistered wall comparison remains inconclusive. Hamlets produced no nomination under the frozen rule requiring positive lower bounds for both equal-wall contrasts. The conditional native strength and latency panel did not run. [Shared run and raw panel archive](../ppo_roadmap_acceptance_20261108/REPORT.md)

## Training and decision cost

| Arm / seed | Wall seconds | First ≥10k | First ≥30k | Final fresh targets | Settled batches / games | Fresh targets per hour | Trainer peak RSS MB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Base 071 | 5,151.53 | 10,111 | 30,068 | 33,463 | 82 / 328 | 23,385 | 1,368 |
| C 071 | 5,127.36 | 10,569 | 30,326 | 33,127 | 80 / 320 | 23,259 | 1,480 |
| Base 072 | 5,120.90 | 10,110 | 30,493 | 33,828 | 82 / 328 | 23,781 | 1,320 |
| C 072 | 5,178.76 | 10,637 | 30,076 | 33,799 | 81 / 324 | 23,495 | 1,496 |
| Base 073 | 5,122.07 | 10,353 | 30,033 | 32,630 | 86 / 344 | 22,934 | 1,383 |
| C 073 | 5,173.11 | 10,126 | 30,422 | 33,330 | 81 / 324 | 23,195 | 1,557 |

| Totals over three PPO cells | Base | C |
| --- | ---: | ---: |
| PPO stage wall seconds | 15,394.50 | 15,479.22 |
| PPO plus corresponding BC wall seconds | 19,253.59 | 19,438.31 |
| Rollout wall seconds | 3,668.89 | 4,056.60 |
| Preparation wall seconds, including reads and batch assembly | 6,430.23 | 5,945.04 |
| Training wall seconds, excluding preparation | 4,549.15 | 4,728.61 |
| Due validation wall seconds | 673.87 | 673.10 |
| Committed / rejected optimizer steps | 1,179 / 247 | 1,120 / 240 |
| Fresh targets per PPO wall hour | 23,367 | 23,317 |
| Compressed rehearsal bytes accounted across reads | 24,233,888,871 | 23,624,426,373 |
| Retained teacher gzip bytes, 300 shards | 313,608,369 | 346,272,290 |
| Retained PPO rollout gzip bytes, including DAgger shards | 1,921,648,109 | 2,161,278,542 |

The sums exclude shared evaluation panels and source staging. These are measured costs of the full paths with different realized trajectories. C used 10.4% more disk for the teacher corpus and 12.5% more for PPO rollout shards. It spent 10.6% more rollout time and 3.9% more training time, while its total preparation time was lower. Aggregate fresh decisions per PPO wall hour were similar. In the first BC update, both arms sampled 722 training rows. Reported compressed bytes for the training read were 8,038,255 on base and 9,065,894 on C. The C2 fixed-state comparison isolates indexed-read time more directly. C1 → C2 was 1.57 → 1.39 ms on arena2, 1.62 → 1.50 ms on Ruined Passage and 14.31 → 16.85 ms for the 40-write history fixture. On Ruined Passage, compressed sample bytes grew 20.7%, mean Lite decision was 14.87 → 15.74 ms and the prepared Lua decision was 106.52 → 218.17 ms. The fixture Lua path starts with prepared public inputs and committed memory. [C2 fixed-state measurements](https://github.com/t66sun/wesnothLearning/blob/2e6be1838b46423b74eaf7d91932f5e0914ac047/verification/spatial_native_grid_20261107/REPORT.md)

| Silverhead learner role | Base p95 ms (decisions) | C p95 ms (decisions) |
| --- | ---: | ---: |
| BC | 59.13 (11,738) | 60.71 (12,031) |
| Wall 071 | 58.44 (11,803) | 60.69 (11,781) |
| Wall 072 | 58.44 (11,044) | 62.31 (11,319) |
| Wall 073 | 58.07 (10,029) | 61.42 (11,352) |

The official holdout measures nearest-rank p95 from public Lite observation and candidate construction through policy choice, including feature encoding and inference. Samples come from learner turns in completed fault-free games. [Timing contract](../ppo_batch_comparison_20261107/DECISION_TIMING.md)

## Trained policy response on the original public states

The offline probe scored only the two original #229 public pairs, with each arm's three recorded wall checkpoints. The 32×16 route pair changes from a 24-step ground route to unreachable. The 16×16 hill pair moves the same hill from (8,5) to (8,11). For each pair the probe reuses the original specifications and synthetic rules. It checks that both arms see all seven identical legal candidates in the same order, including identical local action features, entity rows and other non-board inputs. Only public observation is constructed. Inference uses empty history and float64 arithmetic with the saved model parameters. [Original fixtures](../representation_information_20261106/REPORT.md)

All baseline models produce identical logits and distributions within each pair. The table reports C's maximum absolute change across action log probabilities, total variation distance, and change in the log odds of recruiting Ghost rather than Fighter, summing over the three slots for each unit type. Positive values move relative mass toward Ghost. Directions are closed minus open for the route and farther minus nearer for the hill.

| Pair / seed | Max abs change in log probability | Total variation | Ghost vs Fighter log-odds change | Top-ranked action on both sides |
| --- | ---: | ---: | ---: | --- |
| Route 071 | 2.69e−4 | 1.12e−5 | +3.46e−5 | Ghost (3,7) |
| Route 072 | 3.04e−4 | 8.74e−5 | +3.53e−4 | Fighter (4,8) |
| Route 073 | 3.10e−4 | 1.73e−5 | −9.93e−5 | Ghost (4,8) |
| Hill 071 | 3.27e−5 | 4.98e−6 | −2.34e−5 | Fighter (3,5) |
| Hill 072 | 2.09e−5 | 1.13e−6 | −1.50e−5 | Fighter (3,5) |
| Hill 073 | 4.65e−5 | 1.57e−6 | −1.30e−5 | Ghost (3,5) |

The trained C policies use the recovered public information weakly on these examples. Closing the route moves the relative Ghost odds in different directions across seeds. These synthetic states have no independently labelled best action, so the measured preference changes supply no accuracy estimate or causal account of formal scores. The probe ran 24 forward passes with no moves, new games, collection or optimizer steps. [Base outputs](base.json), [C outputs](c.json)

## Reproduction and source identity

The formal run completed on Ubuntu at `/home/tongshu/acceptance/ppo269_shared_20261107_gzzXd6`. Its launcher recorded 2026-11-07 15:29:11 UTC through 2026-11-08 11:55:45 UTC and exit 0. The shared archive retains the original commands, launch manifest, cell ledgers, gates, role hashes and game records. [Shared evidence](../ppo_roadmap_acceptance_20261108/REPORT.md)

| Item | Commit or SHA-256 |
| --- | --- |
| Formal driver source | `3cfb191640b693f19ce417f047d4596919df4175` |
| Formal base source | `07db85b8ba4def9bfebc7b42fe4c7bec0c4fd1b0` |
| Formal C source | `2e6be1838b46423b74eaf7d91932f5e0914ac047` |
| Launch manifest | `35691d7b2e21c73a5cfee79aa97da0f39c75841811999076d4b46c8ee8c7dd49` |
| Frozen rules | `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17` |
| Frozen Astra package | `2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933` |
| Base/C Lite extension | `56dd77140411db987377d6de4ffbf562da4d0e5c76bc16d34780da67e60e5ae4` |
| Original public fixtures | `cb6cabda2f2a47b9deda38628e8c6959601d9887f711e04d28482089ea1ba74a` |
| Probe source | `236dfc3a02f08a1de4787d11d8f877f6c6b61f10` |
| Probe archive | `80ea25ad9dc26ddcdc436b3c468c2854461f9ccce751fca6b763e32490ec5372` |
| Base and C probe outputs | `bfcecb706197104cabd2d1b93abb0ad88ca9fc6bfac1017ae4ac7b8ad4e5779e` / `a8bee40a2bbd618060d43aab36c431daa3f37857ea1b6f7944db40149a1901bb` |

The probe archive was made with `git archive --format=tar.gz 236dfc3a02f08a1de4787d11d8f877f6c6b61f10 verification/spatial_strength_20261108/probe.py` and extracted in the dated Ubuntu directory below. The formal run's two source trees, modules and final checkpoints were opened read-only. For a repeat, redirect output into a fresh directory. The frozen rules setting supplies the original feature vocabulary.

```bash
formal=/home/tongshu/acceptance/ppo269_shared_20261107_gzzXd6
probe=/home/tongshu/acceptance/spatial_strength_20261108_VKZTkW
extension=/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

for arm in base c; do
  cd "$formal/$arm/source"
  PYTHONPATH="$PWD:$extension" /home/tongshu/venv/bin/python \
    "$probe/verification/spatial_strength_20261108/probe.py" "$formal" "$arm" > "$probe/$arm.json"
done
sha256sum "$probe"/{base,c}.json
```
