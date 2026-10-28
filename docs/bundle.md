# Ubuntu 24.04 training bundle

> Language: English | [中文](bundle_zh.md)

Updated 2026-10-25. The extraction-ready archive is the only artifact the training machine receives. Architecture and parameters are authoritative in [architecture.md](architecture.md); remaining acceptance work is in [TEST.md](TEST.md) (`PKG1`); third-party licensing is in [THIRD_PARTY.md](THIRD_PARTY.md).

## 1. What the archive is and is not

The archive is one deterministic `tar.gz` written by `learning/bundle.py` from this repository. It carries the source tree, the frozen `1.18.8-training` rule package, the curated human games and the datasets, plus only the opponent packages the declared teacher consumes, so a clean Ubuntu machine can install and run training without a git remote or a copied working tree.

It is not a machine image, a Python environment, a training result or evidence. It never contains:

- `.git`, a virtual environment, caches, `.runtime/`, `runs/`, `verification/`, `delivery/`, `tmp/`;
- the historical `data/rules/1.18.8` package, the raw replay dump `data/humanData`, or the untracked `data/references` excerpts;
- compiled suffixes (`.pyc`, `.pyo`, `.pyd`, `.dll`, `.exe`), Cargo `target/`, or `AGENTS.md`.

Because run state and validation evidence are excluded, nothing in the archive records a training run, a strength result or a delivery decision. Building the archive installs nothing and starts nothing.

`docs/bundle.md` and `docs/bundle_zh.md` are required members: the builder refuses to produce an archive without them.

## 2. Build and verify (maintainer side)

```bash
python -m learning bundle --output dist/WesnothLearning-training.tar.gz
python -m learning bundle --output dist/WesnothLearning-training.tar.gz \
    --wheel dist/wesnoth_learning_lite-0.2.0-cp312-cp312-manylinux_2_34_x86_64.whl \
    --created-at 2026-10-25T00:00:00Z
python -m learning verify-bundle dist/WesnothLearning-training.tar.gz
python -m learning verify-bundle dist/WesnothLearning-training.tar.gz --require-wheel
```

- `--output` must resolve inside the project root and must not already exist; the builder writes a temporary file and renames it, so a failed build leaves no partial archive.
- `--wheel` copies a prebuilt extension into `dist/` inside the archive and records it as `build.wheel`. The name must end in `.whl` and contain both `manylinux` and `x86_64`; anything else is rejected.
- `--created-at` accepts an ISO 8601 timestamp and normalizes it to UTC `YYYY-MM-DDTHH:MM:SSZ`. With a fixed stamp and unchanged inputs the archive bytes are reproducible; without it the builder stamps the current time.
- The builder prints a JSON summary (`archive`, `sha256`, `files`, `bytes`, `created_at`, `source`, `rules`, `wheel`). Record the archive `sha256` next to the release note.
- `verify-bundle` prints a JSON report with `ok` and `errors`, and exits with status 2 when `ok` is false. `--require-wheel` fails an archive that bundles no extension wheel, which is what an offline Rust-free install needs.

The builder refuses to package an inconsistent rule identity: `rules.json` must match `catalog-summary.json` in `rules_file_sha256`, `source_hash`, `unit_count` and `terrain_count`.

### Archive invariants

| Property | Value |
| --- | --- |
| Root member | `WesnothLearning/` |
| Members | Sorted, one gzip member, PAX tar |
| Timestamps | `mtime` 0 for every member; gzip header `mtime` 0 |
| Ownership | `uid`/`gid` 0, empty `uname`/`gname` |
| File mode | `0644`, or `0755` for `*.sh` |
| Directory mode | `0755` |
| Manifests | `BUNDLE_MANIFEST.json` (schema 1) and GNU `SHA256SUMS` at the archive root |

`SHA256SUMS` lists every member except itself, with paths relative to the archive root, so `cd WesnothLearning && sha256sum --check SHA256SUMS` works after extraction.

The verifier checks the archive as an archive: readable gzip tar, single `WesnothLearning/` root, no absolute or parent-escaping or duplicate members, no member of an exclusion class, all required paths present, exact modes, manifest schema and Ubuntu 24.04 `x86_64` target, every manifest size/hash/mode and the totals, the rules identity against the archived `rules.json` and `catalog-summary.json`, `identities.teacher` against the rules and the shipped `lua/stock_rca_capture` sources, every listed opponent and the curated human file, the optional wheel, and full `SHA256SUMS` format and coverage. The stock 1.18.8 RCA declares no package capability, so a stock bundle lists no opponent and ships none; a listed package the teacher does not declare is an error. Manifests without `identities` are historical and keep the opponents they were shipped with.

## 3. Install on a clean Ubuntu 24.04 machine

Target: clean Ubuntu 24.04 `x86_64`, `sudo` or root, network access. Ubuntu 22.04 is accepted with a note that 24.04 is the target; any other distribution or architecture exits 2 before touching the system.

```bash
tar -xzf WesnothLearning-training.tar.gz
cd WesnothLearning
./setup.sh --preflight          # exit 0, no writes, verifies SHA256SUMS
./setup.sh --device cpu         # full install; CPU is the reference device
```

`--preflight` runs before the OS gate and before any directory is created. It confirms the required inputs exist and, when `BUNDLE_MANIFEST.json` is present, verifies `SHA256SUMS` with `sha256sum`. It exits 1 on a missing input, a missing `SHA256SUMS`, or a modified file; in a development checkout without a manifest it prints that checksum verification is skipped and still exits 0. Preflight is the tamper check for an extracted copy.

Options:

| Option | Effect |
| --- | --- |
| `--device cpu` | CPU wheels for torch 2.9.1 |
| `--device cu128` | CUDA 12.8 wheels for torch 2.9.1 |
| `--device auto` | Default: `cu128` only when `nvidia-smi` runs successfully, otherwise `cpu` |
| `--wesnoth PATH` | Reuse an existing Wesnoth 1.18.8 binary instead of building the pinned tarball |
| `--skip-system-deps` | Skip `apt-get`; every system package must already be installed |
| `--jobs N` | Parallel Cargo and Wesnoth build jobs (default: CPU count) |
| `-h`, `--help` | Print the usage text and exit without changing anything |

`WESNOTH_EXE` and `BUILD_JOBS` supply the same two values from the environment.

What a full run does, in order:

1. `apt-get update` and install the build/runtime packages (Python 3, venv, curl, build-essential, cmake, ninja, pkg-config, Boost, SDL2 and its image/mixer/ttf modules, Pango, readline, vorbis, ICU, OpenSSL, bz2, fontconfig, harfbuzz, fribidi, zlib, dbus, libcurl). Root runs directly; otherwise `sudo` is required.
2. Create `.venv`, install pip 25.3, then `requirements.txt` (numpy, lupa, matplotlib and their pinned transitive packages; torch is not in that file).
3. Install `torch==2.9.1` from `https://download.pytorch.org/whl/<device>` and stamp the device under `.runtime/stamps/`.
4. Install `_engine_lite`. A bundled wheel in `dist/` named `wesnoth_learning_lite-*.whl` (the maturin project name) is installed with `pip --force-reinstall --no-deps`; the legacy `_engine_lite-*` and `engine_lite-*` names are accepted too. Without a wheel the script installs `maturin`, installs the stable Rust toolchain through rustup only when `cargo` is absent, and runs `maturin develop --release` in `engine_lite/`. Rust is never installed when a wheel is bundled.
5. Check the rule and engine identity: `rules.json` against `catalog-summary.json`, `source_version` 1.18.8, and the extension's `ENGINE_VERSION`/`RNG_VERSION`/`COMBAT_VERSION` against `learning.adapters`. A stale extension build fails here.
6. Reuse a Wesnoth binary that reports `1.18.8`, or download `wesnoth-1.18.8.tar.bz2`, verify SHA-256 `fce3bd71d4ed32c9d11c0f707d19743cec6adf5c34761fab94ab72754aaedd89`, then configure and build with CMake/Ninja into `.runtime/build`, installing to `.runtime/install` with server, campaign server, tests and NLS disabled.
7. Write `.runtime/environment.sh` (`export WESNOTH_EXE=…`) and `.runtime/installed-dependencies.txt`, then check `import torch, _engine_lite`, `python -m learning --help` and `wesnoth --simple-version`.

The run is idempotent: an installed venv, the pinned torch for the requested device, installed requirements matching the `requirements.txt` digest stamp, and a valid Wesnoth 1.18.8 binary are reused instead of rebuilt. The extension is the exception: every setup run reinstalls it from a bundled wheel or otherwise rebuilds it with `maturin develop --release`. Setup logs to `.cache/setup.log` through `tee`, so an interrupted run keeps its history. It starts no sampling, no game and no training.

## 4. Start training

```bash
./train.sh --help       # defaults and overrides; creates nothing
./train.sh              # only after explicit user instruction
```

Defaults: `HOURS=18`, `WORKERS=8`, `DEVICE=cpu`, `TRAINER_THREADS=1`, `ENGINE=lite`, `EVALUATION_ENGINE=lite`, BC targets 300/600/400 for duel/ffa4/team2v2, `FORMATS="duel ffa4 team2v2"`, and no run directory (so `runs/v5_<YYYYMMDD_HHMMSS>` is created). Every default is overridable by the matching environment variable or flag; `--` passes everything after it to `python -m learning run` unchanged. The script calls `learning run` with `--native-bc-games 0 0 0` and `--wesnoth "$WESNOTH_EXE"`.

`train.sh` refuses to start when `.runtime/environment.sh` is missing, `.venv/bin/python` is missing, `_engine_lite` is not importable in that venv, `WESNOTH_EXE` is unset or not executable, or the target run directory already exists. The run directory is created by `learning`, and output is duplicated into `runs/logs/<run name>.log`.

Starting work requires an explicit user instruction. A successful `setup.sh`, a passing preflight or a built archive is not authorization to collect games or train. The bundle acceptance proves installation only: it never proves convergence, strength or a usable model.

## 5. Archive layout

```text
WesnothLearning/
  BUNDLE_MANIFEST.json      schema, target, source commit, per-file size/sha256/mode, identities.teacher, data identities, wheel, totals
  SHA256SUMS                GNU sha256sum lines for every other member
  README.md  LICENSE  requirements.txt  .gitattributes
  setup.sh  run.sh  train.sh              mode 0755
  learning/                 coordinator, adapters, model, training, rewards, evaluation, bundle builder
  lua/                      shared legal observation/candidates/memory/rewards; stock_rca_capture/ is the teacher event capture
  engine_lite/              Rust/PyO3 lite engine sources (built by setup.sh when no wheel is bundled)
  vendor/                   vendored WesnothArena native v2 SDK
  tests/                    behavior test suites
  benchmarks/               engine benchmark contracts
  docs/                     maintained documentation, including this file and its Chinese mirror
  data/rules/1.18.8-training/   frozen 587-unit training rule package
  data/humanData_curated/   curated 1.18.8 human games for BC
  data/opponents/           opponent packages a declared teacher needs; absent for the stock 1.18.8 RCA
  data/datasets/            dataset import inputs; currently human/import.json
  dist/<wheel>              optional prebuilt manylinux x86_64 _engine_lite wheel
```

Not present: `.git`, `.venv`, `__pycache__`, `.cache`, `.runtime`, `runs`, `verification`, `delivery`, `tmp`, `data/references`, `data/humanData`, `data/rules/1.18.8`, compiled suffixes, Cargo `target/`, `AGENTS.md`. The manifest records this list under `excluded`; the verifier independently rejects members belonging to the same exclusion classes, using its own rules rather than the manifest list.

## 6. Checks and evidence status

Observed on 2026-10-25 on the reference workstation:

- `python -m learning bundle --help` and `python -m learning verify-bundle --help` exit 0.
- `python -m unittest tests.test_bundle tests.test_bundle_scripts` passes 27 tests: 16 builder/verifier tests and 11 setup/train script checks (including `bash -n` parsing, preflight acceptance and rejection, wheel-name recognition, `--help` creating nothing and the refusal without setup).
- `bash -n setup.sh run.sh train.sh` exits 0.

The only archive-level checks that exist are the builder and the static verifier described above. They read the tar, recompute hashes and compare the manifest; they execute nothing from the archive.

**NOT RUN:** no Ubuntu 24.04 extraction, `--preflight` run, `setup.sh` install, apt/pip/torch install, Rust or maturin build, Wesnoth 1.18.8 build, `train.sh` start, and no real archive has been built from this tree at documentation time. Those remain `PKG1` in [TEST.md](TEST.md) and are recorded in `verification/training_bundle_ubuntu24_<date>/REPORT.md` once executed. Nothing here is a passed runtime acceptance.

## 7. Troubleshooting

**`preflight: SHA256SUMS verification failed`** — the extracted copy differs from the archive. Re-extract into a fresh directory and rerun `./setup.sh --preflight`; do not repair hashes by hand. `preflight: BUNDLE_MANIFEST.json is present but SHA256SUMS is missing` means the extraction was incomplete.

**`setup.sh: Ubuntu is required` / `Ubuntu 22.04/24.04 is required` / `Ubuntu x86_64 is required`** — the OS gate reads `/etc/os-release` and `uname -m` before any change. Use Ubuntu 24.04 `x86_64`; 22.04 runs with a note that 24.04 is the target.

**`setup.sh: sudo is required for system packages`** — rerun as root, install `sudo`, or pass `--skip-system-deps` after installing the packages yourself.

**Rust or extension problems** — without a bundled wheel, `setup.sh` installs rustup only when `cargo` is missing; after that, `maturin develop --release` in `engine_lite/` must succeed. `identity: engine build … does not match declared …` means the extension is stale: rerun setup so the extension is rebuilt against the current sources.

**Wheel not picked up** — two different rules apply. `learning/bundle.py` accepts a `--wheel` only when the name ends in `.whl` and contains both `manylinux` and `x86_64`, and `verify-bundle --require-wheel` checks the wheel the archive records, so a release intended for Rust-free installs fails when no wheel was bundled. Separately, `setup.sh` only searches `dist/` for names starting `wesnoth_learning_lite-`, `_engine_lite-` or `engine_lite-`; it does not require `manylinux` or `x86_64` in the name, and `--preflight` prints the file it found.

**`setup.sh: Wesnoth version mismatch, 1.18.8 is required`** — the binary setup resolved to does not report `1.18.8`. A `--wesnoth`/`WESNOTH_EXE` binary that is not 1.18.8 is ignored in favour of the pinned tarball, so this message means either the reused install or the fresh build is wrong: read `.cache/setup.log` and pass a genuine 1.18.8 binary with `--wesnoth /path/to/wesnoth`.

**`train.sh: .runtime/environment.sh is missing; run ./setup.sh first`** (and the sibling refusals for the venv, `_engine_lite` and `WESNOTH_EXE`) — the environment is incomplete; run `./setup.sh` in the same directory. `experiment directory already exists` means the timestamped or explicit run directory is taken; use `--run-dir` with a new name.

## Related documents

- [architecture.md](architecture.md): structure, parameters, implemented and unimplemented scope.
- [TEST.md](TEST.md): the `PKG1` acceptance item and the remaining minimal plans.
- [THIRD_PARTY.md](THIRD_PARTY.md): licensing of the bundled third-party components.
- [instructions.md](instructions.md): server takeover, start/resume, maintenance and tuning.
