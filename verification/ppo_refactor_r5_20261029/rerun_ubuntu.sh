#!/usr/bin/env bash
# Usage: rerun_ubuntu.sh <source.tar> <expected-sha256> <root> <inputs.tar>
set -euo pipefail
archive=$1
expected=$2
root=$3
inputs=$4
test "$(sha256sum "$archive" | cut -d' ' -f1)" = "$expected"
test ! -e "$root"
mkdir -p "$root/logs"
tar -xf "$archive" -C "$root"
tar -xf "$inputs" -C "$root"
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
export PYTHONPATH=$PWD PYTHONDONTWRITEBYTECODE=1
python=/home/tongshu/venv/bin/python
"$python" -m unittest tests.test_human -v > "$root/logs/targeted.log" 2>&1
tail -3 "$root/logs/targeted.log"
"$python" verification/ppo_refactor_r5_20261029/inventory_probe.py "$root/logs/audit" \
  > "$root/logs/audit.log" 2>&1
tail -1 "$root/logs/audit.log"
grep -q 'passed: no existing input can fill the R5 rehearsal pool' "$root/logs/audit.log"
"$python" -m learning import-human --curated "$root/data/humanData_curated" \
  --output "$root/logs/inventory" --inventory-only > "$root/logs/inventory.log" 2>&1
"$python" - "$root/logs/inventory/import.json" <<'PY'
import json, sys
report = json.load(open(sys.argv[1], encoding='utf-8'))
print('statuses', report['statuses'])
assert report['statuses'] == {'skipped': 43}, report['statuses']
assert report['samples'] == 0
assert not any(g.get('status') == 'compatible_pending_native_replay' for g in report['games'])
assert sum(g.get('reason') == 'other_version' for g in report['games']) == 2
print('passed: no curated replay is eligible for 1.18.8 labels')
PY
echo "evidence at $root/logs"
