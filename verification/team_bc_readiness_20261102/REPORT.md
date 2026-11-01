# Ordinary team BC after exposure repairs

## Frozen experiment

Source `cb4f03e42091b1d2955f3cc79717be68841c7e59`, shipped with `git archive` into `/home/tongshu/acceptance/team_bc_readiness_20261102` on Ubuntu `cpuServer`. This includes the family-pool admission fix and balanced team teacher factions. It changes neither the BC objective nor any gate. Rules SHA-256 `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`; teacher source `a5d4b3a69d5af0378fa22119f315c1300fb6ad965c79b08071eb4a37c0addbef`, profile `expected_damage_v1`.

Team2v2 only; fresh initialization, seed 20261101, 8 shared workers, one trainer thread, CPU/lite, 48 teacher-game target, 2048 training / 1024 validation rows, four epochs per batch. Predeclared 20-minute phase with a 22-minute external stop, no automatic extension or forced PPO. Other formats, final evaluation and export were not run.

```bash
export PYTHONPATH=.:vendor/arena OMP_NUM_THREADS=1
timeout --signal=INT --kill-after=30 1320 /home/tongshu/venv/bin/python -u -m learning run \
  --run-dir runs/team_bc --hours 0.3333333333333333 --phase bc --formats team2v2 \
  --device cpu --engine lite --workers 8 --trainer-threads 1 --seed 20261101 \
  --bc-games 48 48 48 --native-bc-games 0 0 0 --bc-records 2048 --bc-validation-records 1024 \
  --rules-dir /home/tongshu/myDev/wesnothLearning/WesnothLearning/rules/1.18.8-training \
  --wesnoth /home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth
```

## Observed result: ordinary gate FAIL

Natural exit 0, `bc_complete`, about **21m08s** including finalization (UTC 20:18:03–20:39:11). The external timeout did not fire. Thirty teacher games complete, two are budget-interrupted, zero recorded faults; thirteen completed games reach the true turn limit. Three BC batches commit **120 optimizer steps**. The fourth collected batch is pending at epoch 0 / step 0; it is not represented by the last committed model/gate. `bc_complete` indicates phase termination, not readiness.

Last gate: **24/48 games**, 19 distinct scenarios (floor 12), coverage passes at **92.59% overall**, recruit 85.84%, move 92.94%, attack 88.37%. Imitation fails: overall accuracy 43.98%, recruit **18.64%**, move **52.91%**, attack **13.89%**; required floors remain 40%, 60%, 35%, 35%. CE 2.06949 is below 85% of uniform CE 3.54499; every class has at least 32 validation samples. This does not overcome the recruit/attack or corpus failures.

The archived `last_bc.pt` hash is `ffb554ca152ac93e3602bd45c98841238ef7ee59640b5bf7fb4ba64ba8148a97`. Read-only decomposition reproduces its validation correct/sample counts:

| Class | Training correct / samples | Validation correct / samples |
| --- | ---: | ---: |
| Recruit | 24 / 98 (24.49%) | 11 / 59 (18.64%) |
| Move | 783 / 1382 (56.66%) | 309 / 584 (52.91%) |
| Attack | 86 / 339 (25.37%) | 30 / 216 (13.89%) |

Recruit predictions choose the correct action kind in 90/98 training cases, but the correct type in only 41 and slot in 45. Within recruit candidates, only 28/98 rank the label first. Attack within-kind training ranking is 141/339; action-kind selection is also poor. The remaining failure includes fitting the training examples, so it cannot be attributed solely to held-out generalization or a missing faction.

The exact committed 2048-row read retains **12 of 17 available training families**, all six focal factions: Northerners 342 rows, Loyalists 342, Drakes 342, Rebels 684, Knalgan 171, Undead 167. Five families are excluded by the unchanged retained-byte budget, zero by compressed bytes. Charged retained estimate is 770,368,456 bytes below the 768 MiB limit; returned-row estimate is 343,658,072 bytes. These are accounting estimates, not RSS measurements.

Scheduler spans for the three completed collection batches are 225.31, 244.72 and 258.64 seconds. The fourth, interrupted collection span is 166.36 seconds. Collection is a substantial cost before more fitting can happen; gaps also include reads, updates, gate evaluation and checkpointing, and are not labelled pure optimizer time. Five fixture tests ran during BC (0.043 s test-body time); this run is not an isolated performance benchmark. No speedup or apples-to-apples quality gain over the earlier all-format run is claimed.

## Read-only follow-up commands

From the same extracted source, after ordinary BC exits:

```bash
timeout 300 /home/tongshu/venv/bin/python -u tests/diagnose_bc_parts.py \
  --run runs/team_bc --output committed_parts.json
timeout 300 /home/tongshu/venv/bin/python -u tests/diagnose_bc_admission.py \
  --run runs/team_bc --output admission.json
```

Both exit 0, empty stderr; neither writes model/checkpoint/shard inputs. Commands use `PYTHONPATH=.:vendor/arena OMP_NUM_THREADS=1`. `committed_parts.json`, `admission.json`, their logs/exit files, the manifest, clock, state, gate, jobs and schedules are archived here. Model/data remain at the recorded server run path. The native tactical diagnostic ran after training exited, briefly overlapping the read-only checkpoint audit.

Item 10 and L2 remain open. The repairs establish more balanced exposure, not affordable readiness. Next useful fitting evidence is a predeclared learning curve on this exact frozen batch, retaining the original loss/sampler and a fixed update/time budget, to separate too few optimization steps from a persistent ranking/representation limit. Do not repeatedly recollect the same corpus, expand candidates, or lower gates to compensate.
