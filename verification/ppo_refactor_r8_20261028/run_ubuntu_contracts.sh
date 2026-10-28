#!/usr/bin/env bash
set -euo pipefail
archive=/tmp/wesnoth-r8-20261028-b.tar
root=/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r8_20261028_b
python=/home/tongshu/venv/bin/python
printf '%s  %s\n' "$1" "$archive" | sha256sum -c -
test ! -e "$root"
mkdir -p "$root/source" "$root/logs"
tar -xf "$archive" -C "$root/source"
cd "$root/source"
ln -s /home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source/data data
export PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
cat SOURCE_REVISION > "$root/logs/source_revision.log"
files=(lua/candidates.lua lua/stock_rca_capture/main.lua lua/stock_rca_capture/observer.lua tests/v5/test_native_capture.py)
sha256sum "${files[@]}" > "$root/logs/source_before.sha256"
"$python" -m unittest tests.v5.test_native_capture -v > "$root/logs/targeted.log" 2>&1
"$python" - <<'PY' > "$root/logs/lua_syntax.log" 2>&1
from pathlib import Path
from lupa import LuaRuntime
for p in (Path('lua/candidates.lua'),*Path('lua/stock_rca_capture').glob('*.lua'),Path('vendor/arena/runtime/runtime.lua')):
    LuaRuntime().compile(p.read_text(encoding='utf-8-sig'))
    print(p, 'syntax PASS')
PY
cp lua/candidates.lua "$root/logs/fixed_candidates.lua"
cp lua/stock_rca_capture/main.lua "$root/logs/fixed_capture.lua"
"$python" - <<'PY'
from pathlib import Path
p=Path('lua/candidates.lua');s=p.read_text();assert s.count("facing='ne',")==1
p.write_text(s.replace("facing='ne',",''))
PY
set +e
"$python" -m unittest tests.v5.test_native_capture.NativeCaptureTests.test_recruit_probe_does_not_draw_a_random_facing -v > "$root/logs/facing_reverted.log" 2>&1
facing=$?
set -e
cp "$root/logs/fixed_candidates.lua" lua/candidates.lua
test "$facing" -ne 0
"$python" - <<'PY'
from pathlib import Path
p=Path('lua/stock_rca_capture/main.lua');s=p.read_text();needle="'moveto','attack','post advance'";assert s.count(needle)==1
p.write_text(s.replace(needle,"'moveto','post advance'"))
PY
set +e
"$python" -m unittest tests.v5.test_native_capture.NativeCaptureTests.test_attack_event_becomes_a_label -v > "$root/logs/attack_reverted.log" 2>&1
attack=$?
set -e
cp "$root/logs/fixed_capture.lua" lua/stock_rca_capture/main.lua
test "$attack" -ne 0
"$python" -m unittest tests.v5.test_native_capture.NativeCaptureTests.test_attack_event_becomes_a_label tests.v5.test_native_capture.NativeCaptureTests.test_recruit_probe_does_not_draw_a_random_facing -v > "$root/logs/restored.log" 2>&1
sha256sum "${files[@]}" > "$root/logs/source_after.sha256"
cmp "$root/logs/source_before.sha256" "$root/logs/source_after.sha256"
printf 'targeted_exit=0\nfacing_reverted_exit=%s\nattack_reverted_exit=%s\nrestored_exit=0\nsource_restored=1\nno_native_games=1\n' "$facing" "$attack" > "$root/logs/status.log"
cat "$root/logs/status.log"
