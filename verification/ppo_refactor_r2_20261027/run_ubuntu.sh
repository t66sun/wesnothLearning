#!/usr/bin/env bash
set -euo pipefail
archive=/tmp/wesnoth-r2-3a92436.tar
expected=$1
root=/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r2_20261027_3a92436
frozen=/home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source/data
python=/home/tongshu/venv/bin/python
test -f "$archive"
printf '%s  %s\n' "$expected" "$archive" | sha256sum -c -
test ! -e "$root"
test -f "$frozen/rules/1.18.8-training/catalog-summary.json"
test -x "$python"
mkdir -p "$root/source" "$root/logs"
tar -xf "$archive" -C "$root/source"
cd "$root/source"
ln -s "$frozen" data
export PYTHONPATH="$PWD"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTHONDONTWRITEBYTECODE=1
{
    uname -sr
    "$python" -c 'import sys,torch,_engine_lite; print(sys.version); print(torch.__version__); print(_engine_lite.__file__)'
    sha256sum data/rules/1.18.8-training/rules.json
    cat SOURCE_REVISION
} > "$root/logs/environment.log" 2>&1
files=(learning/updates.py learning/schedule.py learning/bc.py learning/ppo.py
       learning/manifest.py learning/experiment.py tests/v5/test_batch_eligibility.py)
sha256sum "${files[@]}" > "$root/logs/source_before.sha256"
set +e
"$python" -m unittest tests.v5.test_batch_eligibility tests.v5.test_ppo_resume_counters \
    tests.test_schedule tests.v5.test_bc_cancel_rng tests.test_opponents tests.v5.test_rollout_content_identity -v > "$root/logs/targeted.log" 2>&1
status=$?
set -e
printf 'targeted_exit=%s\n' "$status" | tee "$root/logs/status.log"
test "$status" -eq 0
cp learning/updates.py "$root/logs/fixed_updates.py"
cp baseline_updates.py learning/updates.py
set +e
"$python" -m unittest tests.v5.test_batch_eligibility.BatchEligibilityTests.test_validation_row_in_batch_raises \
    -v > "$root/logs/reverted.log" 2>&1
reverted=$?
set -e
cp "$root/logs/fixed_updates.py" learning/updates.py
printf 'reverted_exit=%s\n' "$reverted" | tee -a "$root/logs/status.log"
test "$reverted" -ne 0
"$python" -m unittest tests.v5.test_batch_eligibility.BatchEligibilityTests.test_validation_row_in_batch_raises \
    -v > "$root/logs/restored.log" 2>&1
printf 'restored_exit=0\n' | tee -a "$root/logs/status.log"
sha256sum "${files[@]}" > "$root/logs/source_after.sha256"
cmp "$root/logs/source_before.sha256" "$root/logs/source_after.sha256"
printf 'source_restored=1\n' | tee -a "$root/logs/status.log"
