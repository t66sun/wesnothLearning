#!/bin/sh
# Reproduce the BC-gate scenario-coverage probe (D9).
#
# Read-only: reads <run>/<format>/data/teacher-*.jsonl.gz and nothing else.
# Requires the frozen training source on PYTHONPATH-provided WL_SOURCE.
set -u
FROZEN=${FROZEN:-/home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source}
RUN=${RUN:-$FROZEN/runs/v5_lite30h_20261025}
D=${D:-/home/tongshu/myDev/wesnothLearning/diag_ppo_20261026}
PY=${PY:-/home/tongshu/venv/bin/python}
export WL_SOURCE="$FROZEN" WL_RUN="$RUN"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
mkdir -p "$D/out"

run() {
    name=$1
    shift
    ( cd "$FROZEN" && "$@" ) >"$D/out/$name.log" 2>&1
    rc=$?
    echo "$name rc=$rc"
    tail -10 "$D/out/$name.log"
}

# Command 1: complete duel corpus, ~60 s.
run gate_duel timeout 240 "$PY" "$D/k_gate_scope.py" --format duel

# Commands 2-3: bounded prefixes; the full 608/400-shard scans exceed the
# per-command budget and are recorded as not run to completion.
run gate_ffa4 timeout 150 "$PY" "$D/k_gate_scope.py" --format ffa4 --maxfiles 40
run gate_team2v2 timeout 150 "$PY" "$D/k_gate_scope.py" --format team2v2 --maxfiles 40
