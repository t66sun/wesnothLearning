# Selected checkpoint native final evaluation

Blocker 9 and L1 pass on Ubuntu. The exported duel v12 policy from the restored Astra run finished all 120 original final games in 1,179.17 seconds with four workers. Every game produced a native replay. The original run recorded 120 first-turn watchdog faults. This rerun recorded zero faults, zero missing blocks, 109 last-leader finishes and 11 draws adjudicated at the 30-turn cap.

| Control | Win / draw / loss | Scored blocks | Distinct paired scenarios | Official difference and 95% interval | Strength verdict |
| --- | --- | --- | --- | --- | --- |
| Frozen Astra | 16 / 8 / 36 | 30/30 | 30 | −1.00 [−1.55, −0.45] | not_passed |
| Baseline | 22 / 3 / 35 | 30/30 | 30 | −0.65 [−1.15, −0.15] | not_passed |

The score uses the production evaluator's paired, cluster-weighted difference on the 3/1/0 scale. Both controls met the minimum of 12 distinct scenarios. The timing audit measured 23,331 regular policy returns with p95 232 ms and maximum 316 ms, under the one-second limit. Of these, 13,704 occurred from turn 10 onward, with p95 240 ms. First returns used the SDK's ten-second startup allowance and peaked at 916 ms. [Full scores](summary.json) · [Referee audit](audit.json)

## Protocol and identity

The original L1 run declared duel as its only format. It recorded 40 completed teacher games, seven applied PPO batches, a stop and resume, identical future batches 8–11 and a pre-holdout selection of the fallback last PPO checkpoint. Those clauses reuse their original evidence. This acceptance activates the remaining native evaluation stage. Ordinary BC remains a separate L2 requirement. [Original results](../acceptance_20261031_astra/REPORT.md) · [Same-future comparison](../acceptance_20261031_astra/same_future.json)

The selected file from original training source `5ac67d9` still hashes to `603e3c83d6658b96d65da62bdf5cb277e979fbb19b080d4269ee4ac6e65fff08`. The replay used deployment source `ea449f711877b2966598fee1a014f488ad4d6f20` from a fresh Git archive. The current architecture and ordered input schema match the checkpoint after separating the added candidate-selection descriptor. Strict weight loading consumed the original state dictionary. The fresh greedy export used the current `work-12000-v8` policy and the checkpoint's training lineage. [Plan and hashes](plan.json) · [Export manifest](export.json)

The original schedule SHA256 is `31049d275eef253d72f3ed3a8f000b0c3e0c3d7dbf9c6ce2271720eeb1dc67fc`. Only the policy location, replay destination and isolated evaluation deadline changed. Each job used its original seed, map, factions, sides, native executable, control, turn cap and scenario identity. The acceptance driver used production export, collection and comparison functions. The postrun audit matched all 120 unique result IDs, compared both schedules, verified played seeds, factions and policy seats, and inspected referee events and native replays. [Executed schedule](schedule.json.gz) · [Raw results](jobs.jsonl.gz) · [Events and replays](referee-events.tar.gz)

## Reproduction

On `cpuServer`, extract the archive into `/home/tongshu/acceptance/selected_final_20261103`, provision the frozen rules and build the entropy shim as in `prepare.sh`. During initial preparation the default rule directory selected a different vocabulary, and input verification stopped before any games. The executed command in `launch.sh` explicitly binds the original schedule's `1.18.8-training` directory. Both the preparation failure and the successful panel are preserved. The panel exited 0. [Setup](prepare.sh) · [Initial failure](setup-failure.log) · [Executed command](launch.sh) · [Rule, archive and shim hashes](identities.txt) · [Throughput](jobs.throughput.jsonl)

The audit command on the same host was

```sh
cd /home/tongshu/acceptance/selected_final_20261103
python3 audit.py panel /home/tongshu/myDev/wesnothLearning/acceptance_20261031_astra/src/runs/l1-20261031b/a/duel
```
