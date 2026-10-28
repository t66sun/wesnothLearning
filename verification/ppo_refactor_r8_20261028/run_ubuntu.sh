#!/usr/bin/env bash
set -euo pipefail
archive=/tmp/wesnoth-r8-20261028.tar
root=/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r8_20261028_a
python=/home/tongshu/venv/bin/python
wesnoth=/home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth
printf '%s  %s\n' "$1" "$archive" | sha256sum -c -
test ! -e "$root"
mkdir -p "$root/source" "$root/logs"
tar -xf "$archive" -C "$root/source"
cd "$root/source"
ln -s /home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source/data data
export PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
{
    uname -sr
    "$python" -c 'import sys,torch; print(sys.version); print(torch.__version__)'
    "$wesnoth" --simple-version
    sha256sum "$wesnoth" data/rules/1.18.8-training/rules.json
    cat SOURCE_REVISION
} > "$root/logs/environment.log" 2>&1
"$python" -m unittest tests.v5.test_native_capture tests.v5.test_teacher_identity tests.v5.test_reward_row_schema -v > "$root/logs/targeted.log" 2>&1
"$python" verification/ppo_refactor_r8_20261028/native_probe.py "$root/fixture" "$wesnoth" > "$root/logs/native.log" 2>&1
echo 'targeted and native fixture completed'
