set -eu
root=/home/tongshu/acceptance/training_turn_contract_20261102
mkdir "$root"
tar -xf "$root.tar" -C "$root"
cd "$root"
ln -s /home/tongshu/myDev/wesnothLearning/WesnothLearning/rules data/rules
export PYTHONPATH=/home/tongshu/acceptance/retaliation_fixed_20261102/.extension:.:vendor/arena
export OMP_NUM_THREADS=1
set +e
timeout 180 /home/tongshu/venv/bin/python -u -m unittest tests.v5.test_training_turn_limit.TrainingTurnLimitTests.test_resume_restores_frozen_limit tests.v5.test_lite_default.LiteDefaultTests.test_lite_final_evaluation_has_only_astra_controls tests.v5.test_lite_default.LiteDefaultTests.test_resume_keeps_frozen_targets_workers_and_deadline -v > tests.log 2>&1
result=$?
printf '%s\n' "$result" > tests.exit
tail -65 tests.log
exit "$result"
