#!/bin/bash
# Usage: rerun_ubuntu.sh <source.tar.gz> <sha256-of-tar> [python]
set -euo pipefail
archive=$1
expected=$2
python=${3:-python3}
actual=$(sha256sum "$archive" | cut -d' ' -f1)
[ "$actual" = "$expected" ] || { echo "archive sha256 mismatch: $actual != $expected" >&2; exit 1; }
root="/home/tongshu/myDev/wesnothLearning/acceptance_stock_frame_$(basename "$archive" .tar.gz)"
rm -rf "$root"
mkdir -p "$root"
tar -xzf "$archive" -C "$root"
cd "$root"
export PYTHONPATH="$root"
{ uname -a; "$python" -V; } | tee ubuntu_env.log
"$python" -m unittest tests.v5.test_native_log_cap -v 2>&1 | tee pass.log
cp vendor/arena/match.py /tmp/match.orig.py
"$python" - <<'PY'
import pathlib
p = pathlib.Path('vendor/arena/match.py')
s = p.read_text()
s = s.replace("(prefix + 'LEARN ', prefix + 'STOCK ')", "(prefix + 'LEARN ',)")
p.write_text(s)
PY
set +e
"$python" -m unittest tests.v5.test_native_log_cap > revert.log 2>&1
code=$?
set -e
echo "revert_exit=$code"
cp /tmp/match.orig.py vendor/arena/match.py
cmp /tmp/match.orig.py vendor/arena/match.py
echo "restored=identical"
[ "$code" -ne 0 ]
