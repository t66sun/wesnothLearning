#!/usr/bin/env bash
set -euo pipefail
source=/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r2_20261027_3a92436/source
root=/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r2_20261027_supplement
test ! -e "$root"
mkdir -p "$root"
cp /tmp/wesnoth-r2-supplement-test.py "$root/test_batch_eligibility.py"
cd "$source"
export PYTHONPATH="$source" PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
sha256sum "$root/test_batch_eligibility.py" > "$root/source.sha256"
/home/tongshu/venv/bin/python - "$root/test_batch_eligibility.py" > "$root/targeted.log" 2>&1 <<'PY'
import importlib.util
import sys
import unittest
spec = importlib.util.spec_from_file_location('r2_supplement', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
suite = unittest.TestSuite([module.BatchEligibilityTests(
    'test_four_player_updates_report_zero_excluded_rows')])
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(not result.wasSuccessful())
PY
cat "$root/source.sha256" "$root/targeted.log"
