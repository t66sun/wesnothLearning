set -euo pipefail
base=/home/tongshu/myDev/wesnothLearning
remote=/home/tongshu/myDev/wesnothLearning/verification/astra_restore_20261107/20261107T125415Z_0119385ab61f
commit=0119385ab61f282a1298c18d12efbb1df1a01eee
python=/home/tongshu/venv/bin/python
mkdir "$remote/source" "$remote/checks"
trap 'printf "%s\n" "$?" > "$remote/checks/exit_code"' EXIT
"$python" -c 'import sys,tarfile; t=tarfile.open(sys.argv[1]); assert t.pax_headers["comment"]==sys.argv[2]' "$remote/source.tar" "$commit"
tar -xf "$remote/source.tar" -C "$remote/source"
printf '%s\n' "$commit" > "$remote/checks/SOURCE_COMMIT"
cd "$remote/source"
mkdir -p data/rules .runtime
ln -s "$base/WesnothLearning/data/opponents" data/opponents
ln -s "$base/WesnothLearning/data/rules/1.18.8" data/rules/1.18.8
ln -s "$base/WesnothLearning/data/rules/1.18.8-training" data/rules/1.18.8-training
ln -s /home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered data/rules/1.18.8-combat-filtered
ln -s "$base/WesnothLearning/.runtime/install" .runtime/install
export PATH="/home/tongshu/.cargo/bin:$PATH"
export CARGO_TARGET_DIR=/home/tongshu/.cache/teacher_integration_target
export CARGO_BUILD_JOBS=8 CARGO_NET_OFFLINE=true
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
export WESNOTH_EXE="$PWD/.runtime/install/bin/wesnoth"
"$python" -m maturin build --release --manifest-path engine_lite/Cargo.toml --out .runtime/astra_wheels 2>&1 | tee "$remote/checks/build.log"
"$python" -m pip install --no-deps --target .runtime/astra_host .runtime/astra_wheels/*.whl 2>&1 | tee -a "$remote/checks/build.log"
export PYTHONPATH="$PWD/.runtime/astra_host:$PWD"
"$python" -c 'import _engine_lite; print(_engine_lite.__file__)' | tee "$remote/checks/extension.txt"
"$python" -m unittest tests.v5.test_lite_default tests.v5.test_teacher_state_reuse -v 2>&1 | tee "$remote/checks/unittest.txt"
