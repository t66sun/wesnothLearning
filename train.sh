#!/usr/bin/env bash
# Start one fresh lite training experiment on the machine prepared by setup.sh.
# The run directory is created by learning itself; nothing is created on --help.
set -euo pipefail

TASK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$TASK_ROOT"

HOURS="${HOURS:-18}"
WORKERS="${WORKERS:-8}"
DEVICE="${DEVICE:-cpu}"
TRAINER_THREADS="${TRAINER_THREADS:-1}"
ENGINE="${ENGINE:-lite}"
EVALUATION_ENGINE="${EVALUATION_ENGINE:-lite}"
BC_DUEL="${BC_DUEL:-300}"
BC_FFA4="${BC_FFA4:-600}"
BC_TEAM2V2="${BC_TEAM2V2:-400}"
FORMATS="${FORMATS:-duel ffa4 team2v2}"
RUN_DIR="${RUN_DIR:-}"

usage() {
    cat <<'EOF'
Usage: ./train.sh [options] [-- extra learning-run arguments]

Starts one new lite experiment with the authorized defaults and logs it under
runs/logs/. Requires a successful ./setup.sh in this directory.

Options:
  -h, --help                 Show this help and exit; nothing is created.
      --hours N              Training budget in hours (default: 18).
      --workers N            Shared game workers, 1-16 (default: 8).
      --device NAME          cpu, cuda, cuda:N or auto (default: cpu).
      --trainer-threads N    CPU threads per trainer (default: 1).
      --engine NAME          native or lite (default: lite).
      --evaluation-engine NAME  native or lite (default: lite).
      --bc-games D F T       Teacher-game targets duel/ffa4/team2v2
                             (default: 300 600 400).
      --formats F [F ...]    Formats to train (default: duel ffa4 team2v2).
      --run-dir PATH         Explicit experiment directory instead of
                             runs/v5_<YYYYMMDD_HHMMSS>.
  --                         Everything after this is passed to
                             `python -m learning run` unchanged.

Environment defaults (export to override):
  HOURS=18  WORKERS=8  DEVICE=cpu  TRAINER_THREADS=1
  ENGINE=lite  EVALUATION_ENGINE=lite
  BC_DUEL=300  BC_FFA4=600  BC_TEAM2V2=400
  FORMATS="duel ffa4 team2v2"
  RUN_DIR=<empty: runs/v5_<YYYYMMDD_HHMMSS>>
EOF
}

require_value() {
    [[ $# -ge 2 ]] || { echo "train.sh: $1 needs a value" >&2; exit 2; }
}

extra=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --) shift; extra+=("$@"); break ;;
        --hours) require_value "$@"; HOURS="$2"; shift 2 ;;
        --workers) require_value "$@"; WORKERS="$2"; shift 2 ;;
        --device) require_value "$@"; DEVICE="$2"; shift 2 ;;
        --trainer-threads) require_value "$@"; TRAINER_THREADS="$2"; shift 2 ;;
        --engine) require_value "$@"; ENGINE="$2"; shift 2 ;;
        --evaluation-engine) require_value "$@"; EVALUATION_ENGINE="$2"; shift 2 ;;
        --bc-games)
            [[ $# -ge 4 ]] || { echo 'train.sh: --bc-games needs DUEL FFA4 TEAM2V2' >&2; exit 2; }
            BC_DUEL="$2"; BC_FFA4="$3"; BC_TEAM2V2="$4"; shift 4 ;;
        --formats)
            shift
            formats=()
            while [[ $# -gt 0 && "$1" != --* ]]; do formats+=("$1"); shift; done
            [[ ${#formats[@]} -gt 0 ]] || { echo 'train.sh: --formats needs at least one format' >&2; exit 2; }
            FORMATS="${formats[*]}" ;;
        --run-dir) require_value "$@"; RUN_DIR="$2"; shift 2 ;;
        *) echo "train.sh: unknown argument: $1 (use -- to pass it to learning run)" >&2; exit 2 ;;
    esac
done

if [[ -z "$RUN_DIR" ]]; then
    RUN_DIR="runs/v5_$(date +%Y%m%d_%H%M%S)"
fi

[[ "$HOURS" =~ ^[0-9]+([.][0-9]+)?$ ]] && ! [[ "$HOURS" =~ ^0*([.]0*)?$ ]] || {
    echo "train.sh: --hours must be a positive number, got '$HOURS'" >&2; exit 2; }
[[ "$WORKERS" =~ ^[0-9]+$ ]] && (( WORKERS >= 1 && WORKERS <= 16 )) || {
    echo "train.sh: --workers must be an integer in 1-16, got '$WORKERS'" >&2; exit 2; }
[[ "$TRAINER_THREADS" =~ ^[1-9][0-9]*$ ]] || {
    echo "train.sh: --trainer-threads must be a positive integer, got '$TRAINER_THREADS'" >&2; exit 2; }
case "$ENGINE" in native|lite) ;; *) echo "train.sh: --engine must be native or lite, got '$ENGINE'" >&2; exit 2 ;; esac
case "$EVALUATION_ENGINE" in native|lite) ;; *) echo "train.sh: --evaluation-engine must be native or lite, got '$EVALUATION_ENGINE'" >&2; exit 2 ;; esac
for value in "$BC_DUEL" "$BC_FFA4" "$BC_TEAM2V2"; do
    [[ "$value" =~ ^[0-9]+$ ]] || { echo "train.sh: --bc-games values must be integers, got '$value'" >&2; exit 2; }
done

if [[ ! -f .runtime/environment.sh ]]; then
    echo 'train.sh: .runtime/environment.sh is missing; run ./setup.sh first' >&2
    exit 1
fi
# shellcheck disable=SC1091
source .runtime/environment.sh
if [[ ! -x .venv/bin/python ]]; then
    echo 'train.sh: .venv/bin/python is missing; run ./setup.sh first' >&2
    exit 1
fi
if ! .venv/bin/python -c 'import _engine_lite' >/dev/null 2>&1; then
    echo 'train.sh: _engine_lite is not importable in .venv; run ./setup.sh to build it' >&2
    exit 1
fi
if [[ -z "${WESNOTH_EXE:-}" || ! -x "$WESNOTH_EXE" ]]; then
    echo "train.sh: WESNOTH_EXE is missing or not executable ('${WESNOTH_EXE:-}'); run ./setup.sh" >&2
    exit 1
fi
if [[ -e "$RUN_DIR" ]]; then
    echo "train.sh: experiment directory already exists: $RUN_DIR; use --run-dir with a new name, or pass '-- --resume <RUN_DIR>' to continue an existing experiment" >&2
    exit 1
fi

export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export TMPDIR="$TASK_ROOT/tmp"

mkdir -p runs/logs
log="runs/logs/${RUN_DIR##*/}.log"
cmd=(
    .venv/bin/python -u -m learning run
    --run-dir "$RUN_DIR"
    --engine "$ENGINE" --evaluation-engine "$EVALUATION_ENGINE"
    --bc-games "$BC_DUEL" "$BC_FFA4" "$BC_TEAM2V2" --native-bc-games 0 0 0
    --device "$DEVICE" --workers "$WORKERS" --trainer-threads "$TRAINER_THREADS"
    --hours "$HOURS" --formats $FORMATS
    --wesnoth "$WESNOTH_EXE"
)
cmd+=("${extra[@]}")

printf 'train.sh: experiment %s, device %s, %s hours, %s workers, formats: %s\n' \
    "$RUN_DIR" "$DEVICE" "$HOURS" "$WORKERS" "$FORMATS"
printf 'train.sh: log %s\n' "$log"
printf 'train.sh: %s\n' "${cmd[*]}"
# Unquoted $FORMATS is intentional: it is a space-separated list of format names.
"${cmd[@]}" 2>&1 | tee -a "$log"
