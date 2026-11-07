# PPO-C2 public native grid

The public board is stored at the map's true width and height. The recorded 32×16 route pair now yields different actor inputs, from which the public ground route reconstructs as 24 steps versus unreachable. Python batching masks padded activations between the convolutions and excludes padding from all three C1 readout moments. Lua uses exact map dimensions. This evidence covers [#277](https://github.com/t66sun/wesnothLearning/issues/277), stacked on accepted [C1](../spatial_position_readout_20261107/REPORT.md). Playing strength and adoption belong to [#278](https://github.com/t66sun/wesnothLearning/issues/278).

## Behavioral evidence

- The route assertion fails on the archived C1 source because the two public boards coincide. It passes with native cells, checks every publicly known terrain-ID cell against the fixture, and reconstructs the 24-step and closed routes using only the actor channels. Other current actor inputs match. [Route red](route-red.log), [42-check green run](green.log).
- A non-square 8×6 state, alone and batched with a 32×16 state, has matching valid second-convolution activations, projected readout, policy/value outputs, input gradients and convolution/projection parameter gradients. Both convolution biases and both moment blocks are nonzero. Removing only the first-convolution mask in memory makes 208/768 valid activation elements disagree, with maximum difference `0.23562374429223737`. The archived source files stay intact during this mutation. [Padding red](padding-red.log).
- Recaptured #229 controls preserve hidden-terrain/hidden-unit equality, known fogged terrain, zero unexplored cells, and the last observed enemy location after it becomes fogged. The local 19-cell path uses the existing public tile table. The C1 hill and identity/gradient assertions pass on recaptured inputs.
- Current feature observations use schema 7 and persisted rows use schema 8. Both are disjoint from pooled feature/row schemas 5/6. Decision and memory-write grids carry positive dimensions, shape and finiteness checks. A real pooled #227 shard is rejected by the current raw reader. Human intake rejects old feature observations. The stored finite-task terminal-reward check accepts schema 8 and rejects a conflicting outcome.
- A fresh weights-only BC child imports the exact original #227 actor, with the same actor and seeded reset-critic digests as C1. The source checkpoint and manifest hashes are verified, the optimizer/corpus/qualification reset, and interrupted-child recovery passes. Ordinary checkpoint loads require the current feature and architecture identities. Resuming/exporting historical checkpoints uses their original source.
- The current production rowpack writer, indexed reader, complete raw reader, checkpoint save/load, exported Lua weights and usual `verify_numerics` auditor cover the recaptured fixtures. The replay contains 44 raw rows across 32×16 and 39×9 boards. Its 40-write history repeats the first legal public write from the original #229 structural fixture. Nonzero moment blocks `0.125 I` and `−0.25 I` survive save/reload, and maximum Python/Lua logit/value error is `2.1316282072803006e-14`, under the existing `1e-5` gate. Retained [raw fixture shards](fixture_rows/) are newly captured and labelled as fixture evidence.

The focused suite ran 42 tests in 8.391 seconds. Its tests cover spatial capture, checkpoint initialization, reward-row semantics, candidate provenance, live policy memory, mixed replay, PPO prepared/reread inputs, policy architecture and batching. No Windows tests ran. All engine execution in this acceptance used fixed synthetic fixture moves or observation of a fixed initial map state. Formal collection and training were not started.

## Supported sizes and measured costs

The inventory includes vendored `arena2` 15×13, `arena4` 19×19 and `arena8` 25×25, plus the frozen native maps below.

| Map | Width × height |
| --- | ---: |
| caves_of_the_basilisk | 41×24 |
| clash | 27×26 |
| hamlets | 27×28 |
| isars_cross | 25×25 |
| loris_river | 25×25 |
| morituri | 21×21 |
| ruined_passage | 47×25 |
| sablestone_delta | 21×28 |
| the_freelands | 37×24 |
| weldyn_channel | 29×22 |

The sampled endpoints are `arena2` (smallest, 195 cells) and `ruined_passage` (largest, 1,175 cells). The largest current optimization map is `the_freelands`, 888 cells. A nine-channel float32 grid needs 7,020 / 42,300 / 31,968 bytes respectively, before metadata, entities, candidates, memory writes and compression. C1 always allocated 9,216 grid bytes. The representation accepts arbitrary positive rectangular dimensions through the same path.

Six fresh processes ran serially in the reserved Ubuntu window, 2026-11-07 15:02:42–15:03:14 UTC. Each case/arm performed one discarded warmup and two retained measurements. The machine was an Intel i3-13100F, 8 logical CPUs, about 15 GiB RAM. Python was `/home/tongshu/venv/bin/python`, PyTorch 2.9.1+cpu, one intra-op/inter-op thread, and OMP/MKL/OpenBLAS each one thread. [Host before](host-before.txt), [host after](host-after.txt).

Each timing cell is C1 → C2 mean wall milliseconds. The two map states each have 37 candidates and one visible entity. The history fixture has one current candidate, five entities and 40 prior public writes.

| Input | Indexed read | Lite decision | Lua decision | Training forward | Training backward | Forward + backward |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| arena2, 15×13 | 1.57 → 1.39 | 10.11 → 10.15 | 106.81 → 99.10 | 2.24 → 2.39 | 4.96 → 5.11 | 7.20 → 7.50 |
| ruined_passage, 47×25 | 1.62 → 1.50 | 14.87 → 15.74 | 106.52 → 218.17 | 2.27 → 2.52 | 25.22 → 25.66 | 27.49 → 28.18 |
| 32×16, 40-write fixture | 14.31 → 16.85 | 3.40 → 3.68 | 41.86 → 72.43 | 32.89 → 34.54 | 10.86 → 11.13 | 43.74 → 45.67 |

The map Lite measurements include observation, candidates, DTO serialization, `FrozenPolicies.choose`, and action selection. The history Lite sample starts from the stored row, primes 39 prior writes outside the timer, and measures the latest newly committed write plus the memory read and current decision. Lua measures full `network.forward` and choice on prepared public inputs and committed memory. Input conversion and engine observation are outside that Lua timer. Training includes packing, the complete model, the existing auxiliary classification loss, a fixed value target, and backward. The eight-turn differentiable suffix and detached full prefix are exercised by the history case. The probe performs zero optimizer steps. The indexed reader includes reconstructing the complete raw prefix.

| Input | Last packed raw row bytes | First context row bytes | Gzip shard bytes | Process peak RSS KiB |
| --- | ---: | ---: | ---: | ---: |
| arena2 | 102,964 → 100,059 | — | 5,056 → 4,969 | 468,200 → 468,364 |
| ruined_passage | 103,398 → 147,534 | — | 7,043 → 8,499 | 468,160 → 468,756 |
| 41-row history shard | 18,415 → 30,906 | 80,511 → 105,156 | 122,306 → 137,732 | 434,176 → 431,724 |

A raw context row in the history shard includes the captured candidate set. The reconstructed memory prefix drops those candidates, using the existing sequence reader. RSS is each fresh process's high-water mark after the cost calls, including imports, rules, temporary exports and fixture input. The C2 history parity audit runs afterward.

The large-map Lua decision roughly doubles on this sparse visible opening. The extra grid cells enter both direct Lua convolutions. The largest-map gzip sample grows 20.7%, and the history shard grows 12.6%. These three fixed inputs and two samples per path provide launch-budget reference points. Dense games, complete BC corpus volume, production throughput and deployment p95 need C3 measurements. The C2 model still has 776,962 parameters.

Raw observations and per-call samples are in [C1](c1/) and [C2](c2/). All six runs record the same common actor digest `a2e7404d33e24bc47030734516b05d3c18dc26273c819ff7ecc60431f1c4da98` and reset-value digest `f6f87f880073b8630a3d2f0c1d1d8ad504080fbe3a23b291a2404b6bd69bf73f`. C2 changes the board semantics, and its values/log probabilities differ from C1 on these inputs.

## Sources and reproduction

| Item | Identity |
| --- | --- |
| Accepted C1 base | `64413c72208b7cc9fd944f699558de2b83123b6b` |
| C1 with C2 assertion/probe | `6c3ad4745fcb2e24aa921351107b11c54fe0aa6c` |
| C1 archive SHA-256 | `d37c1ea775f18e54285767eb8ded97ceda65cdf86a1d32f9688089ab1165f9f2` |
| Tested C2 source | `22202ec9ade7bda316a67c67e6a7b4ee1ea643a7` |
| C2 archive SHA-256 | `f8e51d7222994b2e55024596e5a8ccfcc934d12d5de8e98c5242cb0eeb167c3e` |
| Frozen rules SHA-256 | `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17` |
| Frozen Astra package SHA-256 | `2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933` |
| Lite extension SHA-256 | `56dd77140411db987377d6de4ffbf562da4d0e5c76bc16d34780da67e60e5ae4` |
| Original parent manifest SHA-256 | `6de9d81858c71c41de505db2c445bae5229fa8587db7a6d3d66d2ebc3eab3c88` |
| Original duel actor checkpoint SHA-256 | `05908d7f972148ccc7b39b8df0cc00435e2176861654a632de44c379b94953ab` |

Both `git archive --format=tar.gz` files were extracted into fresh directories. Each `source/data/rules/1.18.8` links to the previously frozen map inventory. The following commands run on `cpuServer`, from a fresh output directory for each repeat. The first assertion returns 1 under C1.

```bash
c1=/home/tongshu/acceptance/spatial_native_grid_20261107_6c3ad47
c2=/home/tongshu/acceptance/spatial_native_grid_20261107_22202ec
formal=/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source
old=/home/tongshu/acceptance/duel_comparison_20261106_43325b3/source/runs/duel_ppo_comparison_20261106/runs/a3/duel/data/rollout-00050-duel-g2.jsonl.gz
py=/home/tongshu/venv/bin/python
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1

cd "$c1/source"
export PYTHONPATH="$PWD:$formal/.extension"
"$py" -m unittest -v \
  tests.v5.test_spatial_native_grid.NativeSpatialGridTests.test_public_terrain_cells_recover_route_connectivity

cd "$c2/source"
export PYTHONPATH="$PWD:$formal/.extension"
"$py" -m unittest -v \
  tests.v5.test_spatial_native_grid tests.v5.test_spatial_position_readout \
  tests.v5.test_finite_score_identity tests.v5.test_reward_row_schema \
  tests.v5.test_candidate_provenance tests.v5.test_lite_policy_memory \
  tests.v5.test_replay_optimization tests.v5.test_ppo_rollout_read_once \
  tests.v5.test_learning_core.PolicyArchitectureTests tests.v5.test_learning_core.BatchTests

# Reserve one CPU slot for all six processes.
mkdir "$c1/evidence-repeat" "$c2/evidence-repeat"
for case in arena2 ruined_passage history; do
  for source in "$c1" "$c2"; do
    cd "$source/source"
    export PYTHONPATH="$PWD:$formal/.extension"
    "$py" verification/spatial_native_grid_20261107/probe.py \
      "$case" "$formal/runs/formal_30h_scratch" "$WESNOTH_RULES_DIR" "$old" \
      "../evidence-repeat/$case.json"
  done
done
```

The padding mutation used the exact tested C2 archive and replaced the first masked ReLU only in the running process.

```python
import inspect
import textwrap
import unittest
from learning import model
source = textwrap.dedent(inspect.getsource(model.Policy.encode_board))
mutated = source.replace('torch.relu(self.conv1(board)) * valid', 'torch.relu(self.conv1(board))')
assert mutated != source
namespace = {}
exec(mutated, vars(model), namespace)
model.Policy.encode_board = namespace['encode_board']
suite = unittest.defaultTestLoader.loadTestsFromName(
    'tests.v5.test_spatial_native_grid.NativeSpatialGridTests.test_padding_keeps_valid_convolution_readout_and_gradients')
raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
```
