#!/usr/bin/env bash
# Windows reference checks for the policy rehearsal opt-in. Not Ubuntu acceptance.
set -euo pipefail
cd "$(dirname "$0")/../.."
PY=${PY:-.venv/Scripts/python.exe}
OUT=verification/ppo_refactor_r5_policy_20261028/windows
mkdir -p "$OUT"
$PY -c "import torch,sys;print(sys.version);print('torch',torch.__version__)" | tee "$OUT/environment.log"
git rev-parse HEAD | tee "$OUT/source.txt"
sha256sum learning/experiment.py tests/v5/test_rehearsal_source.py | tee "$OUT/source.sha256"
$PY -m unittest tests.v5.test_rehearsal_source -v 2>&1 | tee "$OUT/rehearsal_tests.log"
$PY -m unittest tests.v5.test_ppo_plan tests.test_validation_cadence tests.v5.test_rehearsal_source 2>&1 | tee "$OUT/related_suites.log"
$PY -m py_compile learning/experiment.py tests/v5/test_rehearsal_source.py | tee "$OUT/compile.log"
$PY verification/ppo_refactor_r5_policy_20261028/revert_windows.py 2>&1 | tee "$OUT/revert.log"
git status --porcelain -- learning/experiment.py | tee "$OUT/restored.log"
