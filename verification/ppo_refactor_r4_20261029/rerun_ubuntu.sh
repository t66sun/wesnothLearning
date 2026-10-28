#!/usr/bin/env bash
# R4 acceptance: planned schedules reach the declared distinct-scenario floors.
set -euo pipefail
archive=${1:?source archive}
expected=${2:?archive sha256}
root=${3:-/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r4_20261029}
data=/home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source/data
python=/home/tongshu/venv/bin/python

actual=$(sha256sum "$archive" | cut -d' ' -f1)
test "$actual" = "$expected" || { echo "archive sha mismatch: $actual"; exit 1; }
test ! -e "$root" || { echo "refusing to reuse $root"; exit 1; }
mkdir -p "$root"
tar -xf "$archive" -C "$root"
rm -rf "$root/data"
ln -s "$data" "$root/data"
mkdir -p "$root/logs"

cd "$root"
{
  echo "host $(uname -a)"
  echo "python $($python -V 2>&1)"
  $python - <<'PY'
import torch, platform
print('torch', torch.__version__)
PY
  echo "source revision $(cat SOURCE_REVISION)"
  sha256sum learning/schedule.py tests/v5/test_evaluation_design.py
} > logs/environment.log 2>&1

PYTHONPATH=$root PYTHONDONTWRITEBYTECODE=1 $python -m unittest -v \
  tests.v5.test_evaluation_design tests.test_validation_cadence tests.test_schedule \
  tests.v5.test_selection tests.v5.test_final_nomination tests.v5.test_final_budget \
  tests.v5.test_teacher_protocol > logs/targeted.log 2>&1
tail -3 logs/targeted.log

PYTHONPATH=$root PYTHONDONTWRITEBYTECODE=1 $python \
  verification/ppo_refactor_r4_20261029/design_probe.py "$root/logs/probe" \
  > logs/design_probe.log 2>&1
grep -q '"status": "passed"' logs/design_probe.log
cp logs/probe/design_probe.json logs/design_probe.json
echo "passed: planned schedules reach every floor"
