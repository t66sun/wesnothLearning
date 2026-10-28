#!/usr/bin/env bash
# R10 revert proof: the pre-R10 bundle ships every opponent package and writes no
# teacher identity, so test_bundle_omits_unused_teacher must fail.
set -euo pipefail

source_root=/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r10b_20261029
python=/home/tongshu/venv/bin/python
logs=$(cd "$(dirname "$0")" && pwd)/rerun
test_id=tests.v5.test_bundle_identity.BundleIdentityTests.test_bundle_omits_unused_teacher
backup=$(mktemp)

cd "$source_root"
cp learning/bundle.py "$backup"
export PYTHONPATH=$PWD PYTHONDONTWRITEBYTECODE=1

$python - <<'PY'
from pathlib import Path
path = Path('learning/bundle.py')
text = path.read_text()
old_needed = "    return not path.startswith('data/opponents/') or path in TEACHER_PACKAGES\n"
new_needed = "    return True\n"
old_identity = "        'identities': {'teacher': teacher},\n"
new_identity = "        'identities_legacy': {'teacher': teacher},\n"
assert old_needed in text and old_identity in text
path.write_text(text.replace(old_needed, new_needed).replace(old_identity, new_identity))
PY

if $python -m unittest "$test_id" > "$logs/revert.log" 2>&1; then
    echo "revert did not fail the identity test" >&2
    cp "$backup" learning/bundle.py
    exit 1
fi
cp "$backup" learning/bundle.py
$python -m unittest "$test_id" > "$logs/restore.log" 2>&1
grep -E 'FAILED \(' "$logs/revert.log"
echo "revert failed as expected; restored source passes"
