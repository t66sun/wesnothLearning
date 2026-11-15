# PPO over qualified v38 BC score-only freeze

#348 completed on cpuServer on 2026-11-15. The preflight and four synthetic checks passed. This preparation started zero games and zero training updates. #349 requires separate authorization for this launch SHA-256.

## Frozen identities

| Artifact | SHA-256 |
| --- | --- |
| [Launch](launch.json) | `3ff17a173aa6af898aead3564d8d466e5ffa7dcdec9481125c01e47130c7da50` |
| [Schedule](schedule.json.gz) decompressed | `ebd3b3c16273f98919a1688e5e38168eb2c123821ebc1e2456625612d7549fe0` |
| Schedule gzip | `417e904c1204d93a3fdd1d122d421f1c284d662556efe06366a6a976be7d791b` |
| [Lineage audit](lineage.json) | `79b84fd9322e4e804b4e05f81f4f7cdbaffa78b47e5f1b4e24aeffd8b326233b` |
| Git adapter archive | `61d016db1317736de9ff3600b6aa084089da9e02c48c7d13abf432419a7eb608` |
| #306 source archive | `240009bf8a55096203d548d4ee349c2e34d574927ff2325c30ef08ef4aef69d2` |
| Lite extension | `56dd77140411db987377d6de4ffbf562da4d0e5c76bc16d34780da67e60e5ae4` |
| 1.18.8-combat-filtered rules | `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17` |
| Astra parent | `2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933` |

The adapter was shipped at commit `d935d5c5e2a50b49e3b2e9a7e3f6a35ea7a0275a` with the three archived maps. The evaluator matched 146 source files from #306 commit `68fbf6b0b087b196526c674f28baffbfae3eb8c4`. The launch records the archive paths, Astra teacher source and profile, each checkpoint's parameter digest, and the four greedy export file trees.

| Role | Checkpoint SHA-256 | PPO wall seconds | Fresh PPO targets |
| --- | --- | ---: | ---: |
| Qualified v38 | `8fc61bbb0be5c2ad8d2ec5b56760ce3dbfa08eed008c490e9b2233624ea91ebe` | | |
| λ=0.95 seed 202611081 | `a00d02fc88523ec82a424ce5eb6436a1133013e7f18a56838ddb3ef4745f4a05` | 14,118.7 | 146,912 |
| λ=0.95 seed 202611082 | `3e6e8efea9da962cd1096b95db30edae14f8522a4c59402e92d5597a06c03a5c` | 14,127.4 | 147,193 |
| λ=0.95 seed 202611083 | `1001f23625924cb96a2a9c9e27cda37a7832d9f0b7b9b8f799c019dc261c728f` | 14,138.9 | 149,719 |

The BC manifest and all recorded qualification gates matched. All three PPO cells reset Adam, started from the same BC parameters and finished with settled training and validation. The seed 202611082 wall checkpoint retained the validation marker present at serialization. The final state has the same batch, version and PPO history, and the validation is settled, as recorded by the original #306 audit.

## Boards and score

| Board | Dimensions | Villages | Physical SHA-256 |
| --- | --- | ---: | --- |
| Fallenstar Lake | 41 × 22 | 20 | `2f9037f75f58c917343aa4cbc82ba48d27d7a8120b1244893012773da307180d` |
| Sulla's Ruins | 35 × 30 | 16 | `47e311d38e3630d29cff7e8f05e75d1e23720819083c3c1ca7fe6d98529cd958` |
| Ur-Thorodor | 38 × 23 | 10 | `82ec08e3de336b17d6dbd675f4881d200f8b1f038a71cd74c736bd738f5d0fb0` |

Fallenstar Lake and Sulla's Ruins each retain two recorded `Mm^Vhh` to `Hh^Vhh` substitutions. Ur-Thorodor has no substitutions. The preflight verified two playable starting leaders for each of the 180 board, roster and seat arrangements. The recorded exposure audit covered 2,308 archived schedules and 16,128 planned jobs across the initializer, v38, #306 cells, validation and both previous #306 holdouts, plus matched shard audits. The three physical layouts and all 90 combat seeds cleared the corresponding historical exclusions.

The frozen schedule has 90 scenario blocks, 180 paired slots and 720 unique games against the same Astra under `official-score-30-v1`. Seeds 2026111600–2026111689 are shared across roles and seats within block. The official normalized score awards 3/1/0 points to wins/draws/losses and uses one observed BC game per slot. Maps and PPO training histories receive equal weight. The paired 95% interval uses 10,000 crossed resamples with seed 2026111699.

A complete run passes at a point estimate of at least +5 pp and a 95% lower bound strictly above zero. An upper bound strictly below +5 pp excludes the useful gain for this panel. Other complete results are inconclusive. A failed validity check or missed deadline makes the run incomplete. The estimate applies to Lite score against frozen Astra on these three boards for the three archived continuations of this BC initializer.

## Ubuntu commands

Preparation ran `driver.py prepare "$root/formal" --adapter-archive "$root/adapter.tar" --commit d935d5c5e2a50b49e3b2e9a7e3f6a35ea7a0275a` and `test_panel.py "$root/formal/schedule.json"` with the environment below. The [preparation](prepare.log), [synthetic results](synthetic.log), and [read-only launch preflight](no-game-preflight.log) record the results.

After authorization, start one eight-worker run with a continuous 120-minute limit. It has up to 15 minutes for launch checks, 90 minutes for games and 15 minutes for recount and archive.

```bash
set -eu -o pipefail
root=/home/tongshu/acceptance/ppo-v38-20261115-8dIsba
source=/home/tongshu/acceptance/ppo306_20261108_Miwoyq/source
cd "$source"
export PYTHONPATH="$PWD:/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension"
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
scripts="$root/adapter/verification/ppo_vs_bc_20261115"
python=/home/tongshu/venv/bin/python
"$python" -u "$scripts/driver.py" run "$root/formal" --launch-sha256 3ff17a173aa6af898aead3564d8d466e5ffa7dcdec9481125c01e47130c7da50
```
