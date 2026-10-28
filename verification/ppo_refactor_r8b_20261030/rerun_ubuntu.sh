#!/usr/bin/env bash
set -euo pipefail
archive=/tmp/wesnoth-r8b.tar
root=/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r8b_20261030
python=/home/tongshu/venv/bin/python
wesnoth=/home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth
canonical_capture=12fbbb4d3b3af4fc0a2afdb3c5d4893b8df23f408a50bc4081932f08042b3b54
printf '%s  %s\n' "$1" "$archive" | sha256sum -c -
test ! -e "$root"
mkdir -p "$root/source" "$root/logs"
tar -xf "$archive" -C "$root/source"
cd "$root/source"
ln -s /home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source/data data
export PYTHONPATH="$PWD" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
gcc -O2 -Wall -shared -fPIC -o "$root/deterministic_entropy.so" \
    verification/ppo_refactor_r8_20261028/deterministic_entropy.c -ldl
export LD_PRELOAD="$root/deterministic_entropy.so"
{
    uname -sr
    "$python" -c 'import sys,torch; print(sys.version); print(torch.__version__)'
    "$wesnoth" --simple-version
    sha256sum "$wesnoth" data/rules/1.18.8-training/rules.json
    sha256sum "$root/deterministic_entropy.so"
    cat SOURCE_REVISION
} > "$root/logs/environment.log" 2>&1
"$python" -m unittest tests.v5.test_native_capture tests.v5.test_teacher_protocol \
    tests.v5.test_reward_row_schema tests.v5.test_bundle_identity tests.v5.test_teacher_identity \
    -v > "$root/logs/targeted.log" 2>&1
"$python" verification/ppo_refactor_r8b_20261030/label_probe.py "$root/probe" "$wesnoth" \
    > "$root/logs/probe.log" 2>&1
"$python" - "$root/probe/probe.json" "$canonical_capture" <<'PY' > "$root/logs/identity.log" 2>&1
import json, sys
probe = json.load(open(sys.argv[1]))
assert probe['status'] == 'passed', probe
assert probe['gate']['passed'] is True, probe['gate']
for kind, count in probe['totals'].items():
    assert count['ambiguous'] == 0, (kind, count)
assert probe['totals']['attack']['matched'] > 0, probe['totals']
assert probe['totals']['recruit']['matched'] > 0, probe['totals']
assert probe['totals']['moveto']['matched'] > 0, probe['totals']
assert probe['capture_sha256'] == sys.argv[2], probe['capture_sha256']
assert probe['runtime_sha256'] == '33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf', probe
assert probe['rules_sha256'] == 'd6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca', probe
assert probe['teacher_query'] == 'none', probe
assert len(probe['games']) == 2, probe['games']
print('games', len(probe['games']), 'gate', probe['gate']['actions'])
print('totals', probe['totals'])
print('capture_sha256', probe['capture_sha256'])
PY
echo 'targeted checks and two stock games completed'
