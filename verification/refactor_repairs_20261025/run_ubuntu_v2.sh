#!/usr/bin/env bash
# Bounded V1-V6 acceptance: recorded schedules and synthetic rows, zero real games.
set -euo pipefail
source_revision=${1:?source commit required}
archive_sha256=${2:?archive hash required}
archive=/tmp/wesnoth-v1-v6-36cc99f.tar
work=/home/tongshu/myDev/wesnothLearning/acceptance_v1_v6_20261025_36cc99f_v2
provision=/home/tongshu/myDev/wesnothLearning/acceptance_refactor_20261025/master
python=/home/tongshu/venv/bin/python
printf '%s  %s\n' "$archive_sha256" "$archive" | sha256sum --check -
test ! -e "$work" || { printf "isolated destination already exists: %s\n" "$work" >&2; exit 1; }
test -d "$provision/data/rules/1.18.8-training" || { printf "missing read-only rules provision: %s\n" "$provision/data/rules/1.18.8-training" >&2; exit 1; }
mkdir "$work"
tar -xf "$archive" -C "$work"
ln -s "$provision/data" "$work/data"
mkdir "$work/logs"
cd "$work"
export PYTHONPATH="$work:$work/vendor/arena"
export PYTHONDONTWRITEBYTECODE=1
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
export ACCEPTANCE_SOURCE_REVISION="$source_revision"
"$python" -B - <<'PY' | tee logs/environment.log
import json, os, platform, sys
import torch, _engine_lite
from learning.features import schema
from learning.teachers import identity
core = {k:getattr(_engine_lite,k,None) for k in ('ENGINE_VERSION','RNG_VERSION','COMBAT_VERSION')}
print(json.dumps(dict(source_revision=os.environ['ACCEPTANCE_SOURCE_REVISION'],
    platform=platform.platform(),python=sys.version,torch=torch.__version__,
    extension=_engine_lite.__file__,engine=core,rules_sha256=schema()['rules_sha256'],
    teacher=identity(),real_games=0),indent=2))
assert core == dict(ENGINE_VERSION='lite-0.2',RNG_VERSION='deterministic-expected_damage_v1',COMBAT_VERSION='expected_damage_v1'), core
assert schema()['rules_sha256']=='d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca'
PY
/usr/bin/time -v "$python" -B -m unittest -v \
  tests.v5.test_final_nomination \
  tests.v5.test_checkpoint_export_identity \
  tests.v5.test_ppo_resume_counters \
  tests.v5.test_bc_cancel_rng \
  tests.v5.test_rollout_content_identity \
  tests.v5.test_teacher_engine_identity 2>&1 | tee logs/targeted.log
