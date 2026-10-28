#!/usr/bin/env bash
# R4 revert probe: the pre-fix three-block rosters must fail the recorded checks.
set -euo pipefail
root=${1:-/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r4_20261029}
python=/home/tongshu/venv/bin/python
cd "$root"

cp learning/schedule.py /tmp/schedule_r4.py
restore() { cp /tmp/schedule_r4.py learning/schedule.py; }

panel=$($python - <<'PY'
import pathlib
path=pathlib.Path('learning/schedule.py'); text=path.read_text(encoding='utf-8')
old="""        roster=(scenarios.get(fmt) if isinstance(scenarios,dict) else scenarios) if scenarios is not None else [
            dict(map_index=i,factions=list(group)) for group in starting_factions(n,fmt)
            for i in range(len(names))]"""
replacement="""        roster=(scenarios.get(fmt) if isinstance(scenarios,dict) else scenarios) if scenarios is not None else [
            dict(map_index=i,faction_block=f) for f in range(len(params.FACTIONS)//gcd(n,len(params.FACTIONS)))
            for i in range(len(names))]"""
assert old in text, 'roster block not found'
path.write_text(text.replace(old,replacement),encoding='utf-8')
print('panel roster reverted')
PY
)
echo "$panel"
set +e
PYTHONPATH=$root PYTHONDONTWRITEBYTECODE=1 $python -m unittest -v \
  tests.v5.test_evaluation_design.EvaluationDesignTests.test_frozen_floors_and_existing_schedule_capacity \
  > logs/revert_panel.log 2>&1
panel_status=$?
PYTHONPATH=$root PYTHONDONTWRITEBYTECODE=1 $python \
  verification/ppo_refactor_r4_20261029/design_probe.py "$root/logs/revert_probe" \
  > logs/revert_probe.log 2>&1
probe_status=$?
set -e
test $panel_status -ne 0 || { echo 'panel check did not fail'; restore; exit 1; }
test $probe_status -ne 0 || { echo 'design probe did not fail'; restore; exit 1; }
grep -q 'distinct_scenarios' logs/revert_probe.log
restore

teacher=$($python - <<'PY'
import pathlib
path=pathlib.Path('learning/schedule.py'); text=path.read_text(encoding='utf-8')
old="""            job = base_job(directory, ident, bots, rng.randrange(2**32), deadline, wesnoth, i, fmt,
                           faction_list=scenario_factions(i, n, fmt))"""
replacement="""            job = base_job(directory, ident, bots, rng.randrange(2**32), deadline, wesnoth, i, fmt)"""
assert old in text, 'stock teacher call not found'
path.write_text(text.replace(old,replacement),encoding='utf-8')
print('teacher roster reverted')
PY
)
echo "$teacher"
set +e
PYTHONPATH=$root PYTHONDONTWRITEBYTECODE=1 $python -m unittest -v \
  tests.v5.test_evaluation_design.EvaluationDesignTests.test_teacher_games_reach_the_bc_scenario_floor \
  > logs/revert_teacher.log 2>&1
teacher_status=$?
set -e
test $teacher_status -ne 0 || { echo 'teacher roster check did not fail'; restore; exit 1; }
restore

PYTHONPATH=$root PYTHONDONTWRITEBYTECODE=1 $python -m unittest -v \
  tests.v5.test_evaluation_design > logs/restored.log 2>&1
tail -3 logs/restored.log
echo 'revert probes failed as expected; sources restored'
