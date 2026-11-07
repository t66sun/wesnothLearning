# Pinned v8 actor initialization for B3

Ubuntu `cpuServer`, 2026-11-07. [#275](https://github.com/t66sun/wesnothLearning/issues/275) · [Original #227 initializer](../duel_ppo_acceptance_20261107/REPORT.md)

The explicit weights-only BC branch initializes v10 from the original v8 duel actor. The copied checkpoint's hash and parent manifest are validated before the compatibility check. Only the `candidate_selection.version` field may differ, and it must be `work-12000-v8` in the v10 child. Checkpoint architecture and tensor shape remain strict. Ordinary resume and export still require the current feature schema. The child starts calibration with the existing seeded value-head reset, empty Adam and corpus, and fresh gates.

The exact original `last_bc.pt` with SHA256 `05908d7f972148ccc7b39b8df0cc00435e2176861654a632de44c379b94953ab` and parent manifest `6de9d81858c71c41de505db2c445bae5229fa8587db7a6d3d66d2ebc3eab3c88` initialized at seed `202611060`. The probe checked every actor tensor, independently recreated the seeded critic, inspected empty counters and optimizer state, and reopened the saved v10 child. Its collector raises if called. This is a startup check for the experimental B source. BC qualification and score measurements are separate. [Exact startup result](startup.json)

The unchanged strict v8 loader failed the new interrupted-child responsibility check with `checkpoint feature schema does not match this engine`. The changed source passed the check while its ordinary checkpoint validator still rejects the old feature identity. A total of 34 affected cases passed across the initial and asset-bound test invocations. The initial exact startup was rejected by the output-path guard and the first fixture invocation lacked frozen maps. The successful run used a fresh child inside the shipped source root and linked the original maps read-only. [Red](red.log) · [Path guard](outside-output.log) · [Initial fixtures](initial-fixtures.log.gz) · [Asset-bound fixtures](bound-fixtures.log)

| Purpose | Shipped commit | Archive SHA256 | Fresh directory under `/home/tongshu/acceptance/` |
| --- | --- | --- | --- |
| Strict loader red | `2c826fc67518140cf428fe605260fb305454c9d8` | `e2d3109e8f17050dd62edb88c4f74455de7f6d811fc31a28c775e25bf0e29db1` | `candidate_actor_red_20261107` |
| v10 weights-only startup | `6dffe54ff3c8810a668a5c8e5992b62f4c1e7b5c` | `bb298a3f251b75def68a19dc6eca4367a67252e3d85006cf34e324dccfe8f70f` | `candidate_actor_green_20261107` |

Rules SHA256 `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`. Both committed archives use the original v6 extension SHA256 `56dd77140411db987377d6de4ffbf562da4d0e5c76bc16d34780da67e60e5ae4`. Use the source-specific root on `PYTHONPATH` and the same frozen parent when reproducing.

```bash
formal=/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source
export PYTHONPATH="$PWD:$formal/.extension:$PWD/vendor/arena"
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
python=/home/tongshu/venv/bin/python
mkdir -p data/rules/1.18.8
ln -s "$formal/data/rules/1.18.8/maps" data/rules/1.18.8/maps
"$python" verification/candidate_actor_transfer_20261107/startup.py \
  "$formal/runs/formal_30h_scratch" "$PWD/runs/startup_actor_new"
"$python" -m unittest tests.v5.test_finite_score_identity tests.v5.test_checkpoint_ops \
  tests.v5.test_branch_restart_bc tests.v5.test_training_failure_fixes -v
```
