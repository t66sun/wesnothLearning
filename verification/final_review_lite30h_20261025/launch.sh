#!/usr/bin/env bash
set -euo pipefail
work=/home/tongshu/myDev/wesnothLearning/training_lite30h_20261025
provision=/home/tongshu/myDev/wesnothLearning/acceptance_refactor_20261025/master
python=/home/tongshu/venv/bin/python
archive=/tmp/wesnoth-lite30h-20261025.tar
if [[ ${1:-} == status ]]; then
  cd "$work/source"
  "$python" -B verification/final_review_lite30h_20261025/launch.py status
  exit
fi
revision=${1:?source commit required}
archive_hash=${2:?archive SHA256 required}
printf '%s  %s\n' "$archive_hash" "$archive" | sha256sum --check -
test ! -e "$work"
test -d "$provision/data/rules/1.18.8-training"
test -d "$provision/data/opponents"
test -x "$provision/.runtime/install/bin/wesnoth"
mkdir -p "$work/source" "$work/logs"
tar -xf "$archive" -C "$work/source"
cd "$work/source"
mkdir -p data/datasets/human
ln -s "$provision/data/rules" data/rules
ln -s "$provision/data/opponents" data/opponents
export PYTHONPATH="$PWD:$PWD/vendor/arena" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
export TRAINING_SOURCE_REVISION="$revision" TRAINING_ARCHIVE_SHA256="$archive_hash"
"$python" -B verification/final_review_lite30h_20261025/launch.py preflight | tee "$work/logs/environment.log"
/usr/bin/time -v "$python" -B -m unittest -v tests.v5.test_final_budget tests.v5.test_final_nomination 2>&1 | tee "$work/logs/preflight.log"
"$python" -B verification/final_review_lite30h_20261025/launch.py start | tee "$work/logs/launch.log"
