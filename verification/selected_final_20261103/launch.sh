set -eu
cd /home/tongshu/acceptance/selected_final_20261103
export WESNOTH_RULES_DIR=/home/tongshu/myDev/wesnothLearning/WesnothLearning/rules/1.18.8-training
export PYTHONPATH=.:vendor/arena OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
nohup bash -c '/home/tongshu/venv/bin/python -u -m tests.acceptance_selected_final /home/tongshu/myDev/wesnothLearning/acceptance_20261031_astra/src/runs/l1-20261031b/a/duel "$PWD/panel" ea449f711877b2966598fee1a014f488ad4d6f20; code=$?; echo "$code" > panel.exit; exit "$code"' </dev/null >panel.log 2>&1 &
echo $! > panel.pid
ps -p "$!" -o pid,stat,comm
