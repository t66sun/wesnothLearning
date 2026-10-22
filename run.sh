#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$TASK_ROOT"
[[ -f .runtime/environment.sh ]] && source .runtime/environment.sh
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export TMPDIR="$TASK_ROOT/tmp"
case "${1:-}" in
    run|collect|train|evaluate|export|report|package|import-human|control|audit|benchmark|rules|freeze-map) exec .venv/bin/python -m learning "$@" ;;
    *) exec .venv/bin/python -m learning run "$@" ;;
esac
