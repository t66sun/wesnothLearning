# Frozen PPO GAE lambda

[#305](https://github.com/t66sun/wesnothLearning/issues/305) accepts the configuration and recovery contract on Ubuntu. New runs freeze `config.gae_lambda` with default 0.95. An explicit BC branch retains its inherited reward settings and seeds the new reward controller with the branch's λ. Scheduled games stamp it into new rows. PPO's existing `advantages()` reads the row configuration, including when a pending update rereads its frozen shards.

## Observed results

- The real runner scheduled eight fixture games per batch and wrote eligible shards through the production writer. At λ=1, both natural victory and a complete round-30 draw gave `G_t = z − Φ(s_t)` and advantage `G_t − V_t` with unequal behavior values within each trajectory. λ=0.95 yielded different targets. A checkpoint interrupted after one optimizer step resumed under the original budget, collected zero replacement games, and matched the uninterrupted weights and counters. Existing Lite boundary checks exercised natural victory, round 30 and an earlier external cut with bootstrap.
- Forcing inherited λ back to 0.95 caused the λ=1 runner test to fail inside the actual PPO advantage call. [Reverted output](reverted.log)
- Both 8-game branches opened and resumed from the qualified #227 duel BC with identical actor/critic parameter digest `d9d694f04d4179a5c65bbc29307a8e425a245d650d47f55a36ec04abeb206801`, zero Adam states and the original budget. Admission was closed and the broker rejected any game request. [Startup output](startup.log)

## Reproduction

On `cpuServer`, Ubuntu 24.04.5 LTS, Linux 7.0.0-38-generic and Python 3.12.3, `git archive --format=tar.gz eb0df02927a4b8cb10af87cb01db0e15f95773ae` had SHA-256 `fe5aa4bc65fb4516cab136ff354244102bfc7a4ac709347cef7de37c475c89e5`. The green and reverted extractions were `~/acceptance/ppo305_20261108_eb0df02_green_SA1fRD` and `~/acceptance/ppo305_20261108_eb0df02_reverted_PFKRw4`. The provisioned rules digest was `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`.

```sh
mkdir -p data/rules
ln -s /home/tongshu/myDev/wesnothLearning/WesnothLearning/rules/1.18.8 data/rules/1.18.8
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export PYTHONPATH="$PWD:/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension"
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONHASHSEED=0
python=/home/tongshu/venv/bin/python
"$python" -m unittest -v tests.v5.test_ppo_gae_lambda tests.v5.test_finite_score \
    tests.v5.test_ppo_rollout_read_once verification.ppo_batch_contract_20261107.test_contract
```

The command passed 32 checks in 19.003 seconds. The first archive (`fb43016`) exposed a shared rehearsal RNG in the test fixture. The final fixture restores each arm's saved RNG before comparing updates. In the reverted extraction, setting `controller_state['config']['gae_lambda'] = .95` and running `tests.v5.test_ppo_gae_lambda.FrozenGaeTests.test_branch_rollout_targets_and_pending_resume` exited 1 at the λ assertion. [Passing output](green.log)

The [startup harness](startup_check.py), SHA-256 `856e51f3b10fe0eac69c6b78dbf56204108448e2ff0430b321c7a68cedd68387`, was copied beside the archive root. Run `"$python" -u startup_check.py "$HOME/acceptance/duel_comparison_20261106_43325b3/source/runs/duel_ppo_comparison_20261106" "$PWD/runs/ppo305-startup"` with the same environment. Both branches completed the check. Windows ran no tests. [#306](https://github.com/t66sun/wesnothLearning/issues/306) supplies the first live sampling and update observation and the paired strength result.
