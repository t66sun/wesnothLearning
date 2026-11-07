# Independent BC qualification preflight

Part of [#272](https://github.com/t66sun/wesnothLearning/issues/272) and [#269](https://github.com/t66sun/wesnothLearning/issues/269). The shared launch attempts both BC qualifications in the frozen order. A clean unqualified BC phase or an owned stage deadline leaves the route ineligible. The driver retains the gate and stage outcome, omits that route from the fixed PPO and panel order, and preserves the original caps for eligible routes. Both panel reports name the unqualified route and its reason. An otherwise observed group with a BC shortfall reports `incomplete_bc` and exits nonzero. Trainer and identity failures still fail the launch.

On `cpuServer`, one zero-game fixture passed in 0.017 s from commit `fcced78a7dc6fe5862096ac71f7921b96fa13228`. It simulated a clean B gate shortfall, an owned B deadline and a B trainer failure. The ordinary cases kept the original A/base and C cells, both matched panels and their contrasts. The failure case stopped the launch before C qualification. The fixture mocks training, process and panel workers.

The source archive SHA-256 was `4322f1eccaf85e2c78c71f6ef38e5c9c269474bb526a5ec87da1c754e67a26ef`. A one-file overlay from `63198caa2cda84b226becf124c85d2617831776d` restored the launch-aborting gate behavior. Its archive SHA-256 was `2281959bae6236b4781d4be5c1fbe30af95310774baaf7adb413b7ef097cfd2e`. Both hashes passed before extraction. The reverted fixture failed at the ordinary gate case with `AssertionError: 'incomplete' != 'incomplete_bc'`.

```sh
cd /home/tongshu/acceptance/ppo_bc_qualification_20261107_fcced78
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export PYTHONPATH=/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
python=/home/tongshu/venv/bin/python
fixture=verification.ppo_batch_comparison_20261107.test_qualification
(cd red && "$python" -m unittest -v "$fixture") > red.log 2>&1
(cd green && "$python" -m unittest -v "$fixture") > green.log 2>&1
```

The frozen comparison protocol and earlier preflight evidence remain at their original revisions. This fixture ran no games, collection, training, or panel evaluation.
