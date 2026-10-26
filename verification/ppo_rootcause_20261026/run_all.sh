#!/bin/sh
# Re-run every read-only diagnostic in order, logging each output and exit code.
set -u
FROZEN=/home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source
D=/home/tongshu/myDev/wesnothLearning/diag_ppo_20261026
RUN=$FROZEN/runs/v5_lite30h_20261025
cd "$FROZEN" || exit 99
export WL_SOURCE=$FROZEN
export WL_RUN=$RUN
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export WL_MAXFILES=24
PY=/home/tongshu/venv/bin/python
mkdir -p "$D/out"
run() {
    name=$1
    shift
    "$@" >"$D/out/$name.log" 2>&1
    echo "$name rc=$?"
}
run a_accounting "$PY" "$D/a_accounting.py"
run c_replay "$PY" "$D/c_parity.py" replay --format duel --version 99 --games 4 --limit 400
run c_grad "$PY" "$D/c_parity.py" grad --format duel --version 99 --games 4
run d_batch "$PY" "$D/d_batch.py" --format duel --version 99
run e_gradpath "$PY" "$D/e_gradpath.py" --format duel --version 99
run f_final "$PY" "$D/f_final_panel.py"
run g_independence "$PY" "$D/g_independence.py" independence
run g_trend "$PY" "$D/g_independence.py" trend
run h_reward "$PY" "$D/h_reward.py" --format duel --version 99
run i_drift "$PY" "$D/i_drift.py" --format duel --version 99
run j_prefix "$PY" "$D/j_prefix.py" --format duel --version 99
