#!/usr/bin/env bash
# Usage: revert_ubuntu.sh <root>
set -euo pipefail
root=$1
cd "$root"
python=/home/tongshu/venv/bin/python
export PYTHONPATH=$PWD PYTHONDONTWRITEBYTECODE=1
backup=/tmp/human_r5.py
cp learning/human.py "$backup"
restore() { cp "$backup" learning/human.py; }
trap restore EXIT
"$python" - <<'PY'
from pathlib import Path
path = Path('learning/human.py')
text = path.read_text(encoding='utf-8')
guard = """    # Labels must describe the frozen 1.18.8 rules; an older replay reproduces
    # under different combat and recruit numbers even when it replays cleanly.
    if row.get('version')!='1.18.8': return 'other_version'
"""
assert guard in text
path.write_text(text.replace(guard, ''), encoding='utf-8')
print('version guard reverted')
PY
set +e
"$python" -m unittest tests.test_human.HumanTests.test_labels_never_come_from_a_replay_recorded_under_older_rules \
  > "$root/logs/reverted.log" 2>&1
status=$?
set -e
tail -4 "$root/logs/reverted.log"
test "$status" -ne 0
restore
trap - EXIT
"$python" -m unittest tests.test_human \
  > "$root/logs/restored.log" 2>&1
tail -3 "$root/logs/restored.log"
grep -q '^OK$' "$root/logs/restored.log"
echo "revert proved and restored"
