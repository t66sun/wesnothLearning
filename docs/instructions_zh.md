# Agent 训练操作指南

> 语言：[English](instructions.md) | 中文

运行契约和当前参数见[架构文档](architecture_zh.md)。待验收事项见[验收清单](TEST_zh.md)。

**当前路线：**每个 manifest 冻结唯一的自定义教师包 `gpt6astra` 及其血脉，因此教师对局、DAgger 纠正与导出一致携带同一身份。lite 是默认引擎，也是默认评估引擎；新 run 采集 lite Astra 教师对局（`native_bc_games` 为 0），最终对照同样为 lite Astra，官方 baseline 席位仍仅走 native。能力与限制见 architecture.md §4–§5。

当前 lite 战斗/教师 profile 为 `probabilistic_combat_v6`，RNG 为 `splitmix64-rejection-v1`。构建匹配扩展后才能使用。旧 expected_damage_v1/v2、probabilistic_combat_v1/v2/v3/v4/v5 运行须使用原源码/构建；不得重写冻结数据、快照或检查点身份。旧权重须走既有显式初始化/重置优化器流程，并重新验收。

当前编译规则包可按 `verification/weapon_filters_20261103/REPORT.md` 中的步骤从既有不可变捕获生成；使用新输出目录并保留旧包。
## 1. 接手时先确定任务

先读根目录 `AGENTS.md`，再按任务阅读本文对应章节：

| 用户指令 | 进入步骤 | 完成标准 |
| --- | --- | --- |
| 启动新训练 | 第 2–4 节 | 配置与授权一致，训练进程存活，至少一个有效采集批次和检查点产生；只创建 manifest 不算启动成功 |
| 继续/恢复训练 | 第 2、5 节 | 恢复原实验的配置、权重、优化器、随机状态和原截止时间，确认继续产生进度 |
| 看进度、维护、排障 | 第 6–7 节 | 给出当前阶段、有效采样/更新进度、故障依据及必要处置；保持原配置 |
| 按指令微调参数 | 第 8 节 | 只变更指定赛制/字段，核对实际生效值和版本，记录前后对比 |

已有明确授权就完成相应操作，无需逐步重复询问。阅读本指南、整理文档或查看状态本身不授权启动训练。维护任务不自动包含修改奖励、降低门槛、扩大采样或更换模型。默认 adaptive 控制器在既定范围内的自动调整继续按原实验执行。

## 2. 环境与工作目录

主要环境是 Ubuntu CPU 服务器。通常从本机连接：

```bash
ssh cpuServer
```

凭据通过现有 SSH 配置或用户提供的认证方式使用，密码不写进文档、命令、日志或脚本。别名在执行环境中不可见时，已知入口为 `tongshu@192.168.122.118`。

进入服务器后：

```bash
project=/home/tongshu/myDev/wesnothLearning/WesnothLearning
python=/home/tongshu/venv/bin/python
wesnoth="$project/.runtime/install/bin/wesnoth"
cd "$project" || exit 1
export PYTHONPATH="$project"
export PATH="/home/tongshu/.cargo/bin:$PATH"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
```

恢复旧实验时使用其冻结源码和匹配环境。`run.sh` 调用 `.venv/bin/python`。使用前确认该解释器与实验环境一致。

快速自检只验证环境和身份，不开游戏：

```bash
"$python" -m learning run --help
"$wesnoth" --version
"$python" -c 'import sys, torch, _engine_lite; print(sys.executable); print("torch", torch.__version__); print("CUDA", torch.cuda.is_available()); print("lite", _engine_lite.__file__)'
```

原版应为 1.18.8，项目冻结入口要求 PyTorch 2.9.1。CPU 服务器默认全局 8 个游戏 worker、每训练器 1 线程，三个训练器共享这 8 个 worker。Windows 只作参考，不安排 Windows 全量验收。CPU 服务器没有 `git` 也没有 `gh`，且 `sudo -n` 需要密码，因此改动以 `git archive` 压缩包送达并解压到新的按日期命名的目录，验收在该解压副本上进行，而不在长期保留的检出目录上。

新源码归档不包含已编译的运行依赖。同种子原版比较前，在解压目录编译已有随机流库并记录哈希。缺少它时，`match._child_env` 省略预加载，仅传入 `--rng-seed` 不能固定逐动作随机流。

```sh
mkdir -p .runtime
cc -O2 -fPIC -shared -o .runtime/entropy.so vendor/arena/entropy.c -ldl
sha256sum .runtime/entropy.so
```

在匹配的虚拟环境中重新构建 `_engine_lite`。Rust 通过 `include_str!` 嵌入 `engine_lite/lua/host.lua`，修改这个 Lua 文件也需要重建扩展。

### 干净 Ubuntu 24.04 训练归档包

`python -m learning bundle --output PATH` 生成、`python -m learning verify-bundle PATH` 校验的归档包，是干净 Ubuntu 24.04 `x86_64` 机器接收本项目的方式。它是上文服务器环境的替代方案而非替代品，现有服务器目录及其说明保持不变。

归档包含源码树、冻结的 `1.18.8-combat-filtered` 规则、精选人类对局、数据集输入，以及 `data/opponents/` 下的对手包（即冻结的 `gpt6astra.zip`，由 `BUNDLE_MANIFEST.json` 的 `data.opponents` 列出，校验器要求至少一个）。它排除 `.git`、虚拟环境、缓存、`.runtime/`、`runs/`、`verification/`、`delivery/`、`tmp/`、`data/rules/1.18.8`、`data/humanData`、`data/references`、编译产物后缀、Cargo `target/` 与 `AGENTS.md`，因此不记录任何运行、棋力结果或交付决定。`docs/instructions.md` 及其镜像为必需成员：缺少它们时构建器拒绝产出归档。

```bash
python -m learning bundle --output dist/WesnothLearning-training.tar.gz \
    --created-at 2026-10-25T00:00:00Z \
    --wheel dist/wesnoth_learning_lite-0.2.0-cp312-cp312-manylinux_2_34_x86_64.whl
python -m learning verify-bundle dist/WesnothLearning-training.tar.gz --require-wheel
```

`--output` 必须位于项目根目录内且尚不存在；构建器先写临时文件再改名，失败不会留下半个归档。`--created-at` 归一化为 UTC `YYYY-MM-DDTHH:MM:SSZ`，固定后重复构建字节一致。`--wheel` 只接受以 `.whl` 结尾且名称同时含 `manylinux` 与 `x86_64` 的文件；`verify-bundle --require-wheel` 会判定无 wheel 的归档不合格，离线免 Rust 安装需要它。两个命令都输出 JSON（`archive`、`sha256`、`files`、`bytes`、`created_at`、`source`、`rules`、`wheel`；随后 `ok`、`errors`，不合格时退出 2），归档 `sha256` 记入发布说明。`rules.json` 与 `catalog-summary.json` 在 `rules_file_sha256`、`source_hash`、`unit_count`、`terrain_count` 上不一致时，构建器拒绝打包。

归档是根为 `WesnothLearning/` 的单个排序 PAX gzip，`mtime` 与 gzip 头时间均为 0，`uid`/`gid` 为 0，`uname`/`gname` 为空，模式 `0644`（`*.sh` 与目录为 `0755`），根下含 `BUNDLE_MANIFEST.json`（schema 1）与 `SHA256SUMS`，解压后 `cd WesnothLearning && sha256sum --check SHA256SUMS` 可用。校验器重算每个成员的大小、哈希、模式与总计，检查 Ubuntu 24.04 `x86_64` 目标、无绝对路径/越界父路径/重复成员、排除类别、对归档内 JSON 的规则身份、`data.opponents` 列表（至少一个包、均位于 `data/opponents/` 下且逐个核验哈希）、精选人类文件与可选 wheel。

```bash
tar -xzf WesnothLearning-training.tar.gz && cd WesnothLearning
./setup.sh --preflight          # 只校验校验和：不做系统门禁、不下载、不写入
./setup.sh --device cpu         # apt 包、venv、torch 2.9.1、_engine_lite、Wesnoth 1.18.8
./train.sh --help               # 打印选项；不创建任何内容
```

目标为具备 `sudo` 或 root 及网络访问的 Ubuntu 24.04 `x86_64`；22.04 可运行但会提示 24.04 才是目标，其他发行版在改动系统前即退出 2。`--device auto`（默认）仅在 `nvidia-smi` 可用时选择 `cu128`，纯 CPU 机器应显式写 `--device cpu`；`--wesnoth PATH` 复用报告 1.18.8 的二进制，`--skip-system-deps` 要求系统包已装好，`--jobs N` 决定 Cargo 与 Wesnoth 构建并行度，`WESNOTH_EXE`/`BUILD_JOBS` 提供同样的值。安装会以 `pip --force-reinstall --no-deps` 安装 `dist/` 中的 wheel，此时绝不安装 Rust；否则仅在 `cargo` 缺失时安装 rustup，并在 `engine_lite/` 运行 `maturin develop --release`。随后校验 `rules.json` 与 `catalog-summary.json`、`source_version` 1.18.8，以及扩展的 `ENGINE_VERSION`/`RNG_VERSION`/`COMBAT_VERSION` 与 `learning.adapters` 是否一致，复用或构建固定版本 Wesnoth（SHA-256 `fce3bd71d4ed32c9d11c0f707d19743cec6adf5c34761fab94ab72754aaedd89`），写入 `.runtime/environment.sh`，并通过 `tee` 记录到 `.cache/setup.log`。venv、torch、requirements 与 Wesnoth 可幂等复用；扩展每次运行都会重装或重建。安装不启动采样、对局或训练，归档包的存在也不等于授权开工。

故障：`preflight: SHA256SUMS verification failed` 表示解压副本与归档不一致——重新解压到干净目录，不要手工修补哈希；缺少 `SHA256SUMS` 表示解压不完整。系统门禁或 sudo 拒绝，用 Ubuntu 24.04 `x86_64` 加 root/`sudo` 解决，或自行装好系统包后加 `--skip-system-deps`。`identity: engine build … does not match declared …` 表示扩展过期：重跑安装。wheel 未被选中通常有两种原因：`setup.sh` 只在 `dist/` 中查找以 `wesnoth_learning_lite-`、`_engine_lite-`、`engine_lite-` 开头的文件（`--preflight` 会打印找到的文件），而构建器还要求文件名同时含 `manylinux` 与 `x86_64`。缺少 `.runtime/environment.sh`、`.venv/bin/python`、可导入的 `_engine_lite`、可执行的 `WESNOTH_EXE` 或运行目录已存在时，`train.sh` 拒绝启动。用户授权后按第 4 节启动运行。

参考工作站已验证归档结构和脚本。干净 Ubuntu 24.04 上的解压、安装和启动尚未验收。[归档包核验记录](../verification/acceptance_20261030/REPORT.md)

## 3. 启动前核对实际可运行范围

新实验默认 lite，规则默认 `data/rules/1.18.8-combat-filtered`（587 单位、438 地形）。启动门禁核验实际六阵营的 158 单位闭包，接受已记录近似，拒绝未支持类型及缺失引用；整包语义/性能标志仍保留原值。新 manifest 冻结唯一的自定义教师包（`gpt6astra`）及其血脉；评估引擎跟随采样引擎，除非用 `--evaluation-engine` 覆盖。能力与限制见 architecture.md §4–§5。

通常使用默认目录即可。采集输入已于 2026-10-24 迁入 `data/`；早于该迁移的检出仍把 `rules/`、`datasets/`、`humanData*`、`opponents/`、`references/` 放在根目录，须先移入 `data/`，否则默认路径无法解析。需要用户指定其他冻结包时，传入：

```bash
rules_dir="$project/data/rules/1.18.8-combat-filtered"
# 新训练命令增加 --rules-dir "$rules_dir"
```

`--rules-dir` 同时绑定特征、job、adapter 和 manifest，优先于环境变量；没有显式参数时也可使用 `WESNOTH_RULES_DIR`。程序 API 传入 `config.rules_dir`。恢复自动使用原 manifest 的目录，不能直接套用最新包。

默认包 `1.18.8-combat-filtered` 的规则身份为 `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`；10 张正式地图已冻结在 `data/rules/1.18.8/maps`。捕获新包时使用 `python -m engine_lite.capture --maps-dir data/rules/1.18.8/maps` 并补齐其他必需参数，保留地图复合地形。切换规则哈希/词表后建立新实验，历史权重仍用原匹配 schema。

核对通过标准：规则哈希与 `features.schema()` 一致，六阵营闭包无缺失/未支持声明，地图和 Astra 存在，选择的赛制确有教师链；已有验证有效时复用证据，只有接入代码变动才做一次受影响的最小核验。严格统计精度、外围战役和包体限制的处理边界见架构文档，不能因此重新扩张成全量测试任务。

### 归档回放供给

托管回放按月供给到 `data/replays/<YYYYMM>/<DD>/`，一天一个目录；连续月份重复 `--month`，除非用户指定其他目录否则用默认输出：

```bash
python -m learning.replay_fetch --month 2026-07 --month 2026-08 --month 2026-09
python -m learning.replay_fetch --month 2026-07 --out data/replays/202607 --verify
```

月份列表读不到、某天列表失败或某次传输始终不成功都按失败上报，命令以非零码退出；没有证据的内容不算已供给。重跑成本低且不打折扣：磁盘上已有的文件只有在能完整解压出 bz2 流时才保留，被中断的传输会被重新下载而不是被信任。`--verify` 重新读取归档列表、逐日比对文件名单并解压每个本地文件。该工具只供给采集输入：不解析回放内容，也不授权采集或训练。

### 引擎基准

成对的 native/lite 工作负载由 `benchmarks/contract.json` 固定；`learning.benchmark.build_manifest` 冻结产物哈希，`learning.benchmark_runner` 在 Linux 上依据 `/proc/*/smaps_rollup` 实测：

```bash
python -m learning.benchmark_runner --executable "$WESNOTH_EXE" \
  --output verification/perf-smoke --formats duel --caches cold \
  --modes equal_work --densities regular --blocks 1 --seats 1 \
  --script-turns 1 --max-decisions 4
```

去掉各项限制并传 `--blocks 30` 得到完整样本；每个输出目录只能写一次，故障永远不会变成成功的 0。`observed.json` 在任意块数下都展示实测比值，`acceptance.json` 则要求 30 个完整块、主机/配额/工作量一致，且 wall 与 CPU 都至少达到 native 的 5 倍；PSS 的 5 倍目标是单独项，绝不以 RSS 代替。等量工作结果只覆盖固定脚本而非战斗，学生推理性能需要单独的小循环测量。

## 4. 新建并启动训练

先确定用户指定的赛制、设备、时长、worker 和实验名。当前默认采集规格见 architecture.md §12；数量是有效教师局目标，采满还要满足 BC 质量/覆盖/场景设计门槛。核对实际生成配置与用户授权一致。

以下是**获准新建 18 小时 CPU 三赛制纯 lite 实验**时的模板；用户指定其他时长或赛制时替换对应项：

```bash
run_dir="runs/v5_$(date +%Y%m%d_%H%M%S)"
test ! -e "$run_dir" || exit 1
mkdir -p runs/logs
set -o pipefail
"$python" -u -m learning run \
  --run-dir "$run_dir" \
  --engine lite --evaluation-engine lite \
  --bc-games 300 600 400 --native-bc-games 0 0 0 \
  --device cpu --workers 8 --trainer-threads 1 \
  --hours 18 --formats duel ffa4 team2v2 \
  --wesnoth "$wesnoth" \
  2>&1 | tee "runs/logs/${run_dir##*/}.log"
```

实验目录必须由程序创建，不要预先 `mkdir "$run_dir"`。日志放在外面的 `runs/logs/`。省略引擎参数即为 lite；需要仅原版时显式传 `--engine native`，原版教师下限默认等于对应赛制总目标。默认不采原版锚点，最终比较也在 lite 内对 Astra；原版棋力评测另行明确执行。`--bc-games` 修改的是三赛制总目标，原版配额由 `native_bc_games` 控制。

获准比较辅助目标时，在新运行命令中加入 `--ppo-aux-target frozen_bc_kl`；`--ppo-aux-target historical_action` 是默认基线。前者在合格 policy/train 复习状态上使用完整合格 BC 端点的冻结动作分布，后者使用历史采样动作。既有 `bc_aux` 系数仍默认 0.1，并逐批冻结。control 排除、候选、采样配额、历史和 PPO 停止规则共用。比较两个目标时不要同时调整系数或奖励。

KL 模式在 PPO 开始前固定 `<format>/frozen_bc.pt`，并将身份写入 `state.json`/完整检查点。移动或恢复运行时须一并保存该文件。同任务的 BC-only 父运行可通过 `--branch-from PARENT` 在两个新目录中分别建立两种模式：复制的起始检查点必须与合格 `last_bc.pt` 一致，分支记录会固定该端点。缺少合格 BC 的强制 PPO 在 KL 模式下报错。旧任务权重只作明确 actor 初始化时，必须先通过新运行 BC 门禁才可成为锚点。模式不能在恢复时改变；`run --resume ... --ppo-aux-target ...` 会报错。禁止用 selected/latest 替换锚点或编辑 manifest 来改变模式。

长任务放到已有持久终端；有 tmux 时可先 `tmux new -s wesnoth-v5`，在其中执行环境和启动命令，使用 Ctrl-b、d 脱离，之后 `tmux attach -t wesnoth-v5` 接回。记录所用会话、主 PID、完整命令、日志和实验目录，确认断开 SSH 不会结束训练。不要依靠一个短时 SSH 工具请求持有整个长实验。

新运行使用 `official-score-30-v1`：教师、PPO 和 DAgger 将完整第 30 回合作为正式计分终局。`--training-max-turns` 仅接受 30；gamma 为 1，探索奖励为 0，经济/控制保留势函数差分。评估同为 30，开局探针在 5 回合外部截断。BC 门禁和面板阈值保持现有合同。旧 60 回合数据与 manifest 不能恢复或混入本任务；`--human-data` 应指向空目录或兼容语料，不能重标历史数据。

启动后的完成检查：

- `manifest.json` 的 `config` 与指令相符，规则/架构/词表及引擎绑定正确。
- `clock.json` 的开始时间和截止时间符合本次预算；默认前 10/12 时长允许更新，最后 2/12 冻结评测。
- 每个启用赛制有 `hardware.json`、`state.json`、`latest.pt`，至少一个有效采集批次继续推进 `jobs.jsonl` 和训练计数。
- 没有 `trainer_error.log` 或持续 `infrastructure_error`；阶段和教师身份符合预期。启动失败就报告失败，不以后台 PID 存在替代进度。

本指南不提供默认重跑 277 项测试、30 块性能矩阵或大样本战斗统计的前置流程。

新实验可用 `--final-holdout-hours H` 在最终评估预算内预留 H 小时（默认 0，`0 <= H < hours/6`）。提名在总截止前 H 小时结束，未完成时保留现任冠军。最终评估沿用原截止时间，恢复时沿用冻结配置。

## 5. 恢复已有训练

先查看原实验的 manifest、clock、最近检查点和错误记录；确认没有同目录的活跃主进程，再在匹配源码、环境和规则下执行：

```bash
run_dir=runs/用户指定的实验目录
test -f "$run_dir/manifest.json" || exit 1
"$python" -u -m learning run --resume "$run_dir"
```

`--resume` 使用 manifest 中冻结的设备、worker、赛制、采样目标和原截止时间。追加 `--hours`、`--workers`、`--bc-games` 等不会变更已有实验；预算已到期时恢复会进入评测/结束，不会自动获得新预算。

确认检查点、优化器、RNG、奖励控制器和未完成批次恢复，计数继续增长。出现 `source changed`、`manifest changed` 或规则/词表不符时，使用原匹配版本排查，保留原 manifest 与校验。需要新配置/新架构时按用户指令建立独立实验或实现明确迁移，不能编辑冻结文件假装是无变化恢复。

`run.lock` 是文件锁，文件存在不等于正在运行；遇到 `already running` 先确认持锁进程，不通过删除锁文件启动第二个同目录实验。

## 6. 日常维护与进度判断

### 分开运行 BC、PPO 和最终评测

要使用兼容父运行的权重和监督语料开始新的 BC 阶段，可运行 `python -m learning run --run-dir CHILD --branch-from PARENT --branch-restart-bc --branch-reset-optimizer --phase bc`，传入与父运行一致的赛制、引擎和训练回合上限。父运行须处在已提交的批次边界。子运行使用自己的种子和预算，从校准开始，以原验证分区评估首次更新的模型。

以旧 BC actor 初始化新有限任务时，使用 `python -m learning run --run-dir CHILD --branch-from PARENT --branch-weights-only --branch-checkpoint last_bc --phase bc --formats duel --human-data EMPTY_OR_COMPATIBLE_DIRECTORY`，保留父运行的引擎和规则，并传入另行授权的预算和种子。仅权重初始化允许父运行赛制的非空子集，普通分支仍要求完整相同赛制集合。省略 `--branch-checkpoint` 则选择 `latest`。程序记录来源路径/哈希，重置价值头和优化器，从空训练状态、全新门禁与校准开始，不继承父语料和 BC 资格。普通 PPO 前需取得新任务的合格 BC 端点；后续同任务分支可复用兼容监督语料。仅在另行指令授权后启动。任务/回合上限变化不构成 warm-start actor 的独立验证集，实验设计需审计其历史地图/场景暴露。

以下入口用于与当前 schema/源码匹配的新实验。旧 schema 4 的已结束实验不能用 schema 5 直接恢复。默认 `run` 仍是 auto 一键流程；只做 BC 时创建实验加 `--phase bc`，BC 达标或阶段预算结束后保存为 `bc_complete`，不自动开始 PPO/最终评测。

```bash
"$python" -m learning run --run-dir runs/new_bc --phase bc --hours 4
"$python" -m learning phase show --run-dir runs/new_bc
# 正常切换要求 BC 门已通过；可用 --formats 仅选择部分赛制。
"$python" -m learning phase ppo --run-dir runs/new_bc --hours 8
# 仅在用户明确指示强转时使用：保留未达标的门结果，记录原因，不改 effective。
"$python" -m learning phase ppo --run-dir runs/new_bc --force --reason '用户明确要求结束 BC' --hours 8
"$python" -m learning run --resume runs/new_bc
"$python" -m learning phase evaluate --run-dir runs/new_bc --hours 2
"$python" -m learning run --resume runs/new_bc
```

上述正常/强制 PPO 命令是二选一示例。命令先写阶段请求：运行中的训练器在当前批次完成后读取；已经停止的实验需随后 resume，不能向仍持锁的实验启动第二个进程。恢复时先完成已有 pending_train 的冻结方法，再开始新阶段采样。PPO 阶段结束保存为 `ppo_complete`，最终评测需显式请求。正式 BC/PPO 的样本、奖励版本和 rehearsal 要求仍生效，强转不保证训练质量，也不凭空生成 BC 数据。

`run --phase bc --hours 4` 给 BC 完整 4 小时，不预留自动最终评测时间。`phase --hours` 明确分配这次请求的阶段截止时间，从请求时刻计时，持久化在检查点；不改原 manifest/clock。省略则沿用原总预算的剩余时间（auto 沿用原更新截止），原预算过期时必须明确给出新阶段时长。普通 `run --resume --hours` 仍不会续预算。最终评测启动后不可在原目录返回训练；需要新实验。阶段命令不会自动启动或恢复训练，也不绕过源码/schema 冻结检查。

若要在截止前停在已提交边界，可为 `phase ppo` 加上 `--ppo-batches N`。每种目标赛制各自提交 N 个新调度且至少执行一步优化器更新的 PPO 批次，完成到期验证后结束阶段。请求生效时已有的待提交批次按原计划完成，不计入本次目标。每次新请求独立计数，阶段截止时间仍可提前结束训练。

对已有实验一次读取足够的状态；首次检查或实际异常才扩大范围。先确认 manifest 存在，再查看控制器，避免对不存在的实验路径创建控制目录。

```bash
test -f "$run_dir/manifest.json" || exit 1
"$python" -m learning control show --run-dir "$run_dir"
```

| 文件 | 读取内容与判断 |
| --- | --- |
| `phase/*.pending.json`、state.phase_history | 阶段请求、原因、独立截止时间、是否显式强转与应用记录；命令排队不等于已切换 |
| `manifest.json`、`clock.json` | 实际配置、源码/对手/词表身份、更新和最终截止时间 |
| `<format>/state.json` | stage、batch、version、effective、counters、pending_train/pending_validation、error；只取需要的字段，history 可能很大 |
| `<format>/jobs.jsonl` | 最近任务的 status、faults、training_eligible、教师覆盖、引擎和阶段；统计有效局而非单看文件行数 |
| `<format>/bc_gate.json` | 语料数量、模仿质量、候选覆盖、场景设计分别是否通过；开局探针记录为 `blocking: false` |
| `<format>/validation/*.json` | 区分 trend/promotion、native/lite 和队友上下文；一次小面板胜利不等于最终棋力 |
| `<format>/latest.pt`、`last_bc.pt`、`last_ppo.pt` | 检查点是否更新、是否匹配状态与当前阶段；best/selected 是选模结果，不能当 latest 恢复状态的替身 |
| `control/*.json`、`control/events.jsonl` | 当前配置、pending 命令、已应用序号、reward_version、last_error、metrics_error（非空时 adaptive 冻结） |
| 主日志、`scheduler.jsonl`、`trainer_error.log` | 是否仍有任务完成、哪个赛制/阶段故障、实际异常栈 |

BC 局数不增长不一定挂住：配额已满而质量未过时会继续学习已有数据，平台期才追加采样。采集阶段短时不更新权重也可能正常。结合最新任务完成时间、待处理批次、optimizer_steps 和检查点时间判断；CPU 利用率高本身不能证明更快或异常，先看有效局/小时、CPU 核秒/局、内存与超时。

只维护本任务拥有的进程和文件。常规维护可以在已有授权内恢复相同配置、保留故障证据；不因看见利用率低就改 worker、奖励或门槛。需要稍后持续看护时使用用户授权的任务调度能力，不在一次检查中无限轮询。

### BC、selected 与 latest 的匹配进步对照

最终留出报告只评测 selected。检查点身份表同时列出 BC 终点、最新完整检查点和未完成更新；中断的更新不计入 latest-complete。

单独获准进行进步评测后，使用已有的终结运行，其内需有 `last_bc.pt`、冻结的 `selected.pt`/`selection.json` 和最新完整检查点。源运行保持只读。以下规划命令不启动对局：

```bash
"$python" -m learning.progress plan --directory "$run_dir/duel" --format duel \
  --output verification/progress_NEW --blocks 12 --seed 20261106 --hours 1
# 显式执行评测对局，不训练，也不生成训练语料分片。
"$python" -m learning.progress run --plan verification/progress_NEW/plan.json --workers 8
```

示例预算为 72 局单挑：BC、selected 和 latest 各 12 个完整 block。FFA 需要 144 局，团队需要 288 局并包含两种队友上下文。截止时间从规划时开始计算；使用获准的时间预算，过期后建立新计划。执行前校验冻结导出、对手、规则、评测源码和赛程。操作创建新输出目录，不改写源运行的清单、检查点或选择结果。

`report/summary.json` 和 `report/REPORT.md` 给出相对 BC 的匹配归一化自身积分变化。缺局、故障和物理场景不足不能证明进步；完整但区间跨零仍为 inconclusive。这是验证集诊断，与独立最终留出评测分开。只重算已有结果、不启动游戏时使用新的报告目录：

```bash
"$python" -m learning.progress report --plan verification/progress_NEW/plan.json \
  --results verification/progress_NEW/execution/results.json --output verification/progress_REPORT_NEW
```

## 7. 停止与故障处理

用户要求停止时，先记录最近可恢复检查点、未完成批次和目标主进程，在所属持久终端发送 Ctrl-C；确认协调器、训练器及本实验游戏子进程退出。当前协调器收到 KeyboardInterrupt 会 terminate 训练器，**没有保证“保存当前每一步后再退出”的优雅暂停命令**，所以只能保证此前已落盘的进度，停止后核对检查点是否可加载。

需要发送信号时，先按 PID、父子关系、命令和实验目录确认归属，逐个处理本实验进程。不要使用按 `python` 或 `wesnoth` 名称全局清理的命令；也不要删除数据、检查点或锁文件来“解卡”。

| 现象 | 最小处理 |
| --- | --- |
| 规则目录/词表不一致 | 对照环境变量、job.rules_dir、schema 与规则哈希，修正实际接入，不修改哈希绕过 |
| lite 四人教师失败 | 对照 `four.lua` 依赖与教师身份；自对弈不能冒充教师采集通过 |
| `infrastructure_error` 或教师查询失败 | 先读该任务错误与教师返回原因，区分采样故障和允许跳过的纠偏标签 |
| 无新进度 | 区分采集、BC 已满后继续训练、验证/最终评测、截止时间、活跃 worker 和错误；用一个具体失败定位 |
| OOM/超时 | 记录当时并发、内存与失败任务；按用户授权修改下一实验配置，已有 run 不靠 resume 参数假改 |
| 参数量/真实规则 smoke 失败 | 核对当前词表和规则哈希；容量按词表计算，测试应使用当前特征目录 |

修复后只重跑受影响的失败/新增最小用例，已通过项按有效证据复用。新输出放到新的 `verification/<日期或任务>/`，保留初次失败和修复后结果。普通维护不修改已安装游戏 AI、历史 V4 权重或其他实验。

恢复已归档的实验时，先从对应归档的 `index.json` 找到原路径，再按 `SHA256SUMS` 校验文件。按归档 README 中的相对路径恢复，避开已有同名实验。恢复后使用原实验的 schema、冻结源码和预算。[归档位置与恢复说明](../verification/training_archive_20261023/REPORT.md)

## 8. 得到指示后微调参数

先把指令落实为：实验目录、赛制、字段、目标值、原因与观察区间。使用用户给定的值；若只要求研究或评估，先报告依据，不执行调参。获准修改后只改指定项，保留其他配置，不用提高 shaping 分数或降低 BC 门槛冒充棋力进步。

### 8.1 可在批次边界热更新

| 字段 | CLI | 允许范围 |
| --- | --- | --- |
| economy | `--reward-economy` | 0.05–0.20 |
| control | `--reward-control` | 0.02–0.15 |
| explore | `--reward-explore` | `official-score-30-v1` 固定为 0 |
| 模式 | `--reward-mode` | fixed / scheduled / adaptive |
| 熵系数 | `--entropy` | 非负有限数 |
| BC 辅助系数 | `--bc-aux` | 非负有限数 |

使用现有控制队列，不能直接写 state/checkpoint/config。以下变量必须先由用户指令赋值；例子只修改指定赛制的经济势函数系数：

```bash
: "${run_dir:?指定现有实验}"
: "${target_format:?指定 duel/ffa4/team2v2}"
: "${target_economy:?填写用户指定的经济系数}"
: "${change_reason:?记录本次用户指令与变更原因}"
test -f "$run_dir/manifest.json" || exit 1
"$python" -m learning control show --run-dir "$run_dir"
"$python" -m learning control set \
  --run-dir "$run_dir" --format "$target_format" \
  --reward-economy "$target_economy" --reason "$change_reason"
```

返回命令 ID 只表示已入队；等对应赛制完成当前批次，再核对 `control show` 的 pending、实际配置与应用序号，核对 events 中旧/新值、原因和递增的 reward_version。当前已开始的对局仍使用旧冻结配置，后续批次才使用新版本。相同 PPO 更新不能混用奖励版本。

需要暂停自动调参时，只有在用户要求下才把对应赛制的 mode 改为 fixed；手动改一个系数不会自动禁用 adaptive。回退同样排队提交旧值并写原因，不删除或改写事件链。

### 8.2 不支持已有 run 直接热改的参数

worker、设备、赛制、总预算、BC 局数/原版锚点数、模型结构/词表、序列窗口、epochs、学习率、PPO clip 和 `ppo_aux_target` 不是当前 control API 的热更新字段。按用户指令调整新实验配置或实现兼容迁移，并更新架构文档；不能把它们塞入 `control set`，也不能以 resume 附加参数声称已经生效。

特别注意：`learning_rate` 当前用于初始 BC 优化器，进入 PPO 的更新代码会设置 1e-4。若用户要求改变 PPO 学习率，需要修改实际负责该阶段的代码并做最小核验，不能只改初始配置。采样配额同理：`bc_games` 是总有效教师局，`native_bc_games` 是原版目标，`bc_records` 是每次读取的决策上限，三者不能混淆。

每次变更核对实际生效配置后，记录旧值→新值、用户依据、命令/事件 ID、实际生效批次/版本、后续观察与回退方式。默认比较有效采样吞吐、故障率、BC 分项指标和同引擎/同赛制的验证结果，正式强度仍依据原版评测。

## 9. 独立原生教师实验

此入口不采集训练数据，也不替换当前教师，仅用于明确授权的教师实验。先提交分支，再用 `python -m learning.teacher_remote --command 'COMMAND'` 归档该提交、上传并在新 Ubuntu 目录中复用现有环境执行命令。核对返回的 `SOURCE` 和 `TREE`，保留旧证据目录。

在该归档源码目录中使用 `/home/tongshu/venv/bin/python -m learning.teacher_lab --directory ABSOLUTE_NEW_DIRECTORY` 及以下子命令：

1. `init --source-commit COMMIT --wesnoth EXECUTABLE` 冻结维护版 Astra 源码/包和运行环境身份。使用八个 worker 前检查可用 CPU 与内存。
2. `register --name VERSION --source-commit COMMIT --description DESCRIPTION [--source TEACHER_DIRECTORY] [--parameters JSON]` 创建不可变候选。通过 `--source` 登记新源码归档，比赛仍从原 `evaluator_root` 执行。
3. `panel --name UNIQUE_PANEL --candidate VERSION --preflight` 检查三个赛制 30/100 回合的完整流程。准备期可以修复正确性，不能反复按成绩调参。
4. `start` 一次性记录五小时探索和赛后截止时间。后续 `panel` 仅使用训练地图，先跑一个 block，再以 `--blocks 2 --offset 1` 补两个。六组暂时战胜基线后才可使用 `--opponent VERSION` 进行版本联赛。`status` 报告完整证据和未完成面板。
5. 五小时后执行 `select`，依据实测吞吐冻结验证与留出设计，每赛制比较最多三个候选，冻结组合包后在既有四小时截止前核验留出集。结果写入 `final.json` 和 `REPORT.md`；未获资格的回退选择不能通过最终验收。

正确性审计判定冻结候选不合格时，保留候选及其对局。在探索截止前新建不可变的 `selection_source.json`，记录经审查选拔器的 `evaluator_root`、`source_commit`，原 `base_source_commit`、`baseline_sha256`、不变的 `exploration_end`、`frozen` 时间戳，以及候选名到 `reason`、`evidence` 的 `exclusions` 映射。只有 `select` 从该审查归档执行。选拔器核对身份，在提名及回退中均排除这些版本，并在输出中记录此发布；原 manifest、时钟、计分和验收门槛保持冻结。

`python -m learning.teacher_lab.batch --directory EXPERIMENT --name PANEL --candidates A B --blocks 2 --offset 1` 将多个冻结候选放入共用的八 worker 训练面板，对 Astra 使用相同场景和原评分。已有实验的评测器较旧时，将 `PYTHONPATH` 指向原评测器根目录，以绝对路径执行审查归档中的 `learning/teacher_lab/batch.py`；脚本导入冻结的对局/计分模块，并记录自身源码哈希。必须等上一 worker 池结束后启动。

加上 `--opponent VERSION` 可共用 worker 进行版本联赛。必须已有正确性合格的候选在六组、至少三个物理场景上取得暂时基线胜出；被排除的候选不能解锁联赛。挑战者必须不同于指定的冻结对手。仍使用原时钟、座位轮换、计分和对手记录中的动作预算。

变更或重启命令不会延长时钟。保留失败版本和未完成对局，不根据留出结果调参，不降低 0.10/95%/12 场景门槛，也不在此流程中接入训练。

## 10. 汇报与交接

获准导出交付包后，可用 `export --audit-data DIR --audit-workers N` 让所有赛制共用最多 N 个审计进程，默认一个。各赛制子目录中的全部 `*.jsonl.gz` 分片都会参与校验，同一序列分散在多个文件时会合并处理。

汇报保持简短，至少包含：

```text
实验/源码目录、持久会话或主 PID、日志位置：
赛制/引擎/设备/全局 worker、规则与架构身份：
各赛制阶段、有效教师局/目标、optimizer_steps、最近检查点：
已完成动作与实际验证结果：
调参（如有）：用户依据、旧→新、事件 ID、生效批次/版本：
当前故障或限制、下一步可执行动作：
```

架构/参数/实现状态变更及验收证据链接写入 [architecture_zh.md](architecture_zh.md)，[TEST_zh.md](TEST_zh.md) 只保留已实现但未验收的事项及最小方案。实际命令、结果、源码/规则身份和日志留在带日期的 `verification/` 报告或对应 run；通过后按根目录 AGENTS.md 的维护准则从待验收清单删除整项。本指南只在操作入口或维护流程变化时更新；不另起平行计划或把历史报告覆盖为新结论。最终导出与安装按用户指令单独执行，训练结束不自动替换已安装 AI。
