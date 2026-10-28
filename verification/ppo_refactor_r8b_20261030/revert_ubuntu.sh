#!/usr/bin/env bash
# Each revert removes one half of the label decision and must fail the checks that
# depend on it. Sources are restored from the archive copy before the next case.
set -euo pipefail
root=/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r8b_20261030
python=/home/tongshu/venv/bin/python
wesnoth=/home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth
cd "$root/source"
export PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1
export LD_PRELOAD="$root/deterministic_entropy.so"
mkdir -p "$root/logs/revert"
backup=$root/revert-backup
rm -rf "$backup"; mkdir -p "$backup"
cp learning/stock_rca.py learning/sample.py lua/stock_rca_capture/main.lua "$backup/"

fail() { echo "expected failure did not happen: $1" >&2; exit 1; }

"$python" - <<'PY'
from pathlib import Path
path = Path('learning/stock_rca.py'); text = path.read_text()
start = text.index('        # One action can appear')
end = text.index('        coverage[kind][', start)
new = ('        ambiguous = len(matches) > 1\n'
       '        choice = matches[0] if len(matches) == 1 else -1\n')
path.write_text(text[:start] + new + text[end:])
print('intent dedupe reverted')
PY
"$python" -m unittest tests.v5.test_native_capture.NativeCaptureTests.test_scoring_variants_of_one_move_are_not_ambiguous \
    > "$root/logs/revert/dedupe.log" 2>&1 && fail 'scoring variants accepted as one intent'
cp "$backup/stock_rca.py" learning/stock_rca.py

"$python" - <<'PY'
from pathlib import Path
path = Path('lua/stock_rca_capture/main.lua'); text = path.read_text()
text = text.replace('if found>0 then frame.weapon=found end', '')
path.write_text(text)
print('weapon naming reverted')
PY
"$python" -m unittest tests.v5.test_native_capture.NativeCaptureTests.test_attack_names_the_weapon_the_engine_reports \
    > "$root/logs/revert/weapon.log" 2>&1 && fail 'weapon index still named'
cp "$backup/main.lua" lua/stock_rca_capture/main.lua

"$python" - <<'PY'
from pathlib import Path
path = Path('learning/sample.py'); text = path.read_text()
text = text.replace("total=count['matched']+count['unmatched']+count['ambiguous'])",
                    "total=count['matched']+count['unmatched']+count['ambiguous']+count['merged'])")
path.write_text(text)
print('merged events counted in the denominator')
PY
"$python" -m unittest tests.v5.test_native_capture.NativeCaptureTests.test_stock_totals_count_decisions_not_events \
    > "$root/logs/revert/totals.log" 2>&1 && fail 'merged events stayed out of the denominator'
"$python" verification/ppo_refactor_r8b_20261030/label_probe.py "$root/revert-probe" "$wesnoth" \
    > "$root/logs/revert/gate.log" 2>&1 && fail 'coverage gate passed with merged events counted'
cp "$backup/sample.py" learning/sample.py

"$python" -m unittest tests.v5.test_native_capture > "$root/logs/restored.log" 2>&1
echo 'revert probes failed as expected; sources restored'
