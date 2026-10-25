# Agent 训练操作指南

> 语言：[English](instructions.md) | 中文

更新日期：2026-10-23。面向接手启动、维护和按指令调参的 agent。架构与当前参数以 [architecture_zh.md](architecture_zh.md) 为准，已实现但未验收的事项及最小方案见 [TEST_zh.md](TEST_zh.md)，历史验收证据从架构文档链接查阅。本文件提供操作步骤，不重复维护架构状态和完整超参数表。

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

这是近期修改所在的主项目；`releases/v5_completion_20261020` 是历史隔离工作目录。恢复旧实验时应使用其匹配的源码，不因路径相似就把两个目录混用。当前服务器使用上面的绝对 Python 路径；仓库 `run.sh` 使用 `.venv/bin/python`，只有确认该虚拟环境有效时才用包装脚本。已有环境不需要重新执行 setup。

快速自检只验证环境和身份，不开游戏：

```bash
"$python" -m learning run --help
"$wesnoth" --version
"$python" -c 'import sys, torch, _engine_lite; print(sys.executable); print("torch", torch.__version__); print("CUDA", torch.cuda.is_available()); print("lite", _engine_lite.__file__)'
```

原版应为 1.18.8，项目冻结入口要求 PyTorch 2.9.1。CPU 服务器默认全局 8 个游戏 worker、每训练器 1 线程，三个训练器共享这 8 个 worker。Windows 只作参考，不安排 Windows 全量验收。

2026-10-22 的按座位候选优化新增了 Rust 扩展的决策参数；使用新源码前需在对应虚拟环境重新编译 `_engine_lite`，不能只复制 Python/Lua 文件。该修改及 300/600/400、8 workers 默认值已于 2026-10-22 在 Ubuntu 通过 T1–T4 受限验收（含 8 worker 真实链路、峰值 PSS 4.02 GiB），结论与证据见 architecture.md 第 8 节和 `verification/pretrain_acceptance_20261022/`；启动正式训练仍需用户后续明确指令。

2026-10-23 当前实现为 schema 5 / 候选 v3。Ubuntu 隔离目录 `/home/tongshu/myDev/wesnothLearning/validation_training_repair_20261023_194022` 已完成阶段接入与恢复的最小验收，使用其 `.venv/bin/python`（共享已安装依赖，拥有自己的新编译扩展）。若主目录尚未同步修复，使用该隔离目录核验入口或先部署已验收源码并重编对应环境；部署记录见修复报告。Rust 用 `include_str!` 嵌入 `engine_lite/lua/host.lua`，只复制 Lua 不会更新已安装扩展。原 20 小时正式实验已失败结束，旧 schema 4/v2 检查点只能使用原匹配源码；新旧语料/检查点不混用。受限移动质量验收已归档至 [后续报告](../verification/bc_rootcause_20261023_2318/REPORT.md)；正式 BC 全部门仍照常执行。

## 3. 启动前核对实际可运行范围

新实验默认 lite，规则默认 `data/rules/1.18.8-training`（587 单位、438 地形）。启动门禁核验实际六阵营的 158 单位闭包，接受已记录近似，拒绝未支持类型及缺失引用；整包语义/性能标志仍保留原值。三赛制使用冻结的真实 Astra 教师，已有验收范围与证据见 architecture.md 第 8 节。

通常使用默认目录即可。采集输入已于 2026-10-24 迁入 `data/`；早于该迁移的检出仍把 `rules/`、`datasets/`、`humanData*`、`opponents/`、`references/` 放在根目录，须先移入 `data/`，否则默认路径无法解析。需要用户指定其他冻结包时，传入：

```bash
rules_dir="$project/data/rules/1.18.8-training"
# 新训练命令增加 --rules-dir "$rules_dir"
```

`--rules-dir` 同时绑定特征、job、adapter 和 manifest，优先于环境变量；没有显式参数时也可使用 `WESNOTH_RULES_DIR`。程序 API 传入 `config.rules_dir`。恢复自动使用原 manifest 的目录，不能直接套用最新包。

默认规则身份为 `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`；10 张正式地图已冻结在 `data/rules/1.18.8/maps`。捕获新包时使用 `python -m engine_lite.capture --maps-dir data/rules/1.18.8/maps` 并补齐其他必需参数，保留地图复合地形。切换规则哈希/词表后建立新实验，历史权重仍用原匹配 schema。

核对通过标准：规则哈希与 `features.schema()` 一致，六阵营闭包无缺失/未支持声明，地图和 Astra 存在，选择的赛制确有教师链；已有验证有效时复用证据，只有接入代码变动才做一次受影响的最小核验。严格统计精度、外围战役和包体限制的处理边界见架构文档，不能因此重新扩张成全量测试任务。

## 4. 新建并启动训练

先确定用户指定的赛制、设备、时长、worker 和实验名。当前默认采集规格见 architecture.md 第 5.1 节；数量是有效教师局目标，采满还要满足 BC 质量/覆盖/开局门槛。核对实际生成配置与用户授权一致。

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

长任务放到已有持久终端；有 tmux 时可先 `tmux new -s wesnoth-v5`，在其中执行环境和启动命令，使用 Ctrl-b、d 脱离，之后 `tmux attach -t wesnoth-v5` 接回。记录所用会话、主 PID、完整命令、日志和实验目录，确认断开 SSH 不会结束训练。不要依靠一个短时 SSH 工具请求持有整个长实验。

启动后的完成检查：

- `manifest.json` 的 `config` 与指令相符，规则/架构/词表及引擎绑定正确。
- `clock.json` 的开始时间和截止时间符合本次预算；默认前 10/12 时长允许更新，最后 2/12 冻结评测。
- 每个启用赛制有 `hardware.json`、`state.json`、`latest.pt`，至少一个有效采集批次继续推进 `jobs.jsonl` 和训练计数。
- 没有 `trainer_error.log`、`errors.log` 或持续 `infrastructure_error`；阶段和教师身份符合预期。启动失败就报告失败，不以后台 PID 存在替代进度。

本指南不提供默认重跑 277 项测试、30 块性能矩阵或大样本战斗统计的前置流程。

新 run 可用 `--final-holdout-hours H` 在既有最终 2/12 预算内冻结 holdout 预留（默认 0；`0 <= H < hours/6`）。仅最终提名提前 H 小时截止，holdout 仍用原总截止。本次获准的新建 30 小时训练取 H=4：25 小时更新、1 小时提名、4 小时 holdout；提名不完整保留冠军，不延长时钟或绕门。恢复沿用原冻结配置。

## 5. 恢复已有训练

**当前状态，2026-10-24：**16:31 续训在 20:05:52 截止 PPO 更新，随后完成每赛制 30 块最终评估，于 **20:42:45** 正常退出，退出码 0。三个 lite Astra 实力对照均为 **not_passed**，现在没有训练运行。最终所选 Duel/FFA4 v100、2v2 v80，最新训练版本为 211/143/80。模型已下载到 `delivery/lite_final_20261024/`，本地安装为 **Arena AI: NeuralArena20261024**，旧附加组件保留。多人游戏启用该模组并选择同名电脑 AI，自动按赛制路由。导出数值与注册检查通过，原版棋力未验收。详见 [安装与实力复盘](../verification/model_strength_20261024_2120/REPORT.md)。下方启动记录是历史信息，未经新指令不要恢复。

**2026-10-24 16:31 历史启动记录：**使用 `/home/tongshu/myDev/wesnothLearning/validation_window_fix_20261024_1630` 下的 `runs/v5_lite_windowfix_20261024_1630`。脱离 SSH 的脚本 PID/PGID 为 202233，初始协调器为 202234；进度读取 `launch.json`、`continuation.log`、各赛制状态和 scheduler 事件。上一轮 `validation_memory_repair_20261024_1321/runs/v5_lite_resume_20261024_1420` 已于 16:21:48 停止，它与 `validation_training_repair_20261023_194022/runs/v5_lite18h_20261024_003512` 都是必需的只读语料、策略和检查点来源，不能删除、移动或恢复。Duel/FF4 从保留的最佳完整 v100 检查点恢复；2v2 没有晋级最佳模型，采用最近合法 v60。三者继续 PPO，滑动窗口修复已部署。**10 月 24 日 20:05:52** 停止 PPO 更新，随后脚本请求最终验收，总截止为 **10 月 25 日 00:00（北京时间）**。不要另开脚本、恢复父实验或覆盖阶段指令；失败时先查证据，不能重跑迁移。选择依据、模型/优化器/RNG 核对及真实进度见 [部署交接](../verification/window_deploy_20261024_1620/REPORT.md)。

`runs/v5_20261021_203930` 因两个训练器 OOM 已于 2026-10-21 21:48 停止，其数据与检查点保留；读取链路修复并验收后，2026-10-22 00:08 的 `runs/v5_20261022_000850` 又于 01:03:45 按用户要求停止。最近纯 lite / 6000×3 / 18 h 实验 `runs/v5_lite6000_replay_20261022_012336` 已按用户要求于 2026-10-22 06:53:44 停止，未进入 PPO；原计划 19:23:37 截止不表示仍在运行。停止状态见 architecture.md 第 1 节，历史问题见其中的归档报告，未获新指令不恢复或新建训练。旧实验源码哈希已变，直接恢复会触发 `verify_frozen`，只在用户明确要求时按受控迁移处理并保留原 manifest 与预算。

先查看原实验的 manifest、clock、最近检查点和错误记录；确认没有同目录的活跃主进程，再在匹配源码、环境和规则下执行：

```bash
run_dir=runs/用户指定的实验目录
test -f "$run_dir/manifest.json" || exit 1
"$python" -u -m learning run --resume "$run_dir"
```

`--resume` 使用 manifest 中冻结的设备、worker、赛制、采样目标和原截止时间。追加 `--hours`、`--workers`、`--bc-games` 等不会变更已有实验；预算已到期时恢复会进入评测/结束，不会自动获得新预算。

确认检查点、优化器、RNG、奖励控制器和未完成批次恢复，计数继续增长。出现 `source changed`、`manifest changed` 或规则/词表不符时，使用原匹配版本排查，保留原 manifest 与校验。需要新配置/新架构时按用户指令建立独立实验或实现明确迁移，不能编辑冻结文件假装是无变化恢复。

`run.lock` 是文件锁，文件存在不等于正在运行；遇到 `already running` 先确认持锁进程，不通过删除锁文件启动第二个同目录实验。

2026-10-24 奖励滑动窗口修复已通过 [隔离 Ubuntu 验收](../verification/reward_window_fix_20261024_1607/REPORT.md)，并经授权迁移部署到现已结束的 16:31 续训。新 manifest 冻结的控制器 SHA-256 为 `2d79571785ab3ebd1b4299653791b78e7a3f85c3cf9338684de855a3c858d1a9`；后续修改仍需新实验或明确受控迁移，不能覆盖冻结源码或清单。

## 6. 日常维护与进度判断

### 分开运行 BC、PPO 和最终评测

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
| `<format>/bc_gate.json` | 语料数量、模仿质量、候选覆盖、开局行为分别是否通过 |
| `<format>/validation/*.json` | 区分 trend/promotion、native/lite 和队友上下文；一次小面板胜利不等于最终棋力 |
| `<format>/latest.pt`、`last_bc.pt`、`last_ppo.pt` | 检查点是否更新、是否匹配状态与当前阶段；best/selected 是选模结果，不能当 latest 恢复状态的替身 |
| `control/*.json`、`control/events.jsonl` | 当前配置、pending 命令、已应用序号、reward_version、last_error、metrics_error（非空时 adaptive 冻结） |
| 主日志、`scheduler.jsonl`、`trainer_error.log`、`errors.log` | 是否仍有任务完成、哪个赛制/阶段故障、实际异常栈 |

BC 局数不增长不一定挂住：配额已满而质量未过时会继续学习已有数据，平台期才追加采样。采集阶段短时不更新权重也可能正常。结合最新任务完成时间、待处理批次、optimizer_steps 和检查点时间判断；CPU 利用率高本身不能证明更快或异常，先看有效局/小时、CPU 核秒/局、内存与超时。

只维护本任务拥有的进程和文件。常规维护可以在已有授权内恢复相同配置、保留故障证据；不因看见利用率低就改 worker、奖励或门槛。需要稍后持续看护时使用用户授权的任务调度能力，不在一次检查中无限轮询。

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

2026-10-23 用户授权的归档清理已完成：服务器 `runs/` 只保留 `v5_lite20h_20261022_210712`、`v5_lite6000_replay_20261022_012336` 两次正式训练及其日志。更早训练、V4 产物和旧回环在 `/home/tongshu/myDev/wesnothLearning/training_archives/20261023_212221/`。历史 run 路径不存在时，先查该目录 `index.json`，按 `SHA256SUMS` 验证所需归档，再依 README 解压回原 project 根目录；归档记录完整相对路径，不向已有同名新实验覆盖恢复。恢复仍使用该实验原 schema、冻结源码和预算，归档不会重置训练资格或时钟。本次是一次性清理，没有安装自动删除任务；详细记录见 [归档报告](../verification/training_archive_20261023/REPORT.md)。

## 8. 得到指示后微调参数

先把指令落实为：实验目录、赛制、字段、目标值、原因与观察区间。使用用户给定的值；若只要求研究或评估，先报告依据，不执行调参。获准修改后只改指定项，保留其他配置，不用提高 shaping 分数或降低 BC 门槛冒充棋力进步。

### 8.1 可在批次边界热更新

| 字段 | CLI | 允许范围 |
| --- | --- | --- |
| economy | `--reward-economy` | 0.05–0.20 |
| control | `--reward-control` | 0.02–0.15 |
| explore | `--reward-explore` | 0–0.15 |
| 模式 | `--reward-mode` | fixed / scheduled / adaptive |
| 熵系数 | `--entropy` | 非负有限数 |
| BC 辅助系数 | `--bc-aux` | 非负有限数 |

使用现有控制队列，不能直接写 state/checkpoint/config。以下变量必须先由用户指令赋值；例子只修改指定赛制的探索系数：

```bash
: "${run_dir:?指定现有实验}"
: "${target_format:?指定 duel/ffa4/team2v2}"
: "${target_explore:?填写用户指定的探索系数}"
: "${change_reason:?记录本次用户指令与变更原因}"
test -f "$run_dir/manifest.json" || exit 1
"$python" -m learning control show --run-dir "$run_dir"
"$python" -m learning control set \
  --run-dir "$run_dir" --format "$target_format" \
  --reward-explore "$target_explore" --reason "$change_reason"
```

返回命令 ID 只表示已入队；等对应赛制完成当前批次，再核对 `control show` 的 pending、实际配置与应用序号，核对 events 中旧/新值、原因和递增的 reward_version。当前已开始的对局仍使用旧冻结配置，后续批次才使用新版本。相同 PPO 更新不能混用奖励版本。

需要暂停自动调参时，只有在用户要求下才把对应赛制的 mode 改为 fixed；手动改一个系数不会自动禁用 adaptive。回退同样排队提交旧值并写原因，不删除或改写事件链。

### 8.2 不支持已有 run 直接热改的参数

worker、设备、赛制、总预算、BC 局数/原版锚点数、模型结构/词表、序列窗口、epochs、学习率和 PPO clip 不是当前 control API 的热更新字段。按用户指令调整新实验配置或实现兼容迁移，并更新架构文档；不能把它们塞入 `control set`，也不能以 resume 附加参数声称已经生效。

特别注意：`learning_rate` 当前用于初始 BC 优化器，进入 PPO 的更新代码会设置 1e-4。若用户要求改变 PPO 学习率，需要修改实际负责该阶段的代码并做最小核验，不能只改初始配置。采样配额同理：`bc_games` 是总有效教师局，`native_bc_games` 是原版目标，`bc_records` 是每次读取的决策上限，三者不能混淆。

每次变更核对实际生效配置后，记录旧值→新值、用户依据、命令/事件 ID、实际生效批次/版本、后续观察与回退方式。默认比较有效采样吞吐、故障率、BC 分项指标和同引擎/同赛制的验证结果，正式强度仍依据原版评测。

## 9. 汇报与交接

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
