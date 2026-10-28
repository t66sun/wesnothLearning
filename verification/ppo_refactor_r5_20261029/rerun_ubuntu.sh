#!/usr/bin/env bash
# Usage: rerun_ubuntu.sh <source.tar> <expected-sha256> <root>
set -euo pipefail
archive=$1
expected=$2
root=$3
data=/home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source/data
test "$(sha256sum "$archive" | cut -d' ' -f1)" = "$expected"
test ! -e "$root"
mkdir -p "$root/logs"
tar -xf "$archive" -C "$root"
rm -rf "$root/data"
ln -s "$data" "$root/data"
{
  echo "host $(uname -sri)"
  /home/tongshu/venv/bin/python - <<'PY'
import sys, torch
print('python', sys.version.split()[0])
print('torch', torch.__version__)
PY
  echo "source revision $(cat "$root/SOURCE_REVISION")"
  sha256sum "$root/data/humanData_curated/games.jsonl" "$root/data/datasets/human/import.json"
} > "$root/logs/environment.log"
cd "$root"
PYTHONPATH=$PWD PYTHONDONTWRITEBYTECODE=1 /home/tongshu/venv/bin/python \
  verification/ppo_refactor_r5_20261029/inventory_probe.py "$root/logs/audit" \
  > "$root/logs/audit.log" 2>&1
tail -1 "$root/logs/audit.log"
test -f "$root/logs/audit/probe.json"
grep -q 'passed: no existing input can fill the R5 rehearsal pool' "$root/logs/audit.log"
echo "audit archived at $root/logs/audit/probe.json"
