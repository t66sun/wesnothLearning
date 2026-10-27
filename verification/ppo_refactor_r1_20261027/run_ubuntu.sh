#!/usr/bin/env bash
set -euo pipefail
archive=/tmp/wesnoth-r1-be0a1ca.tar
expected=$1
root=/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r1_20261027_be0a1ca
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
files=(learning/maps.py learning/data.py learning/sequences.py learning/updates.py
       learning/lite_host.py learning/sample.py learning/experiment.py
       tests/v5/test_scenario_identity.py tests/v5/test_bc_fill.py)
sha256sum "${files[@]}" > "$root/logs/source_before.sha256"
set +e
"$python" -m unittest tests.v5.test_scenario_identity tests.v5.test_rollout_content_identity \
    tests.test_schedule tests.v5.test_bc_fill -v > "$root/logs/targeted.log" 2>&1
status=$?
set -e
printf 'targeted_exit=%s\n' "$status" | tee "$root/logs/status.log"
test "$status" -eq 0
cp learning/maps.py "$root/logs/fixed_maps.py"
cp baseline_maps.py learning/maps.py
set +e
"$python" -m unittest tests.v5.test_scenario_identity.ScenarioIdentityTests.test_seed_does_not_move_the_scenario_between_splits \
    -v > "$root/logs/reverted.log" 2>&1
reverted=$?
set -e
cp "$root/logs/fixed_maps.py" learning/maps.py
printf 'reverted_exit=%s\n' "$reverted" | tee -a "$root/logs/status.log"
test "$reverted" -ne 0
"$python" -m unittest tests.v5.test_scenario_identity.ScenarioIdentityTests.test_seed_does_not_move_the_scenario_between_splits \
    -v > "$root/logs/restored.log" 2>&1
printf 'restored_exit=0\n' | tee -a "$root/logs/status.log"
sha256sum "${files[@]}" > "$root/logs/source_after.sha256"
cmp "$root/logs/source_before.sha256" "$root/logs/source_after.sha256"
printf 'source_restored=1\n' | tee -a "$root/logs/status.log"
