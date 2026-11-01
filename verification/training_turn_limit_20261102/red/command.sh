set -eu
root=/home/tongshu/acceptance/training_turn_red_20261102
mkdir "$root"
tar -xf "$root.tar" -C "$root"
cd "$root"
ln -s /home/tongshu/myDev/wesnothLearning/WesnothLearning/rules data/rules
export PYTHONPATH=/home/tongshu/acceptance/retaliation_fixed_20261102/.extension:.:vendor/arena
export OMP_NUM_THREADS=1
set +e
timeout 180 /home/tongshu/venv/bin/python -u -m unittest tests.v5.test_training_turn_limit -v > tests.log 2>&1
result=$?
printf '%s\n' "$result" > tests.exit
tail -65 tests.log
exit "$result"
