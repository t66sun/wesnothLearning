#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$TASK_ROOT"
device=cu128
skip_system=0
game_exe="${WESNOTH_EXE:-}"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --device) device="$2"; shift 2 ;;
        --wesnoth) game_exe="$2"; shift 2 ;;
        --skip-system-deps) skip_system=1; shift ;;
        *) echo "Unknown argument: $1" >&2; exit 2 ;;
    esac
done
[[ "$(uname -s)" == Linux && "$(uname -m)" == x86_64 ]] || { echo 'Ubuntu x86_64 required' >&2; exit 2; }
source /etc/os-release
[[ "$ID" == ubuntu && ( "$VERSION_ID" == 22.04 || "$VERSION_ID" == 24.04 ) ]] || { echo 'Ubuntu 22.04/24.04 required' >&2; exit 2; }
mkdir -p .cache/pip .cache/downloads .runtime tmp
export TMPDIR="$TASK_ROOT/tmp" PIP_CACHE_DIR="$TASK_ROOT/.cache/pip"
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
exec > >(tee -a "$TASK_ROOT/.cache/setup.log") 2>&1
if [[ $skip_system == 0 ]]; then
    if [[ $EUID == 0 ]]; then SUDO=(); else SUDO=(sudo); fi
    "${SUDO[@]}" apt-get update
    "${SUDO[@]}" apt-get install -y python3 python3-venv python3-dev curl ca-certificates \
        build-essential cmake ninja-build pkg-config libboost-all-dev \
        libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev \
        libpango1.0-dev libreadline-dev libvorbis-dev libicu-dev libssl-dev \
        libbz2-dev libfontconfig1-dev libharfbuzz-dev libfribidi-dev zlib1g-dev libdbus-1-dev libcurl4-openssl-dev
fi
python3 -m venv .venv
.venv/bin/python -m pip install pip==25.3
if [[ "$device" == auto ]]; then
    if command -v nvidia-smi >/dev/null && nvidia-smi >/dev/null 2>&1; then device=cu128; else device=cpu; fi
fi
[[ "$device" == cpu || "$device" == cu128 ]] || { echo '--device must be cpu/cu128/auto' >&2; exit 2; }
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install torch==2.9.1 --index-url "https://download.pytorch.org/whl/$device"
if [[ -z "$game_exe" ]]; then game_exe="$(command -v wesnoth || true)"; fi
version=''
if [[ -n "$game_exe" && -x "$game_exe" ]]; then version="$("$game_exe" --simple-version 2>/dev/null || true)"; fi
if [[ "$version" != 1.18.8 ]]; then
    archive="$TASK_ROOT/.cache/downloads/wesnoth-1.18.8.tar.bz2"
    if [[ ! -f "$archive" ]]; then
        curl --fail --location --retry 3 --output "$archive.part" \
            'https://downloads.sourceforge.net/project/wesnoth/wesnoth-1.18/wesnoth-1.18.8/wesnoth-1.18.8.tar.bz2'
        mv -- "$archive.part" "$archive"
    fi
    echo "fce3bd71d4ed32c9d11c0f707d19743cec6adf5c34761fab94ab72754aaedd89  $archive" | sha256sum --check -
    tar -xjf "$archive" -C .runtime
    cmake -S .runtime/wesnoth-1.18.8 -B .runtime/build -G Ninja \
        -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$TASK_ROOT/.runtime/install" \
        -DENABLE_SERVER=OFF -DENABLE_CAMPAIGN_SERVER=OFF -DENABLE_TESTS=OFF -DENABLE_NLS=OFF
    cmake --build .runtime/build --parallel "${BUILD_JOBS:-4}"
    cmake --install .runtime/build
    game_exe="$TASK_ROOT/.runtime/install/bin/wesnoth"
fi
[[ "$("$game_exe" --simple-version)" == 1.18.8 ]] || { echo 'Wesnoth version mismatch' >&2; exit 1; }
printf 'export WESNOTH_EXE=%q\n' "$game_exe" > .runtime/environment.sh
.venv/bin/python -m pip freeze > .runtime/installed-dependencies.txt
printf 'Environment ready (%s). No sampling started.\n' "$device"
