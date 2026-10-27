#!/usr/bin/env bash
set -euo pipefail
archive=/tmp/wesnoth-r4-a05533f.tar
root=/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r4_20261027_a05533f
python=/home/tongshu/venv/bin/python
printf '%s  %s\n' "$1" "$archive" | sha256sum -c -
test ! -e "$root"
mkdir -p "$root/source" "$root/logs"
tar -xf "$archive" -C "$root/source"
cd "$root/source"
ln -s /home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source/data data
export PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
{
    uname -sr
    "$python" -c 'import sys,torch,_engine_lite; print(sys.version); print(torch.__version__); print(_engine_lite.__file__)'
    sha256sum data/rules/1.18.8-training/rules.json
    cat SOURCE_REVISION
} > "$root/logs/environment.log" 2>&1
files=(learning/evaluate.py learning/experiment.py learning/schedule.py learning/selection.py learning/report.py
       tests/v5/test_evaluation_design.py tests/test_schedule.py tests/v5/test_final_nomination.py
       tests/v5/test_selection.py tests/v5/test_final_budget.py)
sha256sum "${files[@]}" > "$root/logs/source_before.sha256"
"$python" -m unittest tests.v5.test_evaluation_design tests.test_validation_cadence tests.test_schedule \
    tests.v5.test_selection tests.v5.test_final_nomination tests.v5.test_final_budget -v > "$root/logs/targeted.log" 2>&1
printf 'targeted_exit=0\n' > "$root/logs/status.log"
cp learning/evaluate.py "$root/logs/fixed_evaluate.py"
cp learning/experiment.py "$root/logs/fixed_experiment.py"
cp baseline_evaluate.py learning/evaluate.py
set +e
"$python" -m unittest tests.v5.test_evaluation_design.EvaluationDesignTests.test_repeated_identical_blocks_are_insufficient -v > "$root/logs/reverted.log" 2>&1
panel_reverted=$?
set -e
cp "$root/logs/fixed_evaluate.py" learning/evaluate.py
cp baseline_experiment.py learning/experiment.py
set +e
"$python" -m unittest tests.v5.test_evaluation_design.EvaluationDesignTests.test_gate_reports_distinct_scenarios -v > "$root/logs/gate_reverted.log" 2>&1
gate_reverted=$?
set -e
cp "$root/logs/fixed_experiment.py" learning/experiment.py
printf 'panel_reverted_exit=%s\ngate_reverted_exit=%s\n' "$panel_reverted" "$gate_reverted" >> "$root/logs/status.log"
test "$panel_reverted" -ne 0
test "$gate_reverted" -ne 0
"$python" -m unittest tests.v5.test_evaluation_design.EvaluationDesignTests.test_repeated_identical_blocks_are_insufficient \
    tests.v5.test_evaluation_design.EvaluationDesignTests.test_gate_reports_distinct_scenarios -v > "$root/logs/restored.log" 2>&1
printf 'restored_exit=0\n' >> "$root/logs/status.log"
sha256sum "${files[@]}" > "$root/logs/source_after.sha256"
cmp "$root/logs/source_before.sha256" "$root/logs/source_after.sha256"
printf 'source_restored=1\n' >> "$root/logs/status.log"
cat "$root/logs/status.log"
tail -n 5 "$root/logs/targeted.log"
