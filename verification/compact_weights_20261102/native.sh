set -eu
root=/home/tongshu/acceptance/compact_weights_fixed_20261102
cd "$root"
export PYTHONPATH=/home/tongshu/acceptance/retaliation_fixed_20261102/.extension:.:vendor/arena
export OMP_NUM_THREADS=1
mkdir -p .runtime
cc -O2 -fPIC -shared -o .runtime/entropy.so vendor/arena/entropy.c -ldl
sha256sum .runtime/entropy.so data/rules/1.18.8-training/rules.json > native_identities.log
set +e
/usr/bin/time -p timeout --signal=TERM --kill-after=10 900 /home/tongshu/venv/bin/python -u check_native.py "$root" "$root/native" /home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth 2542e8dfa971f5063d12ac109c4942c67ea7f3a5 > native.log 2>&1
result=$?
printf 'EXIT=%s\n' "$result" >> native.log
tail -12 native.log
exit "$result"
