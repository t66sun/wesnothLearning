#!/usr/bin/env bash
set -eu -o pipefail
here=$(cd "$(dirname "$0")" && pwd)
base=/home/tongshu/acceptance
source_tree=$base/ppo306_20261108_Miwoyq/source
old=$base/ppo-mode-interaction-20261115-sgUXX6/verification
extension=/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension
export WESNOTH_RULES_DIR=$base/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTHONPATH="$source_tree:$extension:$old/ppo_mode_interaction_20261115:$old/ppo_diag_capture_20261115:$old/ppo_diagnosis_20261115:$here/../ppo_mode_interaction_result_20261115"
cd "$source_tree"
exec timeout --kill-after=5s 2700 /home/tongshu/venv/bin/python -u "$here/replicate.py" "$@"
