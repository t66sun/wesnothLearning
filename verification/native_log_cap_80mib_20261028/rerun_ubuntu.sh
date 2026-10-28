#!/usr/bin/env bash
# Ubuntu acceptance for the 80 MiB runner native log cap.
# Usage: rerun_ubuntu.sh <source.tar> <expected-sha256-of-tar> [python]
set -euo pipefail
archive=$1
expected=$2
python=${3:-/home/tongshu/venv/bin/python}
commit=$(basename "$archive" .tar)
root=/home/tongshu/myDev/wesnothLearning/acceptance_native_log_cap_${commit}
printf '%s  %s\n' "$expected" "$archive" | sha256sum -c -
test ! -e "$root"
mkdir -p "$root/source" "$root/logs"
tar -xf "$archive" -C "$root/source"
cd "$root/source"
# The tracked archive already carries a partial data/ tree; it must be replaced
# by the frozen rules and datasets the acceptance run reads.
rm -rf data
ln -s /home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source/data data
export PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
{
    uname -sr
    "$python" -c 'import sys; print(sys.version)'
    "$python" -c 'from learning.common import VENDOR; import match; print("NATIVE_LOG_LIMIT", match.NATIVE_LOG_LIMIT)'
    sha256sum vendor/arena/match.py tests/v5/test_native_log_cap.py | tee "$root/logs/source.sha256"
} > "$root/logs/environment.log" 2>&1
"$python" -m unittest tests.v5.test_native_log_cap -v > "$root/logs/cap.log" 2>&1
cp vendor/arena/match.py "$root/match.before.py"
"$python" - vendor/arena/match.py > "$root/logs/revert.log" 2>&1 <<'PY'
import pathlib, subprocess, sys
path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding='utf-8')
old = 'NATIVE_LOG_LIMIT = 80 * 1024 * 1024'
assert text.count(old) == 1, text.count(old)
path.write_text(text.replace(old, 'NATIVE_LOG_LIMIT = 16 * 1024 * 1024'), encoding='utf-8')
try:
    result = subprocess.run([sys.executable, '-m', 'unittest', 'tests.v5.test_native_log_cap'],
                            capture_output=True, text=True)
finally:
    path.write_text(text, encoding='utf-8')
if result.returncode == 0:
    raise SystemExit('the test still passes with the 16 MiB cap')
if 'True is not false' not in result.stderr:
    raise SystemExit('failed for another reason:\n' + result.stderr[-2000:])
print('reverted to 16 MiB: test failed with "True is not false" (exit %d)' % result.returncode)
PY
cmp "$root/match.before.py" vendor/arena/match.py > "$root/logs/restored.log" 2>&1
printf 'targeted_exit=0\n' > "$root/logs/status.log"
printf 'root=%s\n' "$root"
