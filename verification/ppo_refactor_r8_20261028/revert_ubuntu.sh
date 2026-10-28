#!/usr/bin/env bash
set -euo pipefail
root=/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r8b_20261028
archive=/tmp/wesnoth-r8b-45e7146.tar
python=/home/tongshu/venv/bin/python
wesnoth=/home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth
cd "$root/source"
export PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
sha256sum learning/stock_rca.py lua/stock_rca_capture/observer.lua > "$root/logs/source_before.sha256"

# Revert 1: a context labels one action again instead of the whole engine decision.
"$python" - "$root/logs/fold_reverted.log" <<'PY'
from pathlib import Path
path = Path('learning/stock_rca.py')
text = path.read_text()
old = """        elif group and group[0]['id'] == context_id:
            group[1].append(frame)
"""
assert old in text
path.write_text(text.replace(old, ''))
PY
if "$python" -m unittest tests.v5.test_native_capture.NativeCaptureTests.test_recruit_burst_is_one_engine_decision \
        tests.v5.test_native_capture.NativeCaptureTests.test_move_and_attack_share_one_decision \
        > "$root/logs/fold_reverted.log" 2>&1; then
    echo 'fold revert did not fail the named tests'; exit 1
fi
tar -xf "$archive" -C "$root/source" ./learning/stock_rca.py

# Revert 2: the observer stops publishing a context, so actions lose pre-action state.
"$python" - "$root/logs/observer_reverted.log" <<'PY'
from pathlib import Path
path = Path('lua/stock_rca_capture/observer.lua')
text = path.read_text()
old = "    capture.context(capture.row(data.memory),data.memory)\n"
assert old in text
path.write_text(text.replace(old, ''))
PY
if LD_PRELOAD="$root/deterministic_entropy.so" "$python" verification/ppo_refactor_r8_20261028/native_probe.py \
        "$root/revert_fixture" "$wesnoth" > "$root/logs/observer_reverted.log" 2>&1; then
    echo 'observer revert did not fail the probe'; exit 1
fi
tar -xf "$archive" -C "$root/source" ./lua/stock_rca_capture/observer.lua

"$python" -m unittest tests.v5.test_native_capture tests.v5.test_teacher_identity tests.v5.test_reward_row_schema \
    > "$root/logs/restored.log" 2>&1
sha256sum learning/stock_rca.py lua/stock_rca_capture/observer.lua > "$root/logs/source_after.sha256"
diff "$root/logs/source_before.sha256" "$root/logs/source_after.sha256" > "$root/logs/status.log"
echo 'revert and restore completed'
