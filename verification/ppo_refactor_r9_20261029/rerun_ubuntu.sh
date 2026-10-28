#!/usr/bin/env bash
set -euo pipefail
archive=/tmp/wesnoth-r9.tar
root=/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r9b_20261029
python=/home/tongshu/venv/bin/python
wesnoth=/home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth
canonical_capture=26d2894a09ccc66e5d7274d684644815d659d56b0110b0f0d22a83eb0e539557
printf '%s  %s\n' "$1" "$archive" | sha256sum -c -
test ! -e "$root"
mkdir -p "$root/source" "$root/logs"
tar -xf "$archive" -C "$root/source"
cd "$root/source"
ln -s /home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source/data data
export PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
gcc -O2 -Wall -shared -fPIC -o "$root/deterministic_entropy.so" \
    verification/ppo_refactor_r8_20261028/deterministic_entropy.c -ldl
export LD_PRELOAD="$root/deterministic_entropy.so"
{
    uname -sr
    "$python" -c 'import sys,torch; print(sys.version); print(torch.__version__)'
    "$wesnoth" --simple-version
    sha256sum "$wesnoth" data/rules/1.18.8-training/rules.json
    sha256sum "$root/deterministic_entropy.so"
    cat SOURCE_REVISION
} > "$root/logs/environment.log" 2>&1
"$python" -m unittest tests.v5.test_teacher_protocol tests.v5.test_teacher_identity tests.v5.test_native_capture tests.v5.test_reward_row_schema -v > "$root/logs/targeted.log" 2>&1
"$python" verification/ppo_refactor_r9_20261029/stock_bc_probe.py "$root/probe" "$wesnoth" > "$root/logs/probe.log" 2>&1
"$python" - "$root/probe/probe.json" "$canonical_capture" <<'PY' > "$root/logs/identity.log" 2>&1
import json, sys
probe = json.load(open(sys.argv[1]))
assert probe['status'] == 'passed', probe
assert probe['rows'] > 0, probe
assert probe['capture_sha256'] == sys.argv[2], probe['capture_sha256']
assert probe['teacher_query'] == 'none', probe
assert probe['dagger_status'] == 'unsupported_with_stock_rca', probe
assert probe['stock_capture'] == [1, 2], probe
assert set(probe['bots']) == {'baseline'}, probe
print('rows', probe['rows'], 'seed', probe['seed'], 'kinds', probe['kinds'])
print('capture_sha256', probe['capture_sha256'])
PY
echo 'targeted and stock teacher game completed'
