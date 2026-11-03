# Prospective integrated run profile

Use the item 10 Ubuntu parent `/home/tongshu/acceptance/bc_v6_readiness_20261103/runs/bc_readiness`. The authorized starting inputs are its trained float32 model coefficients and compatible supervision. Pin its manifest SHA256 `32adc2420926f9dc9e2f88a5c2a4e35956d486f121dd94b970485b1f3244a9be` and all three latest checkpoint hashes against the original inventory. The initialization check found 152 eligible teacher and four DAgger shards. Preserve the same partition rules and record that the parent was selected using these validation families. The final holdout stays separate. [Parent input inventory](../bc_ordinary_v6_20261103/metadata/artifacts.json) · [Fresh initialization check](../bc_branch_restart_20261104/REPORT.md)

Start the new experiment with `--branch-from "$BOUNDED_BC_PARENT" --branch-restart-bc --branch-reset-optimizer --phase bc`. All three child formats start at calibration with a fresh optimizer, zero progress and an unearned gate. The existing single-Astra calibration path writes its control record. The ordinary corpus minimum is 24 per format, with the larger previous corpus identified as reused. Record the actual number of new BC steps and all ordinary gates. Validation runs every three committed model versions so that a short run with one BC and two PPO batches exercises periodic validation and final selection.

Freeze selection before the 420-game evaluation. Each of the two PPO requests uses `--ppo-batches 1`. Export audits every supplied current-run record with up to eight workers. The 37-candidate, recurrent-memory and `1e-5` numerical criteria apply to the actual export. Each stage retains the ceilings in the [original plan](PLAN.md).

From the fresh extraction on cpuServer, verify the source tar hash, matching compiled extension, teacher digest, current catalog hash and executable before launch. Use the committed driver for CLI arguments and state transitions. Record wall start, finish, process exit and stage JSON separately.

```sh
export PYTHONPATH="$PWD/.extension:$PWD:$PWD/vendor/arena"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
export BOUNDED_BC_PARENT=/home/tongshu/acceptance/bc_v6_readiness_20261103/runs/bc_readiness
export WESNOTH_EXE=/home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth
export SOURCE_COMMIT  # Set to the shipped commit before launching.
timeout --signal=TERM --kill-after=15s 3600 /home/tongshu/venv/bin/python -u tests/bounded_training_loop.py
```
