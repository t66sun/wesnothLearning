#!/bin/bash
cd /home/tongshu/myDev/wesnothLearning/formal_run_20261028_r2
export PYTHONPATH=/home/tongshu/myDev/wesnothLearning/formal_run_20261028_r2
export PATH=/home/tongshu/.cargo/bin:$PATH
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
exec /home/tongshu/venv/bin/python -u -m learning run --run-dir runs/v5_stock30h_20261028_r2 --engine lite --evaluation-engine native --bc-games 400 400 400 --native-bc-games 0 0 0 --device cpu --workers 8 --trainer-threads 1 --hours 30 --final-holdout-hours 4 --seed 20261028 --formats duel ffa4 team2v2 --human-data /home/tongshu/myDev/wesnothLearning/formal_run_20261028_r2/empty_human --wesnoth /home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth
