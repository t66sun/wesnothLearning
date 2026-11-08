# PPO terminal-return comparison

[#306](https://github.com/t66sun/wesnothLearning/issues/306) compares λ=1.0 with λ=0.95 on Lite duel `official-score-30-v1`. The six cells start from the same qualified [#227 BC](../duel_ppo_acceptance_20261107/REPORT.md), with independent Adam resets. Each pair uses the same fixed Astra, 8-game ordinal stream, rules, candidates, encoder, fixed reward coefficients, historical-action CE and KL 0.02. The seed order is 202611081, 202611082, 202611083. The challenge arm runs first in pairs one and three. The baseline runs first in pair two.

## Frozen launch

- Extract a committed Git archive in a fresh Ubuntu directory. Provision the same filtered rules, 1.18.8 map inventory and Lite extension as #227/#269. Run the driver's `prepare` command. It records the source archive, runtime, exact BC and Astra identities, full training config, map hashes and disk headroom in `launch.json` before `run` can start.
- Each PPO cell has 14,400 seconds. The first 14,100 seconds admit new eight-game batches. The last 300 seconds let pending work settle. Six cells have 86,400 seconds combined. Preparation, validation, holdout and reporting have caps of 1,800, 3,600, 12,600 and 3,600 seconds. The absolute cap is 108,000 seconds from input preparation. Inter-cell settlement records count against reporting.
- Den of Onis and Fallenstar Lake are the physical holdout boards. Verify the frozen native 1.18.8 assets against the distribution inventory and exclude all training, validation, initialization and previously used holdout boards by physical hash. Use #269's 30 ordered nonmirror faction pairs with both seat rotations on each board. Validation uses the 15-block Hamlets panel. Freeze the last in-budget settled checkpoint for each cell and the common BC before evaluation. Exact equal-weight roles share actual games.

## Report

Compare `λ=1.0 − λ=0.95` and each PPO arm against shared BC using normalized official score. Reuse the crossed 10,000-draw paired bootstrap from #269, with training seeds crossed with paired scenario draws within each map. Report each seed and map, actual games, 95% intervals, phase use, settled and pending batches, endpoint hashes, fresh decisions per PPO hour, and committed and rejected visits. The challenge is an adoption candidate only when both lower bounds against baseline and BC exceed zero. An interval crossing zero leaves the gain unconfirmed. Missing required samples or a short budget makes the comparison incomplete. The scope is the two Lite holdout maps.

The [driver](driver.py) records every cell's first complete eight-game batch, including the sampled λ and its use in the actual update. For λ=1 it checks the shaped return and advantage against the task-terminal formula. The [Ubuntu implementation checks](../ppo_gae_lambda_20261108/REPORT.md) cover pending-batch recovery.
