#!/usr/bin/env bash
set -euo pipefail
archive=/tmp/wesnoth-r6-30cd046.tar
root=/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r6_20261027_30cd046
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
    sha256sum data/rules/1.18.8-training/rules.json baseline_data.py
    cat SOURCE_REVISION
} > "$root/logs/environment.log" 2>&1
files=(learning/data.py learning/rewards.py learning/reward_metrics.py learning/rowpack.py
       learning/sequences.py learning/updates.py learning/manifest.py tests/v5/test_reward_row_schema.py tests/test_opponents.py)
sha256sum "${files[@]}" > "$root/logs/source_before.sha256"
"$python" -m unittest tests.v5.test_reward_row_schema tests.v5.test_learning_core.RewardTests \
    tests.v5.test_pipeline_contract.RewardMetricsTests tests.test_rowpack tests.v5.test_scenario_identity \
    tests.test_opponents tests.v5.test_pipeline_contract.LiteJobTests.test_policy_actor_input_excludes_teacher_and_reward_fields \
    tests.v5.test_collection_memory.CollectionMemoryTests.test_real_collector_compacts_before_write_without_changing_output \
    -v > "$root/logs/targeted.log" 2>&1
printf 'targeted_exit=0\n' > "$root/logs/status.log"
"$python" frozen_parity.py > "$root/logs/frozen_parity.log" 2>&1
printf 'frozen_parity_exit=0\n' >> "$root/logs/status.log"
cp learning/data.py "$root/logs/fixed_data.py"
cp baseline_data.py learning/data.py
set +e
"$python" -m unittest tests.v5.test_reward_row_schema.RewardRowSchemaTests.test_row_reward_is_not_the_terminal_value -v > "$root/logs/reverted.log" 2>&1
reverted=$?
set -e
cp "$root/logs/fixed_data.py" learning/data.py
printf 'reverted_exit=%s\n' "$reverted" >> "$root/logs/status.log"
test "$reverted" -ne 0
"$python" -m unittest tests.v5.test_reward_row_schema.RewardRowSchemaTests.test_row_reward_is_not_the_terminal_value -v > "$root/logs/restored.log" 2>&1
printf 'restored_exit=0\n' >> "$root/logs/status.log"
sha256sum "${files[@]}" > "$root/logs/source_after.sha256"
cmp "$root/logs/source_before.sha256" "$root/logs/source_after.sha256"
printf 'source_restored=1\n' >> "$root/logs/status.log"
cat "$root/logs/status.log"
tail -n 5 "$root/logs/targeted.log"
