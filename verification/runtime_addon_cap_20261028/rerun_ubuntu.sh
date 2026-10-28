#!/bin/bash
# Usage: rerun_ubuntu.sh <source.tar.gz> <sha256-of-tar> [python]
set -euo pipefail
archive=$1
expected=$2
python=${3:-python3}
actual=$(sha256sum "$archive" | cut -d' ' -f1)
[ "$actual" = "$expected" ] || { echo "archive sha256 mismatch: $actual != $expected" >&2; exit 1; }
root="/home/tongshu/myDev/wesnothLearning/acceptance_runtime_addon_$(basename "$archive" .tar.gz)"
rm -rf "$root"
mkdir -p "$root"
tar -xzf "$archive" -C "$root"
cd "$root"
export PYTHONPATH="$root"
{ uname -a; "$python" -V; } | tee ubuntu_env.log
"$python" -m unittest tests.v5.test_addon_runtime_limit -v 2>&1 | tee pass.log
"$python" -m unittest discover -s vendor/arena/tests -p "test_*.py" 2>&1 | tee sdk.log
cp vendor/arena/addons.py /tmp/addons.orig.py
"$python" - <<'PY'
import pathlib
p = pathlib.Path('vendor/arena/addons.py')
s = p.read_text()
s = s.replace('validate(path, limit=None)', 'validate(path)')
p.write_text(s)
PY
set +e
"$python" -m unittest tests.v5.test_addon_runtime_limit > revert.log 2>&1
code=$?
set -e
echo "revert_exit=$code"
cp /tmp/addons.orig.py vendor/arena/addons.py
cmp /tmp/addons.orig.py vendor/arena/addons.py
echo "restored=identical"
[ "$code" -ne 0 ]
