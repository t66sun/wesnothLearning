# Ordinary BC readiness scope and prospective v6 phase

Blocker 10 requires genuine, committed ordinary BC gates for duel, FFA and team on the current teacher and rules. The completed coverage and teacher-strength evidence stays at its original paths. Item 11 owns subsequent PPO, resume, final evaluation and export. This document records the starting evidence and the phase design before the first new training game.

## Evidence behind the decision

The historical v2 team v10 gate and its manifest give thresholds of 40% overall, 60% recruit and 35% each for move and attack. Its 34/85 recruits fall short of the required 51. Move (426/667) and attack (56/141) clear 35%. Overall accuracy, cross-entropy, corpus (48/48), coverage (94.21%) and scenario design also pass. The dated team report's description of attack as failing conflicts with its recorded gate values. The original record is preserved. [Frozen gate and run metadata](../team_bc_branch_20261102/REPORT.md)

On the 85 held-out recruit decisions, 60 slot predictions and 48 type predictions were correct. This leaves 26 right-slot/wrong-type cases. The actual 48-source team pool has 11,978 rows. All 11,284 covered actions map uniquely to their recorded candidate and the 694 misses have no matching candidate. The 48 families are partitioned consistently. All 691 covered recruits use the same synthetic actor ID. The auxiliary actor group duplicates the action-kind group in each of those rows, including 524 rows with multiple recruit types. Exact candidate cross-entropy still supervises the type. This motivates testing a recruit-type marginal in place of that redundant auxiliary term.

The independent schema-6 value issue concerns the target for valid terminal outcomes. In the old v10 corpus three training games contribute 308 covered value-valid rows whose stored `terminal_reward` is −1. The old BC path reads a missing `reward` as zero. Its correction and the recruit-supervision comparison have distinct tests and evidence.

## Frozen v2 comparison

One matched diagnostic starts at the v10 `last_bc.pt` from `/home/tongshu/acceptance/team_bc_branch_20261102/runs/team_bc_branch/team2v2`, SHA256 `b74350699b445e63cdd11fd07f317e0d818fe3d3166d49705b1342b00336035e`. Both arms use the archived v2 runtime, identical optimizer/RNG state, 2,048/1,024 train/validation rows and 54 training windows. Compare the original objective to changing the recruit actor marginal to a recruit-type marginal. Each arm has 16 complete epochs, 224 updates, 896 window visits and at most 600 seconds. Record the train and held-out exact/type/slot results and the entire original gate at the fixed endpoint. Using held-out labels to mask candidates serves only as an offline error diagnostic. The policy receives its normal legal inputs.

A passing original gate in the changed arm when the control fails supports trying the change prospectively. A result without a clear benefit to ordinary readiness leaves the production auxiliary objective alone for the next phase. The historical data do not provide a v6 acceptance result.

## Current ordinary BC phase

The source baseline at planning is `702dd9a5da4096c8934b8a9909de2ed367443be2`. Before launch, freeze the actual merged source, git archive, rule digest, extension, teacher digest and the final command. The current teacher is `d64e1178c0a8af9b1b10e2626f03e7cb8ed70a5a368d3c38860d40723a903eb5`, profile `probabilistic_combat_v6`. Previous trainable corpora use old v1/v2 combat and teacher identities. The native strength panels carry no learning shards. Fresh BC therefore needs current teacher samples; preserve the old data unchanged.

Use the ordinary `python -m learning run --phase bc` entry in a fresh Ubuntu source extraction and run directory. Freeze seed 20261101, all three formats, 48 teacher games per format as the ordinary corpus target, 30 turns, eight shared workers, one CPU thread per trainer, eight games per BC batch, four epochs, minibatch 256 and 2,048/1,024 train/validation rows. The phase budget is 90 minutes, with a 150-second external shutdown allowance. Normal periodic validation, recorded opening checks and adaptive refresh remain active. The 48-game values are corpus targets; report actual scheduled/completed/refresh/truncated games and committed batches. The supplied 48-game profile is the earlier item-10 bounded readiness profile. Production defaults are 300/600/400 games. No human shard in the audited inventory has the current candidate contract.

Freeze the full intended command using the shipped working directory and actual Wesnoth path:

```sh
timeout --signal=TERM --kill-after=15s 5550s /home/tongshu/venv/bin/python -u -m learning run \
  --run-dir runs/bc_readiness --phase bc --hours 1.5 --formats duel ffa4 team2v2 \
  --engine lite --evaluation-engine lite --device cpu --workers 8 --trainer-threads 1 \
  --seed 20261101 --bc-games 48 48 48 --native-bc-games 0 0 0 --bc-batch-games 8 \
  --bc-records 2048 --bc-validation-records 1024 --training-max-turns 30 \
  --wesnoth /home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth
```

Each format must pass actual corpus, coverage, imitation and design gates on a committed BC checkpoint. Keep coverage ≥90% overall and ≥80% by kind, 12 or more distinct scenario families, no missing scenario rows, actual imitation counts of at least 32 per kind, cross-entropy below 85% of uniform, and the frozen accuracy thresholds above. Record the manifest's teacher/rule identities and the job-to-shard provenance and hashes, making the distinction from per-row metadata explicit. Stop at the ordinary phase boundary or its declared budget. An ineffective checkpoint remains a failure. The results guide any separately predeclared follow-up to a specific remaining cause.
