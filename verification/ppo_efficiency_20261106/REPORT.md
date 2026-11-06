# Frozen PPO cost and update efficiency

Issue: [#226](https://github.com/t66sun/wesnothLearning/issues/226), part of [#221](https://github.com/t66sun/wesnothLearning/issues/221). Date: 2026-11-06.

## Finding

The strongest measured throughput opportunity is the repeated data preparation around a small four-game batch. In six frozen batches, rehearsal reads took 5.80–17.05 seconds on average, content identities another 4.97–11.50 seconds, and validation 1.84–3.83 seconds before any PPO forward/backward work. A complete fixed-weight epoch took 5.79–22.24 seconds. These are isolated CPU measurements, not a decomposition of the original run's entire elapsed time.

The high KL-stop frequency does **not** mean 69–90% of computation was wasted. Completed duel/team batches discarded 7.45%/5.12% of their inspected decision visits at the rejected logical step. Another 1,959/2,057 planned steps were never attempted. They consumed no forward/backward computation. The current stop contract in [#56](https://github.com/t66sun/wesnothLearning/issues/56) remains intact.

Four fresh games still supply only four outcome trajectories, despite hundreds or thousands of correlated decisions and repeated epochs. The evidence supports improving fresh-information throughput and removing measured data-path overhead before enlarging the network or relaxing KL. It does not establish an end-to-end speedup or a strength gain. The objective and capability-retention findings remain owned by [#224](https://github.com/t66sun/wesnothLearning/issues/224), [#235](https://github.com/t66sun/wesnothLearning/issues/235), and [#225](https://github.com/t66sun/wesnothLearning/issues/225).

## Scope and identities

All execution was on Ubuntu through `ssh cpuServer`. No games, collection, training, optimizer construction/steps, checkpoint saves, or production changes were performed. Backward calls only populated transient gradients; model parameter digests were asserted unchanged after every measured epoch. No Windows tests were run.

| Item | Identity |
| --- | --- |
| Frozen run | `/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/runs/formal_30h_scratch` |
| Formal-run source | `d2e6da5fbd07396c0c4d13a6588f66e1796f80fd`, retained from the [original audit](../ppo_architecture_audit_20261106/REPORT.md) |
| Research branch base | `cc28f23ee7c681cf2dc59e1a556708de4de0f351` |
| Full census and forward/backward source | `9bf5e0fb320128375449f5c1300a28399e9f3dbd` |
| Final scripts, preliminary reads, two accounting tests | `0e73350a90c9f78caaefb70a4253f0cc9953b93a` |
| Main source archive SHA-256 | `a0a157161d70b3f9b8f53e07238e321b6c1eda4f0a88c4a0126399f89527d9f2` |
| Final source archive SHA-256 | `2353aa7e0b2ba7e13f325c431975e706544d1012d2511ec1d5e67a3cdef73917` |
| Ubuntu directories | `/home/tongshu/acceptance/ppo_efficiency_20261106_9bf5e0f`, `/home/tongshu/acceptance/ppo_efficiency_20261106_0e73350` |
| Runtime | Python 3.12.3; PyTorch 2.9.1+cpu; one intra-op/inter-op thread; OMP/MKL/OpenBLAS threads = 1 |
| Host | Intel i3-13100F, 4 cores / 8 logical CPUs; [before](host_before.txt), [after](host_after.txt) |

The final `census.py` and `probe.py` are byte-identical to the measured source. The final source adds `recorded_costs.py` and removes an unnecessary AST blacklist test. The frozen run, prior dated evidence, and production files remain unchanged. Log/schedule hashes are in [census.json](census.json); selected shard/model hashes are in [probe.json](probe.json) and [recorded_costs.json](recorded_costs.json). [SHA256SUMS](SHA256SUMS) identifies these new artifacts.

## Completed-run accounting

The census includes all **completed** PPO history entries. Team also has four later collected games whose batch was not settled; they appear in scheduler/corpus totals, not the completed-batch ledger.

| Quantity | Duel | Team 2v2 |
| --- | ---: | ---: |
| Completed PPO batches | 902 | 231 |
| Fresh games in those batches | 3,608 | 924 |
| Fresh eligible decisions | 386,593 | 341,940 |
| Distinct scenario-family IDs across those batches | 6 | 7 |
| Planned optimizer steps | 9,020 | 5,460 |
| Committed optimizer steps | 6,435 | 3,196 |
| Evaluated but rejected logical steps | 626 | 207 |
| Never-attempted planned steps | 1,959 | 2,057 |
| Inspected decision visits | 1,242,230 | 878,835 |
| Committed decision visits | 1,149,722 | 833,857 |
| Inspected but uncommitted decision visits | 92,508 | 44,978 |
| Uncommitted / inspected visits | 7.45% | 5.12% |
| Committed visits / fresh decisions | 2.974 | 2.439 |

The three step counts sum to planned steps; committed plus rejected visits sum to inspected visits. Every completed batch has four game families. Duel batches contain four distinct scenario-family IDs; team batches contain two to four. These IDs do not turn repeated states, correlated trajectories or repeated epochs into independent observations. The old run's total 6/7 scenario families are historical: the broader `map-seat-faction-v1` scheduler from [#223](https://github.com/t66sun/wesnothLearning/issues/223) was already merged before this research. Its learning effect has not yet been measured.

The accounting follows the real [PPO loop](../../learning/ppo.py): each selected window's actor/value/entropy and rehearsal forward/backward finish before the logical-batch KL check. A rejected step clears gradients and settles the batch; the remaining plan is not retried. The inspected-minus-committed interpretation here is limited to these completed history entries, whose ledger consistency checks passed. It is not a general rule for interrupted/resumed runs.

The run's rehearsal reader reports 90.227 GB (duel) and 23.218 GB (team) of compressed inputs admitted across PPO reads, including repeated reads of old files. Of 2,310,665 returned rehearsal targets, 1,151,209 were subsequently excluded because they came from the evaluation control. All retained rehearsal source identities in this run are historical policy. These are recorded reader volumes and target counts, not physical disk traffic or CPU time.

## What the scheduler can and cannot attribute

The scheduler spans 91,818.86 elapsed seconds. Completed worker jobs account for 332,849.14 summed worker-wall seconds, and at least one worker is active during 74,713.91 elapsed seconds. Eight-worker slot occupancy is therefore 45.31%; the union is 81.37% of the scheduler interval. Neither is CPU utilization. Simultaneous formats and jobs overlap, so phase unions cannot be added to obtain the run duration.

| Recorded worker activity | Jobs | Summed worker-wall seconds |
| --- | ---: | ---: |
| Duel PPO jobs | 3,608 | 49,208.74 |
| Team PPO jobs, including the later unsettled batch | 928 | 85,759.72 |
| All FFA worker activity | 2,084 | 98,761.24 |

FFA never entered PPO; its worker time is real competing work, not PPO optimizer cost. Full phase detail is in `census.json`. `state.history.elapsed_hours` is cumulative elapsed time at a completed update, not a trainer CPU timer. The original logs cannot separately recover simulation/execute, observation capture, policy inference, teacher planning, compression, export, checkpoint writing, or scheduler waiting. Subtracting candidate time from worker-wall time would leave all of these mixed together, not isolate the Rust simulation cost.

## Frozen CPU cost breakdown

The matrix was fixed before measuring: first, middle, and last completed batch for each PPO format. It contains 5,306 current-policy decisions from 24 games. For each sample the probe:

1. Loads its original rollout policy and the next rollout export; asserts their parameter digests equal the history's before/after digests.
2. Reconstructs the then-available rehearsal corpus, reads with the production limit/seed, and asserts **all** historical `reads.bc` fields match. It asserts current rollout rows and window counts match the history.
3. Repeats a full deterministic epoch twice at unchanged weights using CPU groups of four windows, 32-row microbatches, the production objective coefficients, and `len(rows) / len(window) / len(selected_windows)` gradient weighting. Main and rehearsal losses share the same backward call and history cache lifetime as production.
4. Compares the two actual frozen checkpoints under no-grad inference; no Adam step is reproduced or simulated.

Rehearsal draws use a recorded diagnostic seed, not the unrecoverable historical Python RNG state. Current-policy microbatches and window order follow production. A small initial forward/backward warms each model. The two read repetitions do not evict OS caches; process metadata caches warm across calls. The values below are two-run means, with individual wall and process-CPU observations retained in `probe.json`. Preliminary nonempty reads are separate single measurements from `recorded_costs.json`.

| Format/batch | Rows | Preliminary read | Full rollout read | Rehearsal read | Both content identities | Prepare validation | One fixed-weight epoch |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Duel 38 | 447 | 0.78 | 0.78 | 5.80 | 4.97 | 1.84 | 5.79 |
| Duel 489 | 536 | 0.95 | 0.98 | 17.05 | 7.10 | 2.49 | 7.69 |
| Duel 939 | 724 | 1.27 | 1.30 | 16.75 | 7.51 | 2.61 | 9.68 |
| Team 53 | 1,490 | 3.06 | 3.04 | 16.82 | 11.50 | 3.83 | 20.39 |
| Team 168 | 756 | 1.39 | 1.46 | 14.70 | 9.04 | 2.99 | 11.92 |
| Team 283 | 1,353 | 2.70 | 2.74 | 15.36 | 11.35 | 3.69 | 22.24 |

All times are seconds. Reads include gzip/metadata decoding, row validation, allocation and raw-history attachment; they are not pure disk time. Content identities include compacting and hashing targets and raw prefixes. `prepare` validates the supplied rows again. Summed measured per-batch preparation is 14.16, 28.57, 29.44, 38.24, 29.58 and 35.85 seconds, respectively. The preliminary bounded read only tests nonemptiness and is discarded before the full rollout read in `finish_train`; it must never be reused as a truncated PPO training batch.

Mean rehearsal read CPU times are 5.70, 16.32, 16.07, 16.76, 14.59 and 15.26 seconds, close to their wall times. This identifies substantial active CPU work in the reader under these probe conditions. Mean epoch CPU times are 5.79, 7.69, 9.68, 20.39, 11.92 and 22.24 seconds. These observations do not establish original-run host saturation.

| Format/batch | PPO forward | Rehearsal forward | Combined backward | PPO history context, included in forward | Rehearsal history context, included in forward |
| --- | ---: | ---: | ---: | ---: | ---: |
| Duel 38 | 0.66 | 1.23 | 3.76 | 0.17 | 0.74 |
| Duel 489 | 0.83 | 2.48 | 4.20 | 0.23 | 1.89 |
| Duel 939 | 1.13 | 2.93 | 5.39 | 0.33 | 2.12 |
| Team 53 | 2.47 | 5.89 | 11.50 | 0.80 | 4.22 |
| Team 168 | 1.31 | 3.85 | 6.49 | 0.46 | 3.01 |
| Team 283 | 2.32 | 7.28 | 12.14 | 0.79 | 5.76 |

History columns are **inclusive subcomponents**, not extra terms to add. Backward is joint; the probe does not attribute its cost to individual losses or recurrent operations. Rehearsal forward costs 1.86–3.14 times current-policy forward despite equal target counts, principally through the measured raw-history context path. Main and rehearsal tensor packing together take only 0.10–0.37 seconds per epoch. Reusing old hidden states across optimizer updates would change the model's semantics and is not an eligible shortcut.

This epoch deliberately omits optimizer steps, gradient clipping, training digest boundaries, saves/exports and the actual KL-dependent schedule. It cannot be multiplied by four to reproduce a historical batch: real batches stop early, weights change, partial windows vary, rehearsal draws differ and the original server had concurrent work. No claim about Adam execution cost, full trainer time or a global speedup follows from this table.

## Existing candidate and DAgger work

`lua/candidates.lua` records elapsed milliseconds around `C.generate`; `engine_lite/lua/host.lua` captures observations before it and asks the teacher after it. The stored field therefore supplies candidate-generation wall time for the recorded learner decisions, excluding teacher planning and environment execution. It has millisecond resolution and historical scheduling effects. Other seats' candidate work is not in these learner shards.

| Format/batch | Historical learner candidate seconds | Whole four-job worker-wall seconds | DAgger raw / queried / labeled rows | DAgger raw-read wall seconds |
| --- | ---: | ---: | ---: | ---: |
| Duel 38 | 6.198 | 43.995 | 447 / 94 / 88 | 1.05 |
| Duel 489 | 12.239 | 96.991 | 536 / 89 / 77 | 1.43 |
| Duel 939 | 9.938 | 83.081 | 724 / 87 / 74 | 1.82 |
| Team 53 | 34.791 | 422.027 | 1,490 / 128 / 118 | 4.02 |
| Team 168 | 13.484 | 221.080 | 756 / 120 / 115 | 2.05 |
| Team 283 | 33.766 | 577.002 | 1,353 / 128 / 119 | 4.08 |

Candidate time is a recorded component of those jobs, not an isolated benchmark or a new measurement of simulation. The candidate component alone does not explain most worker-wall time. DAgger copies a row for every learner decision to preserve raw history, although only 7.92–19.69% of this panel's copies contain a usable teacher label. All those teacher labels are excluded by the current PPO rehearsal control rule in the frozen run. The zero utility for this objective is established by the sampler/logs; teacher-query and write/compression CPU savings are **not measured** by reading the resulting files.

The retained duel/team DAgger corpora occupy 3.707/4.206 GB compressed, compared with 3.721/4.193 GB for their policy corpora. Those state-retained inventories include refresh or unsettled files where present, so they are not a count of completed PPO training inputs. FFA's DAgger belongs to BC refresh and is a separate consumer; no blanket removal is proposed.

## Actual policy movement at KL stop

The rollout export and its successor are real snapshots around the completed update. The probe uses every legal action to compute `KL(old_distribution || final_distribution)` and separately reconstructs the production sampled-action estimator `exp(logp_new-logp_old) - 1 - (logp_new-logp_old)`. Both are averaged within windows, then equally over windows. The stopped subset is reconstructed from its saved epoch/step/seed, not chosen afterward.

| Format/batch | Committed / planned steps | Logged stop KL | Exact KL on stopped windows | Exact KL on all windows | Relative parameter L2 change |
| --- | ---: | ---: | ---: | ---: | ---: |
| Duel 38 | 4 / 12 | 0.02540 | 0.01872 | 0.01492 | 0.0682% |
| Duel 489 | 5 / 12 | 0.03449 | 0.01069 | 0.00901 | 0.1195% |
| Duel 939 | 9 / 12 | 0.02312 | 0.01491 | 0.01383 | 0.2212% |
| Team 53 | 13 / 20 | 0.05684 | 0.03328 | 0.01752 | 0.2265% |
| Team 168 | 12 / 16 | 0.02150 | 0.02138 | 0.01470 | 0.1997% |
| Team 283 | 16 / 24 | 0.02372 | 0.01971 | 0.02155 | 0.2545% |

Maximum reproduced stop-KL error is `3.78e-8`; original rollout log-probability/value replay errors are at most `5.10e-6` / `4.95e-7`. Thus these stops do not require a stale-policy replay mismatch to explain them. Local movement and the sampled-action estimator matter. In team batch 53, one five-decision window has sampled KL 0.19812 and exact KL 0.10235; it receives the same window weight as longer windows. In duel batch 489, an eight-decision window contributes sampled KL 0.05166 versus exact KL 0.00801. This explains how a small subset can stop an update while the whole-batch average remains smaller. Team 283 also demonstrates that whole-batch exact KL can exceed 0.02.

These are on-batch, final-checkpoint comparisons, not held-out policy generalization or a per-step causal trace. They do not show that a larger KL gate is safe, that the stop should be ignored, or that Adam/auxiliary gradients caused the movement. The [four earlier gradient probes](../ppo_architecture_audit_20261106/gradient_probe.json) still do not establish persistent auxiliary-gradient dominance.

## Ranked changes to evaluate

The ranking combines measured cost and the likely effect on fresh information per unit work. It is a proposal for separate changes and authorized experiments, not a claim of realized gains.

| Priority | Evidence and possible direction | Validation before adoption |
| --- | --- | --- |
| 1. Make rehearsal work match its intended consumer | Resolve the retention objective in #225, then read, validate and hash the rows that objective actually consumes. Rehearsal reads cost 5.80–17.05 s, rehearsal identity 3.77–6.86 s, and the current post-read filter excludes about half the returned targets. | Filtering control sources **before** the bounded reader changes its per-source quotas and may increase available policy targets. Decide whether to preserve the old selected rows/effective budget or explicitly change the training distribution. For an equivalent data-path optimization require identical target IDs, raw prefixes, source mixture, digests, losses/gradients and stop cursor. For a new mixture require a separate retention/strength comparison under the selected 30-turn objective. Preserve the evaluation-control exclusion. |
| 2. Amortize preparation across more independent fresh trajectories | Only four fresh outcomes enter a batch; data preparation costs 14.16–38.24 s even before epochs. Evaluate a larger fresh-game batch using #223's broader scenario schedule rather than adding more passes over the same four outcomes. | First compare frozen complete batches for memory, complete-window weighting, no-drop behavior and per-decision preparation cost. Any new collection/training needs its own explicit scope. Compare matched fresh-game budgets and wall budgets, reporting distinct scenarios, actual committed visits/steps, whole-batch/stop-subset KL and official 30-turn score. Keep the 0.02 gate and settle-on-stop behavior. |
| 3. Avoid repeated work on the same immutable rollout inputs | The preliminary bounded read is thrown away and a second full read follows; its measured cost is 0.78–3.06 s. Content identities and repeated validation add measurable work. Read the full rollout once and pass it into preparation; examine reuse of validated immutable row/prefix contributions instead of repeatedly serializing them. | Never substitute a bounded 2,048-row preliminary subset for full PPO trajectories. Demonstrate identical full targets, no-drop rejection, identity values and resume behavior. Retain detection of changed input content. Measure each eliminated pass on the same frozen shards before any end-to-end claim. |
| 4. Stop PPO DAgger work that no chosen objective consumes | Current PPO asks for teacher labels and writes dense duplicate raw context, while its only rehearsal consumer excludes the labels. Retained duel/team duplicates consume 7.91 GB. | After #225 settles the consumer, trace every reader before disabling PPO queries/writes. Preserve BC refresh DAgger, teacher identity and raw-history semantics. A separately authorized paired game/profile experiment must verify identical learner decisions/RNG behavior where equivalence is claimed and measure query/compression CPU. File sizes alone are not a time estimate. |
| 5. Reduce repeated legal-history computation where gradients remain identical | Rehearsal history context takes 0.74–5.76 s per epoch and dominates rehearsal forward. The model already caches detached prefixes within a logical update. | First benchmark a narrowly scoped reuse of immutable input packing or valid same-weight context. Require forward and gradient parity across microbatches, correct cache invalidation after a weight change, and the existing bounded-memory behavior. Do not reuse old-policy hidden states or enlarge the architecture based only on this timing. |
| 6. Consider earlier KL rejection only after measuring its tradeoff | Rejected decision visits are 7.45%/5.12% of inspected visits. A no-grad precheck can avoid rejected backward/rehearsal work but adds a PPO forward to accepted steps; retaining all forward graphs instead can increase memory. | Replay the same fixed batches with identical stop subsets/cursors and unchanged #56 semantics. Compare total CPU/wall and peak memory, including the extra accepted-step forward. The current evidence does not make this the first optimization. No higher KL limit or retry is proposed. |

For the next authorized production comparison, record phase CPU and wall time with explicit scope, fresh games/decisions/scenario families, committed/rejected/never-attempted steps and visits, reader bytes, and the stop-subset versus whole-batch policy-movement measures. Those fields close the gaps identified here; slot occupancy alone does not.

## Reproduction and acceptance

The main committed source was sent with `git archive` and extracted into the fresh `_9bf5e0f` directory. The final script source was independently archived into `_0e73350`; the host needs no git. Main timing ran from 03:36 to 03:44 UTC before the other research task's CPU diagnostics. The preliminary-read pass completed afterward, still before releasing the timing window. Background host state is recorded, but no claim of an OS-isolated benchmark is made.

From an extracted final archive on Ubuntu, with the provisioned frozen inputs:

```bash
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PWD:/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension"
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
python=/home/tongshu/venv/bin/python
run=/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/runs/formal_30h_scratch
scripts=verification/ppo_efficiency_20261106
out=/tmp/ppo-efficiency-reproduction
mkdir "$out"
"$python" -m unittest discover -s "$scripts" -p test_diagnostic.py -v
"$python" "$scripts/census.py" "$run" "$out/census.json"
"$python" "$scripts/probe.py" "$run" "$out/probe.json" --repetitions 2
"$python" "$scripts/recorded_costs.py" "$run" "$out/recorded_costs.json"
```

The output directory must be new; existing evidence is read-only. `probe.py` asserts exact historical row/window/read-statistics and checkpoint-digest agreement, unchanged model weights after backward, and finite losses. Timings have no invented pass threshold. Further measured-output checks required six batches/two repetitions, rollout log-probability error below `1e-4`, value error below `1e-5`, stop-KL reconstruction error below `1e-5`, and the completed ledger sum identities. All passed; values are retained in [result_checks.txt](result_checks.txt). The two meaningful accounting assertions passed in [tests_final.txt](tests_final.txt). [Source checks](source_checks.txt) confirm the line limit with only the two unchanged grandfathered files and byte identity of the measured/final census and probe. No production suite was rerun because production code is unchanged.

Accepted here: reproducible frozen-input cost accounting, actual policy-movement reconstruction and concrete ranked follow-ups. Not measured here: new optimization speedup, new sampling/30-turn training behavior, training convergence, playing strength, or full native-engine semantics. No pending implementation acceptance item is added to `docs/TEST.md`; this research does not implement a production change.
