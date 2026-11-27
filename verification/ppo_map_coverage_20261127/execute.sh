#!/usr/bin/env bash
set -eu -o pipefail
here=$(cd "$(dirname "$0")" && pwd)
b=/home/tongshu/acceptance
p=$b/ppo306_20261108_Miwoyq/source
ext=/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension
export PYTHONPATH="$p:$ext:$b/ppo-v38-20261115-8dIsba/adapter/verification/ppo_vs_bc_20261115:$here/../ppo_diagnosis_20261115"
export WESNOTH_RULES_DIR=$b/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
cd "$p"
module=$1
shift
exec /home/tongshu/venv/bin/python -u "$here/$module.py" "$@"
