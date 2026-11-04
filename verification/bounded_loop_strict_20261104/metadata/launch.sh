set -eu
run_name=$1
source_commit=$2
archive_sha=$3
extension_dir=$4
base=/home/tongshu/acceptance
root=$base/$run_name
archive=$base/$run_name.tar.gz
mkdir "$root"
cd "$root"
date -Ins > preparation.started
printf '%s  %s\n' "$archive_sha" "$archive" | sha256sum --check -
tar -xzf "$archive"
mkdir -p data/rules .runtime
ln -s /home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered data/rules/1.18.8-combat-filtered
ln -s /home/tongshu/myDev/wesnothLearning/WesnothLearning/data/rules/1.18.8 data/rules/1.18.8
ln -s "$extension_dir" .extension
cc -O2 -fPIC -shared -o .runtime/entropy.so vendor/arena/entropy.c -ldl
export PYTHONPATH="$root/.extension:$root:$root/vendor/arena"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
export SOURCE_COMMIT="$source_commit"
export WESNOTH_EXE=/home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth
export BOUNDED_BC_PARENT=/home/tongshu/acceptance/bc_v6_readiness_20261103/runs/bc_readiness
sha256sum .extension/_engine_lite.so .runtime/entropy.so "$WESNOTH_EXE" data/rules/1.18.8-combat-filtered/rules.json "$BOUNDED_BC_PARENT/manifest.json" "$BOUNDED_BC_PARENT"/*/latest.pt > inputs.sha256
/home/tongshu/venv/bin/python -B -c 'import json, os, platform, torch, _engine_lite; from learning.teachers import identity; print(json.dumps(dict(source=os.environ["SOURCE_COMMIT"],python=platform.python_version(),torch=torch.__version__,extension=_engine_lite.__file__,teacher=identity())))' > runtime.json
date -Ins > started.txt
rc=0
timeout --signal=TERM --kill-after=15s 3600 /home/tongshu/venv/bin/python -u tests/bounded_training_loop.py >driver.log 2>&1 || rc=$?
date -Ins > finished.txt
printf '%s\n' "$rc" > driver.exit
cat driver.log
exit "$rc"