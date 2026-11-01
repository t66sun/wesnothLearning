set -eu
root=/home/tongshu/acceptance/training_turn_opening_20261102
mkdir "$root"
tar -xf "$root.tar" -C "$root"
cd "$root"
ln -s /home/tongshu/myDev/wesnothLearning/WesnothLearning/rules data/rules
export OMP_NUM_THREADS=1
export PYTHONPATH=/home/tongshu/acceptance/retaliation_fixed_20261102/.extension:/home/tongshu/acceptance/training_turn_contract_20261102:/home/tongshu/acceptance/training_turn_contract_20261102/vendor/arena
set +e
timeout 180 /home/tongshu/venv/bin/python -u tests/v5/test_training_turn_limit.py TrainingTurnLimitTests.test_opening_probe_keeps_its_five_turn_limit -v > opening_red.log 2>&1
printf '%s\n' "$?" > opening_red.exit
export PYTHONPATH=/home/tongshu/acceptance/retaliation_fixed_20261102/.extension:.:vendor/arena
timeout 180 /home/tongshu/venv/bin/python -u -m unittest tests.v5.test_training_turn_limit tests.v5.test_scenario_identity tests.v5.test_lite_default tests.v5.test_teacher_factions tests.v5.test_evaluation_design tests.test_experiment tests.test_worker_limit tests.v5.test_final_budget tests.test_validation_cadence -v > tests.log 2>&1
result=$?
printf '%s\n' "$result" > tests.exit
cat opening_red.log
tail -8 tests.log
sha256sum data/rules/1.18.8-training/rules.json /home/tongshu/acceptance/retaliation_fixed_20261102/.extension/_engine_lite.so > identities.txt
exit "$result"
