#!/usr/bin/env bash
# Invoke only after the frozen protocol, fixtures and command receive root review.
set -uo pipefail
cd "$(dirname "$0")/../.."
export SOURCE_COMMIT
SOURCE_COMMIT=$(cat ../SOURCE_COMMIT)
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0
export PYTHONPATH="$PWD:/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension"
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
printf '%s\n' "source=$SOURCE_COMMIT" "launcher_pid=$$" "started_utc=$(date -u +%FT%TZ)" > ../launcher.txt
timeout --signal=TERM --kill-after=5s 28800s /home/tongshu/venv/bin/python -u \
  verification/duel_ppo_comparison_20261106/driver.py run \
  --output runs/duel_ppo_comparison_20261106 > ../driver.log 2>&1
status=$?
printf '%s\n' "$status" > ../driver.exit
printf '%s\n' "finished_utc=$(date -u +%FT%TZ)" >> ../launcher.txt
exit "$status"
