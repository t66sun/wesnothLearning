#!/bin/bash
set -u
export PYTHONPATH=.:vendor/arena OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
for variant in profile sparse; do
  root=/home/tongshu/acceptance/native_inference_${variant}_20261102
  cd "$root" || exit 2
  if [ "$variant" = profile ]; then source=01b5170; else source=5b90f02; fi
  date -u > native_host_before.txt
  uptime >> native_host_before.txt
  ps -eo pid,ppid,pcpu,comm,args --sort=-pcpu | head -12 >> native_host_before.txt
  /usr/bin/time -p timeout --signal=TERM --kill-after=15s 1800s /home/tongshu/venv/bin/python -u verification/candidate_work_budget_20261031/check.py "$root" "$root/native" /home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth "$source" > native.log 2> native.err
  status=$?
  echo "$status" > native.exit
  date -u > native_host_after.txt
  uptime >> native_host_after.txt
  if [ "$status" -gt 1 ]; then exit "$status"; fi
 done