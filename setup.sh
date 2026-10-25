#!/usr/bin/env bash
# Prepare one Ubuntu 24.04 extraction of the training bundle: Python venv,
# pinned torch, the Rust _engine_lite extension and a pinned Wesnoth 1.18.8.
# No sampling or training is started here.
set -euo pipefail

TASK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$TASK_ROOT"

usage() {
    cat <<'EOF'
Usage: ./setup.sh [options]

Options:
  -h, --help              Show this help and exit; nothing is changed.
      --preflight         Check bundle integrity and required inputs only.
                          Exit 0 without an OS gate, downloads or writes.
      --device DEVICE     cpu, cu128 or auto (default: auto; cuda only when
                          nvidia-smi works).
      --wesnoth PATH      Use an existing Wesnoth 1.18.8 binary instead of
                          building the pinned tarball.
      --skip-system-deps  Do not run apt-get; all system packages must already
                          be installed.
      --jobs N            Parallel build jobs for Cargo and Wesnoth (default:
                          the number of CPUs).

Environment: WESNOTH_EXE (default game binary), BUILD_JOBS (default --jobs).

The script is idempotent: an installed venv, pinned torch, extension and
Wesnoth binary are reused. Then start training with ./train.sh.
EOF
}

device=auto
skip_system=0
preflight=0
jobs="${BUILD_JOBS:-}"
game_exe="${WESNOTH_EXE:-}"

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help) usage; exit 0 ;;
        --preflight) preflight=1; shift ;;
        --device)
            [[ $# -ge 2 ]] || { echo 'setup.sh: --device needs a value' >&2; exit 2; }
            device="$2"; shift 2 ;;
        --wesnoth)
            [[ $# -ge 2 ]] || { echo 'setup.sh: --wesnoth needs a path' >&2; exit 2; }
            game_exe="$2"; shift 2 ;;
        --skip-system-deps) skip_system=1; shift ;;
        --jobs)
            [[ $# -ge 2 ]] || { echo 'setup.sh: --jobs needs a number' >&2; exit 2; }
            jobs="$2"; shift 2 ;;
        *) echo "setup.sh: unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

case "$device" in
    cpu|cu128|auto) ;;
    *) echo "setup.sh: --device must be cpu, cu128 or auto, got '$device'" >&2; exit 2 ;;
esac
if [[ -n "$jobs" && ! "$jobs" =~ ^[1-9][0-9]*$ ]]; then
    echo "setup.sh: --jobs must be a positive integer, got '$jobs'" >&2; exit 2
fi
if [[ $skip_system == 0 && $preflight == 0 && $EUID != 0 ]] && ! command -v sudo >/dev/null 2>&1; then
    echo 'setup.sh: sudo is required for system packages; rerun as root or pass --skip-system-deps' >&2
    exit 2
fi

required=(
    learning/__main__.py
    engine_lite/Cargo.toml
    engine_lite/pyproject.toml
    data/rules/1.18.8-training/rules.json
    data/rules/1.18.8-training/catalog-summary.json
    data/opponents/gpt6astra.zip
    data/humanData_curated/games.jsonl
    run.sh
    train.sh
)

preflight_check() {
    local missing=() path
    for path in "${required[@]}"; do
        [[ -f "$path" ]] || missing+=("$path")
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        printf 'preflight: missing required input: %s\n' "${missing[@]}" >&2
        exit 1
    fi
    if [[ -f BUNDLE_MANIFEST.json ]]; then
        if [[ ! -f SHA256SUMS ]]; then
            echo 'preflight: BUNDLE_MANIFEST.json is present but SHA256SUMS is missing; re-extract the archive' >&2
            exit 1
        fi
        command -v sha256sum >/dev/null 2>&1 || { echo 'preflight: sha256sum (coreutils) is required' >&2; exit 1; }
        if ! sha256sum --check --quiet SHA256SUMS; then
            echo 'preflight: SHA256SUMS verification failed; the archive is incomplete or modified' >&2
            exit 1
        fi
        echo 'preflight: bundle checksums verified'
    else
        echo 'preflight: development checkout (no BUNDLE_MANIFEST.json); checksum verification skipped'
    fi
    printf 'preflight: ok (%d required paths present) in %s\n' "${#required[@]}" "$TASK_ROOT"
}

if [[ $preflight == 1 ]]; then
    preflight_check
    exit 0
fi

[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] || {
    echo 'setup.sh: Ubuntu x86_64 is required' >&2; exit 2; }
[[ -r /etc/os-release ]] || { echo 'setup.sh: /etc/os-release is missing; Ubuntu is required' >&2; exit 2; }
# shellcheck disable=SC1091
source /etc/os-release
[[ "${ID:-}" == ubuntu ]] || { echo "setup.sh: Ubuntu is required, found '${ID:-unknown}'" >&2; exit 2; }
[[ "${VERSION_ID:-}" == 22.04 || "${VERSION_ID:-}" == 24.04 ]] || {
    echo "setup.sh: Ubuntu 22.04/24.04 is required (24.04 is the target), found '${VERSION_ID:-unknown}'" >&2; exit 2; }
if [[ "${VERSION_ID:-}" != 24.04 ]]; then
    echo "setup.sh: note: Ubuntu ${VERSION_ID} is supported but 24.04 is the target platform" >&2
fi

mkdir -p .cache/pip .cache/downloads .runtime/stamps tmp runs/logs
export TMPDIR="$TASK_ROOT/tmp"
export PIP_CACHE_DIR="$TASK_ROOT/.cache/pip"
export PIP_DISABLE_PIP_VERSION_CHECK=1
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
exec > >(tee -a "$TASK_ROOT/.cache/setup.log") 2>&1

echo "setup.sh: $(date -Is) root=$TASK_ROOT device=$device"
echo "setup.sh: $(uname -srm), Ubuntu ${VERSION_ID}"

if [[ -z "$jobs" ]]; then
    jobs="$(nproc 2>/dev/null || echo 4)"
fi

if [[ $skip_system == 0 ]]; then
    if [[ $EUID == 0 ]]; then SUDO=(env DEBIAN_FRONTEND=noninteractive); else SUDO=(sudo env DEBIAN_FRONTEND=noninteractive); fi
    "${SUDO[@]}" apt-get update
    "${SUDO[@]}" apt-get install -y \
        python3 python3-venv python3-dev curl ca-certificates \
        build-essential cmake ninja-build pkg-config libboost-all-dev \
        libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
        libpango1.0-dev libreadline-dev libvorbis-dev libicu-dev libssl-dev \
        libbz2-dev libfontconfig1-dev libharfbuzz-dev libfribidi-dev zlib1g-dev \
        libdbus-1-dev libcurl4-openssl-dev
else
    echo 'setup.sh: --skip-system-deps: not touching apt'
fi

if [[ ! -x .venv/bin/python ]]; then
    command -v python3 >/dev/null 2>&1 || { echo 'setup.sh: python3 is not installed (python3-venv)' >&2; exit 1; }
    python3 -m venv .venv
fi
PY="$TASK_ROOT/.venv/bin/python"
export VIRTUAL_ENV="$TASK_ROOT/.venv"
export PATH="$VIRTUAL_ENV/bin:$PATH"
"$PY" -m pip install --quiet pip==25.3
echo "setup.sh: $("$PY" --version)"

sha_of() { sha256sum "$1" | cut -d' ' -f1; }
stamp_matches() {
    local stamp="$1" digest="$2"
    [[ -f "$stamp" && "$(cat "$stamp")" == "$digest" ]]
}

requirements_stamp="$TASK_ROOT/.runtime/stamps/requirements.sha256"
requirements_digest="$(sha_of requirements.txt)"
if stamp_matches "$requirements_stamp" "$requirements_digest"; then
    echo 'setup.sh: requirements.txt unchanged; keeping installed Python packages'
else
    "$PY" -m pip install -r requirements.txt
    printf '%s\n' "$requirements_digest" > "$requirements_stamp"
fi

if [[ "$device" == auto ]]; then
    if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
        device=cu128
    else
        device=cpu
    fi
    echo "setup.sh: --device auto resolved to $device"
fi

if [[ "$("$PY" -c 'import torch;print(torch.__version__)' 2>/dev/null || true)" == 2.9.1* ]] \
        && stamp_matches "$TASK_ROOT/.runtime/stamps/torch-$device" '2.9.1'; then
    echo "setup.sh: torch 2.9.1 ($device) already installed"
else
    "$PY" -m pip install torch==2.9.1 --index-url "https://download.pytorch.org/whl/$device"
    printf '2.9.1\n' > "$TASK_ROOT/.runtime/stamps/torch-$device"
fi

"$PY" -m pip install 'maturin>=1.7,<2'

if ! command -v cargo >/dev/null 2>&1; then
    echo 'setup.sh: cargo is absent; installing the stable Rust toolchain via rustup'
    command -v curl >/dev/null 2>&1 || { echo 'setup.sh: curl is required to install Rust (curl)' >&2; exit 1; }
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain stable
    [[ -f "$HOME/.cargo/env" ]] || { echo "setup.sh: rustup finished without $HOME/.cargo/env" >&2; exit 1; }
    # shellcheck disable=SC1091
    source "$HOME/.cargo/env"
fi
command -v cargo >/dev/null 2>&1 || { echo 'setup.sh: cargo is still missing after rustup; install the Rust toolchain' >&2; exit 1; }
export CARGO_BUILD_JOBS="$jobs"

wheel_path=''
for candidate in "$TASK_ROOT"/dist/_engine_lite-*.whl; do
    if [[ -f "$candidate" ]]; then
        wheel_path="$candidate"
        break
    fi
done
if [[ -n "$wheel_path" ]]; then
    echo "setup.sh: installing prebuilt extension $wheel_path"
    "$PY" -m pip install --force-reinstall --no-deps "$wheel_path"
else
    command -v maturin >/dev/null 2>&1 || { echo 'setup.sh: maturin is missing from the venv' >&2; exit 1; }
    echo 'setup.sh: building engine_lite with maturin (release)'
    ( cd engine_lite && maturin develop --release )
fi

echo 'setup.sh: checking rule identity and engine build identity'
"$PY" - "$TASK_ROOT" <<'PY'
import hashlib
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
rules_dir = root / 'data/rules/1.18.8-training'
summary = json.loads((rules_dir / 'catalog-summary.json').read_text(encoding='utf-8'))
rules_path = rules_dir / 'rules.json'
digest = hashlib.sha256(rules_path.read_bytes()).hexdigest()
if summary.get('rules_file_sha256') != digest:
    sys.exit('identity: rules.json does not match catalog-summary.json rules_file_sha256')
rules = json.loads(rules_path.read_text(encoding='utf-8'))
if rules.get('source_hash') != summary.get('source_hash'):
    sys.exit('identity: catalog-summary.json source_hash differs from rules.json')
if rules.get('source_version') != '1.18.8':
    sys.exit('identity: rules.json is not native Wesnoth 1.18.8')
sys.path.insert(0, str(root))
import _engine_lite
from learning.adapters import COMBAT_VERSION, ENGINE_VERSION, RNG_VERSION
keys = ('ENGINE_VERSION', 'RNG_VERSION', 'COMBAT_VERSION')
built = tuple(getattr(_engine_lite, key, None) for key in keys)
declared = (ENGINE_VERSION, RNG_VERSION, COMBAT_VERSION)
if built != declared:
    sys.exit(f'identity: engine build {built} does not match declared {declared}; rebuild with maturin develop')
print('identity: rules source_hash=%s units=%s terrains=%s engine=%s' % (
    str(summary.get('source_hash'))[:16], summary.get('unit_count'),
    summary.get('terrain_count'), built[0]))
PY

if [[ -z "$game_exe" ]]; then
    game_exe="$(command -v wesnoth || true)"
fi
version=''
if [[ -n "$game_exe" && -x "$game_exe" ]]; then
    version="$("$game_exe" --simple-version 2>/dev/null || true)"
fi
if [[ "$version" != 1.18.8 ]]; then
    archive="$TASK_ROOT/.cache/downloads/wesnoth-1.18.8.tar.bz2"
    if [[ ! -f "$archive" ]]; then
        curl --fail --location --retry 3 --output "$archive.part" \
            'https://downloads.sourceforge.net/project/wesnoth/wesnoth-1.18/wesnoth-1.18.8/wesnoth-1.18.8.tar.bz2'
        mv -- "$archive.part" "$archive"
    fi
    printf '%s  %s\n' 'fce3bd71d4ed32c9d11c0f707d19743cec6adf5c34761fab94ab72754aaedd89' "$archive" | sha256sum --check -
    tar -xjf "$archive" -C .runtime
    cmake -S .runtime/wesnoth-1.18.8 -B .runtime/build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$TASK_ROOT/.runtime/install" \
        -DENABLE_SERVER=OFF -DENABLE_CAMPAIGN_SERVER=OFF -DENABLE_TESTS=OFF -DENABLE_NLS=OFF
    cmake --build .runtime/build --parallel "$jobs"
    cmake --install .runtime/build
    game_exe="$TASK_ROOT/.runtime/install/bin/wesnoth"
else
    echo "setup.sh: reusing Wesnoth 1.18.8 at $game_exe"
fi
[[ -x "$game_exe" ]] || { echo "setup.sh: Wesnoth binary is not executable: $game_exe" >&2; exit 1; }
[[ "$("$game_exe" --simple-version)" == 1.18.8 ]] || { echo 'setup.sh: Wesnoth version mismatch, 1.18.8 is required' >&2; exit 1; }
version=1.18.8

printf 'export WESNOTH_EXE=%q\n' "$game_exe" > .runtime/environment.sh
"$PY" -m pip freeze > .runtime/installed-dependencies.txt

echo 'setup.sh: final checks'
"$PY" -c 'import torch, _engine_lite; print("torch", torch.__version__, "| lite", _engine_lite.__file__)'
"$PY" -m learning --help >/dev/null
"$game_exe" --simple-version

printf '\nEnvironment ready (%s), Wesnoth %s at %s.\n' "$device" "$version" "$game_exe"
printf 'No sampling or training started. Next:\n'
printf '  ./train.sh                 # 18h CPU, 8 workers, duel/ffa4/team2v2\n'
printf '  ./train.sh --help          # defaults and overrides\n'
printf '  ./setup.sh --preflight     # re-check bundle integrity at any time\n'
printf 'Log: %s\n' "$TASK_ROOT/.cache/setup.log"
