#!/usr/bin/env bash
# Ubuntu acceptance for the R5 policy rehearsal opt-in.
# Usage: rerun_ubuntu.sh <source.tar> <expected-sha256-of-tar> [python]
set -euo pipefail
archive=$1
expected=$2
python=${3:-/home/tongshu/venv/bin/python}
commit=$(basename "$archive" .tar)
root=/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r5_policy_${commit}
printf '%s  %s\n' "$expected" "$archive" | sha256sum -c -
test ! -e "$root"
mkdir -p "$root/source" "$root/logs"
tar -xf "$archive" -C "$root/source"
cd "$root/source"
ln -s /home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source/data data
export PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
{
    uname -sr
    "$python" -c 'import sys,torch; print(sys.version); print(torch.__version__)'
    sha256sum data/rules/1.18.8-training/rules.json
    sha256sum learning/experiment.py tests/v5/test_rehearsal_source.py | tee "$root/logs/source_before.sha256"
} > "$root/logs/environment.log" 2>&1
sha256sum learning/experiment.py > "$root/logs/experiment_before.sha256"
"$python" -m unittest tests.v5.test_rehearsal_source -v > "$root/logs/rehearsal.log" 2>&1
"$python" -m unittest tests.v5.test_ppo_plan tests.test_validation_cadence tests.v5.test_rehearsal_source \
    > "$root/logs/related.log" 2>&1
"$python" -m py_compile learning/experiment.py tests/v5/test_rehearsal_source.py
"$python" verification/ppo_refactor_r5_policy_20261028/revert_windows.py > "$root/logs/revert.log" 2>&1
sha256sum -c "$root/logs/experiment_before.sha256" > "$root/logs/restored.log" 2>&1
printf 'targeted_exit=0\n' > "$root/logs/status.log"
printf 'root=%s\n' "$root"
