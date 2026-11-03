# Ordinary BC readiness on the current v6 teacher

**PASS for blocker 10.** The normal BC-only entry point reached an effective committed checkpoint in duel, four-player FFA and team. Each format passed the unchanged corpus, candidate coverage, held-out imitation and scenario-design gates. The Ubuntu phase finished naturally at 22:14:12 Asia/Shanghai on 2026-11-03, 69 minutes 10 seconds after launch, within the predeclared 90-minute budget. The process exited 0.

| Format | Committed checkpoint | Teacher games / target | Distinct scenarios / minimum | Coverage | Held-out samples | Overall accuracy | Cross-entropy / uniform |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Duel | v37, 1,824 optimizer steps | 56 / 48 | 31 / 12 | 5,533/6,128 (90.29%) | 749 | 54.21% | 2.70635 / 3.56500 |
| FFA | v16, 972 optimizer steps | 48 / 48 | 39 / 12 | 8,278/9,133 (90.64%) | 674 | 67.36% | 1.21075 / 3.55057 |
| Team | v17, 872 optimizer steps | 48 / 48 | 47 / 12 | 11,034/11,836 (93.22%) | 1,011 | 65.38% | 1.21767 / 3.57692 |

| Format | Recruit exact ≥60% | Move exact ≥35% | Attack exact ≥35% | Coverage by class (recruit / move / attack) |
| --- | --- | --- | --- | --- |
| Duel | 86/134 (64.18%) | 179/310 (57.74%) | 112/253 (44.27%) | 87.16% / 92.41% / 85.55% |
| FFA | 46/75 (61.33%) | 172/257 (66.93%) | 150/245 (61.22%) | 88.55% / 92.41% / 85.34% |
| Team | 49/78 (62.82%) | 434/621 (69.89%) | 70/183 (38.25%) | 90.55% / 93.64% / 88.44% |

All classes have at least 32 held-out samples. Overall accuracy exceeds 40% and cross-entropy is below 85% of uniform in each format. The coverage floor is 90% overall and 80% per class. Each gate has zero missing scenario rows. The opening spot-check field in the endpoint gates reads `passed=false, blocking=false` under the existing gate definition. There is no separate opening-probe acceptance claim.

## Ordinary completion and provenance

The first 48 duel teacher jobs covered 4,735/5,263 labels (89.97%). While coverage held the duel gate open the trainer continued its normal updates. Its existing plateau refresh scheduled eight additional teacher games and four DAgger games in batch 36. The eight teacher games supplied 798/865 additional matches, bringing coverage to 5,533/6,128 at the v37 boundary. The four DAgger games contributed corrections and were excluded from the 56-game teacher count and its coverage denominator. No seed or gate changed during the phase.

There were 234 complete jobs with zero recorded gameplay faults. Of these, 152 were eligible teacher games (56/48/48), four were DAgger refresh games, 30 were periodic validation games and 48 were reward-reference games. The teacher games included 2/40/46 turn-limit outcomes for duel/FFA/team respectively. They appear in the raw result's truncation field. Training masks value labels for truncated outcomes. The corpus here is newly generated v6 teacher data. The source archive's human import inventory supplied no compatible human training shards.

All three final `state.json` records show `stage=bc_complete`, `status=stage_complete` and `effective=true`. The three report summaries record completed pretraining. There is no pending update, pending validation, error or forced PPO selection. The four corpus, coverage, imitation and design gates were checked directly from the endpoint records. Independently summing the eligible teacher jobs reproduces the complete coverage object for each format. The corresponding final checkpoint paths and shard files exist and match the recorded hashes. The model parameter tensors, version and counters in each final `latest.pt` and `last_bc.pt` agree. [Exact metadata and extraction instructions](metadata/README.md) · [Shard and checkpoint identities](metadata/artifacts.json)

## Frozen inputs and command

| Input | Identity |
| --- | --- |
| Git source | `87a68eac666f1fe4f3384f39016d17feaf423e05` |
| Source tar | `25bca781a9040bfde7bcb6e439e426aa0865612999d9bc5a2aafbd0912a8303a` |
| Run manifest SHA256 | `32adc2420926f9dc9e2f88a5c2a4e35956d486f121dd94b970485b1f3244a9be` |
| Teacher (probabilistic_combat_v6) | `d64e1178c0a8af9b1b10e2626f03e7cb8ed70a5a368d3c38860d40723a903eb5` |
| Frozen teacher parent | `2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933` |
| `1.18.8-combat-filtered` rules | `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17` |
| Accepted v6 Lite extension | `63b1c119670d4d0981925fafef4f781ab274f05fb0aa2fedafc8b24dfd503059` |
| Entropy shim | `f12d763303445aa437de06d0dba129dc923e3d81fd1fc82d72b8e331916480cf` |

The committed source was shipped by `git archive` with all tracked root entries except historical `verification/`, `runs/` and `delivery/`. The local and Ubuntu archive digests matched, as did the archive's commit comment and shipped source. The fresh source directory was `/home/tongshu/acceptance/bc_v6_readiness_20261103`. The accepted extension and read-only rule/map directories were linked there. Ubuntu ran Python 3.12.3 and PyTorch 2.9.1+cpu. The actual manifest binds the teacher tree, opponent, rules, schema and `work-12000-v8` candidate budget. The job results identify which shard belongs to each accepted game. The full teacher digest is established by the isolated source, manifest and jobs; a Lite row carries its teacher profile.

```sh
cd /home/tongshu/acceptance/bc_v6_readiness_20261103
export PYTHONPATH="$PWD/.extension:$PWD:$PWD/vendor/arena"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy SOURCE_COMMIT=87a68eac666f1fe4f3384f39016d17feaf423e05
timeout --signal=TERM --kill-after=15s 5550s /home/tongshu/venv/bin/python -u -m learning run \
  --run-dir runs/bc_readiness --phase bc --hours 1.5 --formats duel ffa4 team2v2 \
  --engine lite --evaluation-engine lite --device cpu --workers 8 --trainer-threads 1 \
  --seed 20261101 --bc-games 48 48 48 --native-bc-games 0 0 0 --bc-batch-games 8 \
  --bc-records 2048 --bc-validation-records 1024 --training-max-turns 30 \
  --wesnoth /home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth
```

Start was 21:05:02 with a 22:35:03 phase deadline. Eight global workers and one thread per trainer ran at the original four epochs, minibatch 256, original learning rate, scenario partitions and ordinary gates. The 48-game corpus target is the bounded item-10 readiness profile. The default formal targets remain 300/600/400. [Design frozen before training](../bc_readiness_scope_20261103/PLAN.md)

## Changes, diagnostics and limits

The adopted fix makes the BC value head consume the schema-6 `terminal_reward` on valid rows and preserves the older schema and masks. A toy training step failed before this fix and passed afterward. The v2 matched recruit-type experiment used the same model, Adam, RNG and 224 updates in each arm. The recruit-type objective yielded 37/85 versus 41/85 for the control, so production retained the existing imitation loss. This v6 run differs from the old v2 runs in teacher, rules, corpus and training time. The aggregate improvement cannot be assigned to the value-label fix alone. [Value target regression](../bc_terminal_value_20261103/REPORT.md) · [Matched comparison](../team_bc_recruit_marginal_20261103/REPORT.md)

A separate candidate proposal recovered a legal Spearman recruit in an early duel board, while displacing seven partial leader moves in that example. It stayed outside the accepted source. The evidence here covers v8. The earlier fixed-schedule candidate repair and the independent native teacher strength result satisfy the preceding item-10 requirements. [Probe diagnosis on its retained branch](https://github.com/t66sun/wesnothLearning/blob/7ae34991f1c61af589347bd8e3780f9d8b0739de/verification/recruit_probe_priority_20261103/REPORT.md) · [Candidate coverage](../bc_root_20261101/REPORT.md) · [Native teacher strength](../duel_landing_ni_20261103/REPORT.md)

This closes item 10 for ordinary BC readiness under the stated real-data profile. Student playing strength, convergence, and the approximately one-hour complete training loop are separate outcomes. Item 11 still requires its integrated BC/PPO, stop/resume, selection, complete final evaluation and audited export under its own stage ceilings.
