#!/usr/bin/env bash
# Isolated extension for the shipped source; never replace a running experiment's build.
set -euo pipefail
export PATH="/home/tongshu/.cargo/bin:$PATH"
export CARGO_TARGET_DIR=/home/tongshu/.cache/teacher_integration_target
export CARGO_BUILD_JOBS=8 CARGO_NET_OFFLINE=true
python=/home/tongshu/venv/bin/python
"$python" -m maturin build --release --manifest-path engine_lite/Cargo.toml --out .runtime/teacher_wheels
"$python" -m pip install --no-deps --target .runtime/teacher_host .runtime/teacher_wheels/*.whl
export PYTHONPATH="$PWD/.runtime/teacher_host:$PWD"
"$python" -c 'import _engine_lite; print("HOST", _engine_lite.HOST_VERSION, _engine_lite.__file__)'
exec "$@"
