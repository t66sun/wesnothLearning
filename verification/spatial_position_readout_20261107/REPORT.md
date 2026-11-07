# PPO-C1 spatial position readout

The 48→16 readout distinguishes the recorded distant-hill pair with a fixed nonzero position coefficient. The `[I,0,0]` initialization preserves mean pooling. Python and Lua agree within `5.69e-14` on 220 recorded decisions after saving and reloading nonzero position weights. This is implementation evidence for [#276](https://github.com/t66sun/wesnothLearning/issues/276). Adoption and playing strength are assessed separately in [#278](https://github.com/t66sun/wesnothLearning/issues/278).

## Position and checkpoint assertions

- The [#229 hill pair](../representation_information_20261106/REPORT.md) moves a publicly visible hill from `(8,5)` to `(8,11)`. Two deterministic center-tap convolutions pass the terrain channel. Global pooling produces equal scenes. A y-moment coefficient of one separates the first board feature by `0.0003277504280821918`. The [original-mean run](red.log) returns zero and fails that assertion.
- At identity initialization the full forward matches the old mean operation on a fixed input with history. Both position blocks receive gradients, and the scene and GRU widths match the existing network. The [focused suite](green.log) passed 30 checks in 12.550 seconds, including checkpoint identity, recovery of a pinned interrupted weights-only child, stale export rejection, replay, and current checkpoint export. Ordinary loading of the predecessor rejects its architecture.
- Both source archives initialized a fresh BC child from the exact [#227 actor source](../duel_ppo_acceptance_20261107/REPORT.md) through the real coordinator and trainer constructors, with collection prohibited by the fixture. All compatible actor tensors are byte-equal across arms and match the source checkpoint. The seeded reset critics also have the same digest. Both children start with empty Adam state, corpus, and runner history and require fresh BC qualification. Baseline and C1 produced identical choices, log probabilities, and values on all three timed states at initialization.
- The existing `verify_numerics` auditor compared logits and value after each recorded prefix, committing the first recorded write per turn once. The archived duel shard covers 220 decisions over 20 turns, with up to 37 candidates. The probe set the x and y projection blocks to `0.125 I` and `−0.25 I`, saved and reloaded the checkpoint, and ran the usual exported Lua weight encoding. The maximum error was `5.684341886080802e-14` against the existing `1e-5` bound.

## Cost on frozen states

Ubuntu `cpuServer`, 2026-11-07 14:37:29–14:38:09 UTC. Intel i3-13100F, Python `/home/tongshu/venv/bin/python`, PyTorch 2.9.1+cpu, one intra-op and one inter-op thread. OMP, MKL and OpenBLAS were each set to one thread. Each path has one discarded warmup and two retained measurements. [Host before](host-timing-before.txt), [host after](host-after.txt), [baseline measurements](baseline.json), [C1 measurements](readout.json).

Each cell shows baseline → C1 mean wall milliseconds.

| State | Candidates / entities / prior turns | Lite decision | Lua decision | Training forward + backward |
| --- | ---: | ---: | ---: | ---: |
| #228 recruitment | 17 / 3 / 0 | 6.53 → 6.80 | 67.56 → 67.64 | 4.57 → 4.59 |
| #228 combat slots | 37 / 33 / 0 | 15.39 → 15.25 | 134.70 → 134.60 | 5.38 → 5.55 |
| #227 turn 20 | 37 / 18 / 19 | 4.78 → 4.73 | 120.94 → 121.12 | 31.05 → 31.03 |

The two short Lite measurements include public observation, candidate construction, DTO serialization, the frozen policy forward, and action choice. The long Lite measurement starts at the recorded decision row, with 18 prior writes already cached. It includes encoding the most recent committed write, the memory read, and the current policy and choice. Lua starts from its prepared public inputs and committed memory, and measures `network.forward` plus greedy selection. Its timings exclude engine work and Python-to-Lua fixture conversion. The training path includes packing, the full model, eight differentiable history turns on the long case, the existing auxiliary classification loss, a fixed value target, and backward. The probe performs zero optimizer steps. Raw measurements separate forward and backward. C1 adds **784 parameters** (776,178 → 776,962). The three states and two samples per state bound these observations to the measured inputs.

Spatial capture continues to average within each 16×16 bin. The route in the separate 32×16 fixture still opens or closes within one bin while yielding identical actor inputs. The hill witness tests position capacity. Playing strength, convergence, native end-to-end latency, and training throughput require separate evidence.

## Identities and reproduction

| Item | Identity |
| --- | --- |
| Common baseline | `07db85b8ba4def9bfebc7b42fe4c7bec0c4fd1b0` |
| Red source with focused assertion and probe | `657baf18b52884942838ad9006eb5a87eec26e0e` |
| Red `git archive --format=tar.gz` SHA-256 | `d062031d8db67d14d6d9071e3135283f264be980305dfe9d0f7c844450efe24b` |
| C1 tested source | `1bd6079393941c99bb8d407002ca5af63a4e16c1` |
| C1 `git archive --format=tar.gz` SHA-256 | `ab3a740d0f8a07b416581fa459f2b131c9951b82d0e538f45216d7585d495533` |
| Frozen rules SHA-256 | `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17` |
| Frozen Astra package SHA-256 | `2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933` |
| Lite extension SHA-256 | `56dd77140411db987377d6de4ffbf562da4d0e5c76bc16d34780da67e60e5ae4` |
| Parent manifest SHA-256 | `6de9d81858c71c41de505db2c445bae5229fa8587db7a6d3d66d2ebc3eab3c88` |
| Parent duel `last_bc.pt` SHA-256 | `05908d7f972148ccc7b39b8df0cc00435e2176861654a632de44c379b94953ab` |
| #228 measured fixture SHA-256 | `c3d5b3dbbde3433b13d62e03d444efd37bb941e2e63fc4bc4f1c7cc252f015ae` |
| #227 raw duel shard SHA-256 | `8c06bd724362b3777723a4200d02d1310836f3d56cbcd3c65e24118878eeee1d` |

The committed archives were extracted into fresh `source/` directories on Ubuntu. The following runs from a Bash shell on `cpuServer`, with fresh output paths for a repeat. The red command is expected to return 1. No local Windows tests, new games, collection, or training runs were used.

```bash
old=/home/tongshu/acceptance/spatial_position_readout_20261107_657baf1/source
new=/home/tongshu/acceptance/spatial_position_readout_20261107_1bd6079/source
formal=/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source
recorded=/home/tongshu/acceptance/duel_comparison_20261106_43325b3/source/runs/duel_ppo_comparison_20261106/runs
shard="$recorded/a3/duel/data/rollout-00050-duel-g2.jsonl.gz"
py=/home/tongshu/venv/bin/python
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

cd "$old"
export PYTHONPATH="$PWD:$formal/.extension"
"$py" -m unittest -v \
  tests.v5.test_spatial_position_readout.SpatialPositionReadoutTests.test_distant_hill_changes_position_feature_with_equal_global_mean

cd "$new"
export PYTHONPATH="$PWD:$formal/.extension"
"$py" -m unittest -v \
  tests.v5.test_spatial_position_readout tests.v5.test_finite_score_identity \
  tests.v5.test_checkpoint_ops tests.v5.test_checkpoint_export_identity \
  tests.v5.test_parallel_export_audit tests.v5.test_lite_policy_memory \
  tests.v5.test_training_failure_fixes.FailureBoundaryTests.test_internal_export_resume_keeps_weights_integrity_without_sdk_size_cap \
  tests.v5.test_learning_core.PolicyArchitectureTests

# Reserve a shared CPU slot for both probe processes.
for source in "$old" "$new"; do
  cd "$source"
  export PYTHONPATH="$PWD:$formal/.extension"
  "$py" verification/spatial_position_readout_20261107/probe.py \
    "$formal/runs/formal_30h_scratch" "$WESNOTH_RULES_DIR" "$shard" "../repeat.json"
done
```
