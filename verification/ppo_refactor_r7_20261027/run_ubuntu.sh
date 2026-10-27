#!/usr/bin/env bash
set -euo pipefail
archive=/tmp/wesnoth-r7-e509a8d.tar
root=/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r7_20261027_e509a8d
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
files=(learning/data.py learning/experiment.py learning/lite_host.py learning/manifest.py
       learning/native_rpc.lua learning/schedule.py learning/updates.py tests/v5/helpers.py
       tests/v5/test_teacher_identity.py tests/test_validation_cadence.py tests/v5/test_final_nomination.py)
sha256sum "${files[@]}" > "$root/logs/source_before.sha256"
"$python" -m unittest tests.v5.test_teacher_identity tests.test_validation_cadence tests.v5.test_scenario_identity \
    tests.v5.test_batch_eligibility tests.v5.test_final_nomination tests.v5.test_final_budget \
    tests.v5.test_ppo_resume_counters tests.test_opponents tests.v5.test_rehearsal_source \
    tests.v5.test_bc_cancel_rng -v > "$root/logs/targeted.log" 2>&1
printf 'targeted_exit=0\n' > "$root/logs/status.log"
"$python" - <<'PY' > "$root/logs/lua_syntax.log" 2>&1
from pathlib import Path
from lupa import LuaRuntime
LuaRuntime().compile(Path('learning/native_rpc.lua').read_text(encoding='utf-8-sig'))
print('native_rpc.lua syntax: PASS; no native runtime executed')
PY
printf 'lua_syntax_exit=0\n' >> "$root/logs/status.log"
cp learning/experiment.py "$root/logs/fixed_experiment.py"
"$python" - <<'PY'
from pathlib import Path
path=Path('learning/experiment.py')
source=path.read_text()
anchor="                job.setdefault('allow_approximate',self.config.get('allow_approximate',False))"
assert source.count(anchor)==1
source=source.replace(anchor,anchor+"\n                job['bots']=[self.teachers[0] if bot=='baseline' else bot for bot in job['bots']]")
path.write_text(source)
PY
set +e
"$python" -m unittest tests.v5.test_teacher_identity.TeacherIdentityTests.test_baseline_is_never_substituted -v > "$root/logs/reverted.log" 2>&1
reverted=$?
set -e
cp "$root/logs/fixed_experiment.py" learning/experiment.py
printf 'reverted_exit=%s\n' "$reverted" >> "$root/logs/status.log"
test "$reverted" -ne 0
"$python" -m unittest tests.v5.test_teacher_identity.TeacherIdentityTests.test_baseline_is_never_substituted -v > "$root/logs/restored.log" 2>&1
printf 'restored_exit=0\n' >> "$root/logs/status.log"
sha256sum "${files[@]}" > "$root/logs/source_after.sha256"
cmp "$root/logs/source_before.sha256" "$root/logs/source_after.sha256"
printf 'source_restored=1\n' >> "$root/logs/status.log"
cat "$root/logs/status.log"
tail -n 5 "$root/logs/targeted.log"
