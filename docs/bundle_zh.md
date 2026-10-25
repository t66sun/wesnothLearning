# Ubuntu 24.04 训练归档包

> 语言：[English](bundle.md) | 中文

更新于 2026-10-25。可解压即用的归档包是训练机器收到的唯一产物。架构与参数以 [architecture_zh.md](architecture_zh.md) 为准；剩余验收工作见 [TEST_zh.md](TEST_zh.md)（`PKG1`）；第三方许可见 [THIRD_PARTY_zh.md](THIRD_PARTY_zh.md)。

## 1. 归档包是什么、不是什么

归档包是由 `learning/bundle.py` 从本仓库写出的单个确定性 `tar.gz`。它包含源码树、冻结的 `1.18.8-training` 规则包、精选人类对局、参考对手和数据集，使干净的 Ubuntu 机器无需 git 远端或手工拷贝工作目录即可安装并运行训练。

它不是机器镜像、不是 Python 环境、不是训练结果、也不是证据。它从不包含：

- `.git`、虚拟环境、缓存、`.runtime/`、`runs/`、`verification/`、`delivery/`、`tmp/`；
- 历史 `data/rules/1.18.8` 规则包、原始回放转储 `data/humanData`，以及未入库的 `data/references` 摘录；
- 编译后缀（`.pyc`、`.pyo`、`.pyd`、`.dll`、`.exe`）、Cargo `target/`、`AGENTS.md`。

由于运行状态与验证证据被排除，归档包内没有任何内容记录某次训练、棋力结果或交付决定。构建归档包不安装任何东西，也不启动任何东西。

`docs/bundle.md` 与 `docs/bundle_zh.md` 是必需成员：缺少它们时构建器拒绝产出归档包。

## 2. 构建与校验（维护方）

```bash
python -m learning bundle --output dist/WesnothLearning-training.tar.gz
python -m learning bundle --output dist/WesnothLearning-training.tar.gz \
    --wheel dist/wesnoth_learning_lite-0.2.0-cp312-cp312-manylinux_2_34_x86_64.whl \
    --created-at 2026-10-25T00:00:00Z
python -m learning verify-bundle dist/WesnothLearning-training.tar.gz
python -m learning verify-bundle dist/WesnothLearning-training.tar.gz --require-wheel
```

- `--output` 必须解析到工程根目录之内，且目标文件不得已存在；构建器先写临时文件再改名，因此失败不会留下半成品归档包。
- `--wheel` 把预编译扩展复制进归档包内的 `dist/`，并记录为 `build.wheel`。文件名必须以 `.whl` 结尾，且同时包含 `manylinux` 与 `x86_64`，否则被拒绝。
- `--created-at` 接受 ISO 8601 时间戳，并归一化为 UTC `YYYY-MM-DDTHH:MM:SSZ`。固定时间戳且输入不变时归档包字节可复现；不传则写入当前时间。
- 构建器打印 JSON 摘要（`archive`、`sha256`、`files`、`bytes`、`created_at`、`source`、`rules`、`wheel`）。把归档包 `sha256` 记在发布说明旁。
- `verify-bundle` 打印含 `ok` 与 `errors` 的 JSON 报告，`ok` 为 false 时以状态码 2 退出。`--require-wheel` 会让未内嵌扩展 wheel 的归档包失败，这正是离线、免 Rust 安装所需要的检查。

构建器拒绝打包身份不一致的规则：`rules.json` 的 `rules_file_sha256`、`source_hash`、`unit_count`、`terrain_count` 必须与 `catalog-summary.json` 一致。

### 归档包不变量

| 属性 | 取值 |
| --- | --- |
| 根成员 | `WesnothLearning/` |
| 成员 | 排序、单 gzip 成员、PAX tar |
| 时间戳 | 每个成员 `mtime` 为 0；gzip 头 `mtime` 为 0 |
| 归属 | `uid`/`gid` 为 0，`uname`/`gname` 为空 |
| 文件权限 | `0644`，`*.sh` 为 `0755` |
| 目录权限 | `0755` |
| 清单 | 归档包根目录的 `BUNDLE_MANIFEST.json`（schema 1）与 GNU `SHA256SUMS` |

`SHA256SUMS` 列出除自身以外的全部成员，路径相对归档包根目录，因此解压后 `cd WesnothLearning && sha256sum --check SHA256SUMS` 可用。

校验器把归档包当作归档包来检查：gzip tar 可读、只有单一 `WesnothLearning/` 根、无绝对路径/越出父目录/重复成员、无排除清单中的成员、必需路径齐全、权限精确、清单 schema 与 Ubuntu 24.04 `x86_64` 目标、清单中每个文件的大小/哈希/权限与总计、规则身份与归档内 `rules.json` 及 `catalog-summary.json` 的比对、每个对手与精选人类文件、可选 wheel，以及 `SHA256SUMS` 的完整格式与覆盖。

## 3. 在干净的 Ubuntu 24.04 上安装

目标环境：干净的 Ubuntu 24.04 `x86_64`，具备 `sudo` 或 root 权限与网络。Ubuntu 22.04 会被接受，但会提示 24.04 才是目标平台；其他发行版或架构会在改动系统之前以状态码 2 退出。

```bash
tar -xzf WesnothLearning-training.tar.gz
cd WesnothLearning
./setup.sh --preflight          # 退出码 0，不写任何文件，校验 SHA256SUMS
./setup.sh --device cpu         # 完整安装；CPU 为参考设备
```

`--preflight` 在系统门禁之前、在任何目录创建之前执行。它确认必需输入存在，并在存在 `BUNDLE_MANIFEST.json` 时用 `sha256sum` 校验 `SHA256SUMS`。输入缺失、`SHA256SUMS` 缺失或文件被修改时以 1 退出；在没有清单的开发检出中，它打印跳过校验并仍以 0 退出。preflight 是解压副本的防篡改检查。

选项：

| 选项 | 作用 |
| --- | --- |
| `--device cpu` | 安装 torch 2.9.1 的 CPU wheel |
| `--device cu128` | 安装 torch 2.9.1 的 CUDA 12.8 wheel |
| `--device auto` | 默认值：仅当 `nvidia-smi` 能成功运行时用 `cu128`，否则 `cpu` |
| `--wesnoth PATH` | 复用已有的 Wesnoth 1.18.8 可执行文件，不构建固定压缩包 |
| `--skip-system-deps` | 跳过 `apt-get`；系统包须已全部安装 |
| `--jobs N` | Cargo 与 Wesnoth 并行构建任务数（默认：CPU 核数） |
| `-h`、`--help` | 打印用法并退出，不改变任何东西 |

`WESNOTH_EXE` 与 `BUILD_JOBS` 可从环境提供同样两个值。

完整运行的执行顺序：

1. `apt-get update` 并安装构建/运行包（Python 3、venv、curl、build-essential、cmake、ninja、pkg-config、Boost、SDL2 及其 image/mixer/ttf 模块、Pango、readline、vorbis、ICU、OpenSSL、bz2、fontconfig、harfbuzz、fribidi、zlib、dbus、libcurl）。root 直接执行，否则需要 `sudo`。
2. 创建 `.venv`，安装 pip 25.3，再安装 `requirements.txt`（numpy、lupa、matplotlib 及其固定版本的传递依赖；torch 不在该文件中）。
3. 从 `https://download.pytorch.org/whl/<device>` 安装 `torch==2.9.1`，并在 `.runtime/stamps/` 下按设备打戳。
4. 安装 `_engine_lite`。`dist/` 中名为 `wesnoth_learning_lite-*.whl`（maturin 工程名）的内嵌 wheel 用 `pip --force-reinstall --no-deps` 安装；旧的 `_engine_lite-*`、`engine_lite-*` 名称同样被接受。没有 wheel 时脚本安装 `maturin`，仅当 `cargo` 缺失才通过 rustup 安装稳定版 Rust 工具链，然后在 `engine_lite/` 执行 `maturin develop --release`。内嵌 wheel 时绝不安装 Rust。
5. 检查规则与引擎身份：`rules.json` 对 `catalog-summary.json`、`source_version` 为 1.18.8，以及扩展的 `ENGINE_VERSION`/`RNG_VERSION`/`COMBAT_VERSION` 对 `learning.adapters`。扩展构建过期会在此失败。
6. 复用报告 `1.18.8` 的 Wesnoth 可执行文件，或下载 `wesnoth-1.18.8.tar.bz2`，校验 SHA-256 `fce3bd71d4ed32c9d11c0f707d19743cec6adf5c34761fab94ab72754aaedd89`，随后用 CMake/Ninja 配置并构建到 `.runtime/build`，安装到 `.runtime/install`，关闭 server、campaign server、tests 与 NLS。
7. 写 `.runtime/environment.sh`（`export WESNOTH_EXE=…`）与 `.runtime/installed-dependencies.txt`，然后检查 `import torch, _engine_lite`、`python -m learning --help` 与 `wesnoth --simple-version`。

该运行是幂等的：已安装的 venv、按请求设备固定版本的 torch、与 `requirements.txt` 摘要戳一致的已装依赖、可用的扩展以及 Wesnoth 1.18.8 可执行文件都会被复用而非重建。安装日志通过 `tee` 写入 `.cache/setup.log`，中断的运行保留历史。它不启动采样、对局或训练。

## 4. 启动训练

```bash
./train.sh --help       # 打印默认值与可覆盖项；不创建任何东西
./train.sh              # 仅在用户明确指令后执行
```

默认值：`HOURS=18`、`WORKERS=8`、`DEVICE=cpu`、`TRAINER_THREADS=1`、`ENGINE=lite`、`EVALUATION_ENGINE=lite`、BC 目标为单挑/ffa4/2v2 的 300/600/400、`FORMATS="duel ffa4 team2v2"`，且不指定运行目录（因此创建 `runs/v5_<YYYYMMDD_HHMMSS>`）。每个默认值都可由同名环境变量或命令行参数覆盖；`--` 之后的全部内容原样传给 `python -m learning run`。脚本以 `--native-bc-games 0 0 0` 与 `--wesnoth "$WESNOTH_EXE"` 调用 `learning run`。

以下情况 `train.sh` 拒绝启动：缺少 `.runtime/environment.sh`、缺少 `.venv/bin/python`、该 venv 中 `_engine_lite` 不可导入、`WESNOTH_EXE` 未设置或不可执行，或目标运行目录已存在。运行目录由 `learning` 创建，输出同时写入 `runs/logs/<运行目录名>.log`。

启动工作必须有用户明确指令。成功的 `setup.sh`、通过的 preflight 或已构建的归档包都不是采集对局或训练的授权。归档包验收只证明安装可用：它从不证明收敛、棋力或模型可用。

## 5. 归档包布局

```text
WesnothLearning/
  BUNDLE_MANIFEST.json      schema、目标、源码提交、逐文件大小/sha256/权限、数据身份、wheel、总计
  SHA256SUMS                其余全部成员的 GNU sha256sum 行
  README.md  LICENSE  requirements.txt  .gitattributes
  setup.sh  run.sh  train.sh              权限 0755
  learning/                 协调器、适配器、模型、训练、奖励、评测、归档构建器
  lua/                      两引擎共用的合法观测/候选/记忆/奖励
  engine_lite/              Rust/PyO3 精简引擎源码（无内嵌 wheel 时由 setup.sh 构建）
  vendor/                   内置的 WesnothArena native v2 SDK
  tests/                    行为测试套件
  benchmarks/               引擎基准契约
  docs/                     维护文档，含本文件及其英文原文
  data/rules/1.18.8-training/   冻结的 587 单位训练规则包
  data/humanData_curated/   用于 BC 的 1.18.8 精选人类对局
  data/opponents/           冻结的参考对手包（Astra）
  data/datasets/            人类/教师数据与序列索引
  dist/<wheel>              可选的预编译 manylinux x86_64 `_engine_lite` wheel
```

不包含：`.git`、`.venv`、`__pycache__`、`.cache`、`.runtime`、`runs`、`verification`、`delivery`、`tmp`、`data/references`、`data/humanData`、`data/rules/1.18.8`、编译后缀、Cargo `target/`、`AGENTS.md`。清单在 `excluded` 下记录该清单，校验器拒绝任何匹配它的成员。

## 6. 检查与证据状态

2026-10-25 在参考工作站上观察到：

- `python -m learning bundle --help` 与 `python -m learning verify-bundle --help` 退出码为 0。
- `python -m unittest tests.test_bundle tests.test_bundle_scripts` 通过 27 项测试：16 项构建器/校验器测试与 11 项 setup/train 脚本检查（含 `bash -n` 解析、preflight 接受与拒绝、wheel 名称识别、`--help` 不创建任何东西、以及未安装时拒绝启动）。
- `bash -n setup.sh run.sh train.sh` 退出码为 0。

现存的归档包层面检查只有上述构建器与静态校验器。它们读取 tar、重算哈希并与清单比对；不执行归档包内任何内容。

**未运行（NOT RUN）：** 尚无 Ubuntu 24.04 解压、`--preflight` 运行、`setup.sh` 安装、apt/pip/torch 安装、Rust 或 maturin 构建、Wesnoth 1.18.8 构建、`train.sh` 启动；撰写文档时也尚未从本树构建真实归档包。这些仍作为 [TEST_zh.md](TEST_zh.md) 中的 `PKG1`，执行后记录在 `verification/training_bundle_ubuntu24_<date>/REPORT.md`。本文任何内容都不构成已通过的运行时验收。

## 7. 排障

**`preflight: SHA256SUMS verification failed`** —— 解压副本与归档包不一致。重新解压到新目录并重跑 `./setup.sh --preflight`；不要手工改哈希。`preflight: BUNDLE_MANIFEST.json is present but SHA256SUMS is missing` 表示解压不完整。

**`setup.sh: Ubuntu is required` / `Ubuntu 22.04/24.04 is required` / `Ubuntu x86_64 is required`** —— 系统门禁在改动前读取 `/etc/os-release` 与 `uname -m`。请使用 Ubuntu 24.04 `x86_64`；22.04 可运行但会提示 24.04 才是目标平台。

**`setup.sh: sudo is required for system packages`** —— 以 root 重跑、安装 `sudo`，或自行安装系统包后传 `--skip-system-deps`。

**Rust 或扩展问题** —— 没有内嵌 wheel 时，`setup.sh` 仅在 `cargo` 缺失时安装 rustup；随后 `engine_lite/` 下的 `maturin develop --release` 必须成功。`identity: engine build … does not match declared …` 表示扩展过期：重跑 setup 以按当前源码重建扩展。

**wheel 未被识别** —— 文件须位于 `dist/`，名称须同时含 `manylinux` 与 `x86_64`；`setup.sh` 按 `wesnoth_learning_lite-`、`_engine_lite-`、`engine_lite-` 三个前缀查找，`--preflight` 会打印它找到的 wheel。面向免 Rust 安装的发布若未内嵌 wheel，`--require-wheel` 会使其失败。

**`setup.sh: Wesnoth version mismatch, 1.18.8 is required`** —— setup 最终确定的二进制未报告 `1.18.8`。若 `--wesnoth`/`WESNOTH_EXE` 指向的不是 1.18.8，setup 会忽略它并改用固定压缩包，因此该消息意味着复用的安装或新构建本身有问题：查看 `.cache/setup.log`，并用真正的 1.18.8 二进制传 `--wesnoth /path/to/wesnoth`。

**`train.sh: .runtime/environment.sh is missing; run ./setup.sh first`**（以及 venv、`_engine_lite`、`WESNOTH_EXE` 的同类拒绝）—— 环境不完整；在同一目录执行 `./setup.sh`。`experiment directory already exists` 表示时间戳或显式指定的运行目录已被占用；用 `--run-dir` 指定新名称。

## 相关文档

- [architecture_zh.md](architecture_zh.md)：结构、参数、已实现与未实现范围。
- [TEST_zh.md](TEST_zh.md)：`PKG1` 验收项及剩余最小方案。
- [THIRD_PARTY_zh.md](THIRD_PARTY_zh.md)：内嵌第三方组件的许可。
- [instructions_zh.md](instructions_zh.md)：服务器接手、启动/恢复、维护与调参。
