# Driver boundary preflight

[PPO-A3 #272](https://github.com/t66sun/wesnothLearning/issues/272) uses the shared [protocol](PROTOCOL.md). This check covers evidence recording at the wall-clock and fresh-decision boundaries. The #271 tests already cover rollout ordinals, complete-batch admission and recovery of the production update.

Ubuntu on `cpuServer` ran one focused fixture from commit `b6fdaf5af23e069f70c74edb318fe5479e724a3f`. The verified source archive SHA-256 was `2083df26e6526ae956017f3c0a2636a756ecd908111db56f3fe1d74f81666457`. Linux was 7.0.0-38-generic x86_64 and Python was 3.12.3.

| Check | Result |
| --- | --- |
| Current source | One test passed in 0.009 s. The fixture checks both exact threshold crossings, continued admission after 30k, admission cutoff, and the checkpoint retained across a partial update and a late settlement. The 10k crossing is a zero-step KL rejection. |
| Hard cutoff removed | One test failed at the expected late-checkpoint assertion. The reverted fixture retained `outside budget` where `last settled tail` was required. |
| Driver help | Imported the driver and displayed the `run` and `stage` entry points. |

The reverted archive contained only `arm.py` from commit `9285eed8bd086de7aeb703247f8f422c5881f809`, SHA-256 `d2150ebca5a3248af854159df07ac51fd717766144e10a718d62c96c58fe0971`. It removed only the check of settlement time against the hard deadline. The same original archive was extracted into `green` and `red`, then the one-file archive overlaid `red`. Both archive hashes passed before extraction.

```sh
cd /home/tongshu/acceptance/ppo_batch_comparison_20261107_b6fdaf5
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export PYTHONPATH=/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
python=/home/tongshu/venv/bin/python
fixture=verification.ppo_batch_comparison_20261107.test_boundary
(cd red && "$python" -m unittest -v "$fixture") > red.log 2>&1
(cd green && "$python" -m unittest -v "$fixture") > green.log 2>&1
(cd green && "$python" -m verification.ppo_batch_comparison_20261107.driver --help) > driver-help.log 2>&1
```

The wrapper's final display command inherited a trailing carriage return and exited 1 after the fixture commands. A separate read verified the saved help log. The test fixture exercised simulated settlements. No games, collection, training, panel evaluation, or local Windows tests ran. The first real A8 batch and the remaining execution evidence belong to the authorized shared launch.
