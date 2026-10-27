#!/usr/bin/env bash
set -euo pipefail
archive=/tmp/wesnoth-r3-3983cd0.tar
root=/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r3_20261027_3983cd0
python=/home/tongshu/venv/bin/python
printf '%s  %s\n' "$1" "$archive" | sha256sum -c -
test ! -e "$root"
mkdir -p "$root/source" "$root/logs"
tar -xf "$archive" -C "$root/source"
cd "$root/source"
ln -s /home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source/data data
export PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
{
    uname -sr
    "$python" -c 'import sys,torch,_engine_lite; print(sys.version); print(torch.__version__); print(_engine_lite.__file__)'
    sha256sum data/rules/1.18.8-training/rules.json
    cat SOURCE_REVISION
} > "$root/logs/environment.log" 2>&1
files=(learning/ppo.py learning/experiment.py tests/v5/test_kl_defer.py tests/v5/test_ppo_resume_counters.py)
sha256sum "${files[@]}" > "$root/logs/source_before.sha256"
"$python" -m unittest tests.v5.test_kl_defer tests.v5.test_ppo_resume_counters tests.v5.test_ppo_plan -v > "$root/logs/targeted.log" 2>&1
printf 'targeted_exit=0\n' > "$root/logs/status.log"
cp learning/ppo.py "$root/logs/fixed_ppo.py"
cp baseline_ppo.py learning/ppo.py
set +e
"$python" -m unittest tests.v5.test_kl_defer.KlAccountingTests.test_kl_rejection_accounts_for_all_remaining_work -v > "$root/logs/reverted.log" 2>&1
reverted=$?
set -e
cp "$root/logs/fixed_ppo.py" learning/ppo.py
printf 'reverted_exit=%s\n' "$reverted" >> "$root/logs/status.log"
test "$reverted" -ne 0
"$python" -m unittest tests.v5.test_kl_defer.KlAccountingTests.test_kl_rejection_accounts_for_all_remaining_work -v > "$root/logs/restored.log" 2>&1
printf 'restored_exit=0\n' >> "$root/logs/status.log"
sha256sum "${files[@]}" > "$root/logs/source_after.sha256"
cmp "$root/logs/source_before.sha256" "$root/logs/source_after.sha256"
printf 'source_restored=1\n' >> "$root/logs/status.log"
cat "$root/logs/status.log"
tail -n 5 "$root/logs/targeted.log"
