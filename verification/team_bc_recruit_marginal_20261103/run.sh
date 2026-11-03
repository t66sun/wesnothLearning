#!/usr/bin/env bash
set -euo pipefail
root=$(cd "$(dirname "$0")/../.." && pwd)
runtime=/home/tongshu/acceptance/team_bc_branch_20261102
stage="$root/verification/team_bc_recruit_marginal_20261103"
export PYTHONPATH="/home/tongshu/acceptance/team_bc_v2_20261102/.extension:$runtime:$runtime/vendor/arena"
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
cd "$runtime"
echo "wrapper_pid=$$ source=$root"
date -u
set +e
timeout --signal=TERM --kill-after=10 1500 /home/tongshu/venv/bin/python -B -u "$stage/probe.py" 2>&1 | tee "$stage/console.log"
status=${PIPESTATUS[0]}
set -e
date -u
echo "$status" > "$stage/exit_code"
exit "$status"
