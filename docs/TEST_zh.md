# 验收计划

> 语言：[English](TEST.md) | 中文

更新日期：2026-10-30。本文件只保留仍未完成的验收工作。已验收事项整项离开本文件，作为带日期的证据留在 `verification/`；`docs/architecture.md` 描述当前实现，而不是其验收历史。

每个事项说明哪些内容仍未完成、能关闭它的最小 Ubuntu 流程、通过标准与证据路径。状态用词：**PASS**、**FAIL**、**NOT RUN**、**REUSED**（身份匹配的既有证据）。无法运行的检查记为 NOT RUN，永不记为跳过的通过。有界烟测自身声明对棋力不充分；本文件中的任何事项都不授权采集、正式训练或调参。

## 边界与共享输入

- Ubuntu 为验收环境，Windows 仅作参考。在隔离目录或临时 run 中工作。冻结输入、manifest、证据与已安装模型保持只读。
- 只激活所有者发生变更的事项。每处行为变更都需要一条被回退即失败的断言；缺少夹具或运行环境即 NOT RUN。
- 复用已验收证据，不要重复。不因代码搬动就重跑完整阵营/规则/worker/种子矩阵、新语料、长收敛实验或压力测试。
- 派生夹具只准备一次，带父哈希，且不修改历史证据。小链条只证明接线，不证明质量、晋升、收敛或棋力。

## N1 —— 原版终局采集

**状态：** 已实现，NOT RUN；固定场景助手未写。只阻断新的原版终局路径，不阻断 lite。2026-10-30 的巡检无法启动它：参考机没有原版 1.18.8 安装（`.runtime/` 不存在）。

**流程与通过：** 一个固定的原版 1.18.8 早起淘汰/终局场景，上限五回合，外加既有截断反例。真实的初始、被淘汰与终局事件保留存活方与真实自身 HP；只有真实终局才做 bootstrap 吸收。失败或截断不能凭空产生终局。缺失事件即缺失证据，而不是取零的成功。诊断行不得进入行动者/BC/PPO shard，也不得写记忆。原始事件、命令与身份存入 `N1/`；不做原版规则或性能矩阵。

## L1 —— 缩减全链路运行

**状态：** NOT RUN。历史缩减链条只覆盖 duel 的 BC → PPO → 恢复 → final；未中断同未来对比、计划中的运行中打点与全赛制覆盖仍未证实。2026-10-30 未启动任何运行：没有运行时，也没有运行授权。

**流程：** 在隔离源码树上冻结一份 lite 配置，使用能到达 BC 的最小面板、至少两次实际提交的 PPO 更新、一次从已提交批检查点恢复，以及 final 评估入口。启动前记录计数、种子、manifest 与检查点身份。每 30 分钟查看状态/日志并保留异常；运行期间不得提高对局数、降低门禁或修改冻结证据。

**通过：** 运行到达 final 评估；两次 PPO 更新均提交；从保存边界恢复在身份一致处精确复现未中断的未来；选中的检查点与其导出被记录；每个停止原因都被报告而非隐藏。缩减面板的限制保持对棋力不充分，失败仍是失败。

**证据：** 新的带日期 `verification/<run>_<date>/REPORT.md`，含命令、计数、身份、检查点/恢复轨迹、final 入口与资源读数。

## R3 —— 适配后教师棋力证据

**状态：** 适配本身已实现，六个 value 级位置已检查；完整的合法棋盘教师查询/排序与配对棋力比较均 NOT RUN，2026-10-30 的巡检也没有可用的运行时来启动。战术证据与棋力证据分开。

**流程：** 在同一规则下比较冻结的未适配与已适配 Astra，使用配对初始地图、阵营与角色，每种赛制用一个既有完整轮转 block 作有界烟测（预先声明对局数与回合上限）。在角色与调度一致时复用新的同规则对局。截断或块数不足的结果保持不充分。要声明维持或提升棋力，需要未改动的完整 12 block 验证/冠军契约，并运行在冻结的 hold-out 验证调度上，不得在其上调参。

**通过：** 烟测能发现明显的战术或运行时退化，但不声明统计非退化；完整棋力结论需要完整匹配面板且 hold-out 预留未被触碰。否则状态保持未验证，应修正假设而不是一直加种子直到赢。

**证据：** `verification/acceptance_<date>/R3/`，含比较调度、身份、结果，并明确标注战术/烟测/完整面板。

## PKG1 —— Ubuntu 24.04 训练归档

**状态：** Ubuntu 上 **NOT RUN**。2026-10-30 的参考巡检构建了一个归档（308 个文件、244,807,237 字节、sha256 `86a47d43…`），其静态校验通过，翻转一个字节的副本被拒绝；尚无干净的 Ubuntu 24.04 机器解压、安装或启动过。

**流程：** 用 `python -m learning bundle --output tmp/bundle_<date>/WesnothLearning-training.tar.gz --created-at <固定 ISO8601>` 构建一个归档并记录其 sha256；只有在需要随包 Linux wheel 时才传 `--wheel dist/<manylinux x86_64>.whl`，并用 `verify-bundle --require-wheel` 对应校验。按 [instructions.md](instructions_zh.md) 核对成员清单、权限与排除项。复制到干净的 Ubuntu 24.04 x86_64 机器解压，运行 `./setup.sh --preflight`（退出 0，无写入），在一份副本中翻转一个载荷字节并确认 preflight 失败，然后运行 `./setup.sh --device cpu`、`./train.sh --help`（前后对比源码树），以及在没有 `.runtime/environment.sh` 的副本中运行 `./train.sh`，必须拒绝。事后确认不存在 `runs/` 目录或运行日志。

**通过：** 记录的 sha256 与校验读取一致；preflight 接受完好副本并拒绝被篡改副本；归档不含 `.git`、venv、运行状态、验证证据、交付产物、历史 `1.18.8` 规则或原始录像转储；setup 退出 0 并写入 `.runtime/environment.sh` 与 `.cache/setup.log`，其身份检查与 `rules.json`、`catalog-summary.json`、`_engine_lite` 一致；`--help` 不创建任何文件；未 setup 时 `train.sh` 拒绝启动。观察到的失败如实报告，不得缩窄成通过。

**证据：** `verification/training_bundle_ubuntu24_<date>/REPORT.md`，含归档路径/sha256/manifest 身份、每条命令与退出码、两次 preflight 结果、身份检查输出、源码树差异、拒绝输出与 setup 日志。缺少该报告即 NOT RUN。

**阻断：** 只证明安装；不授权采集、启动训练、收敛或棋力结论。

## C1 —— 大厅归档录像整理

**Status:** 已实现；`learning/replay_curate.py` 在本地存档布局之外同时读取大厅归档布局（`[scenario]` 加 `[carryover_sides_start]`，历史拆在两个 `[replay]` 块中）。参考证据仅来自 Windows——2026-10-30 的巡检用四个月度归档逐字节重建了全部 1,076 个载荷——Ubuntu 上仍 **NOT RUN**。它不阻断任何训练路径：在出现按规则版本区分的 BC 或归档采集路径之前，整理出的语料仍是暂存集。

**Procedure:** 运行 `python -m unittest tests.test_replay_curate -v`，再整理一个归档样本，并从四个月度归档（`202412`、`202607`、`202608`、`202609`）重新整理语料到临时输出目录，逐成员对比 `inventory.jsonl` 与 `data/replays_curated/inventory.jsonl`。

**Pass:** 回退 `initial = start if start is not None else scenario` 分支时归档测试必须失败；把赛后的"接管某方"消息或同一玩家的重连计为换人时，换人测试必须失败；每个整理出的 `.gz` 解压内容重算后与其记录的 `payload_sha256` 一致，`.gz` 字节与其 `curated_sha256` 一致；选定数、同局族数与格式统计完全复现（1,076 局、1,076 族、359,526 个决策意图）；原始文件未被修改。

**Evidence:** `verification/acceptance_20261030/REPORT.md`（2026-10-30 参考巡检：逐字节重建与哈希）以及 `verification/replay_archive_20261029/`、`verification/replay_corpus_audit_20261030/` 与 `verification/replay_archive_2026q3_20261030/`；Ubuntu 跑通后追加一份带日期的 `verification/` 报告。

## 执行与报告

1. 确认变更所有者、激活事项与可复用证据。预先声明行/窗口/步数/对局上限与数值容差；只实现需要的断言或助手；运行前记录真实命令。
2. 先跑受影响的本地确定性检查，再跑相关 Ubuntu 检查。真实对局只在该事项被激活并另行授权后启动。
3. 受影响检查通过即停止；修复后只重跑失败用例及其变更依赖。

一份带日期的 `verification/acceptance_<date>/REPORT.md`，仅在用到时创建产物子目录：

```text
Scope: 行为/提交；激活事项；排除项与原因
Identity: 源码/扩展构建、Ubuntu/Python/torch、catalog/profile/teacher/schema、
          输入/模型/优化器哈希、种子/计划/游标（如相关）
Commands: 可执行命令、cwd、参数、退出码、耗时
Results: 用例 | PASS / FAIL / NOT RUN / REUSED | 断言/计数 | 产物
Reuse: 原报告 + 身份匹配；复用不是新运行
Failure: 首个不同输入/步骤、期望/实际、复现方式
Resources: 行/窗口/族/解码/步数/子进程；相关时峰值 RSS/PSS
Gate: 可进入指定下一阶段 / 被阻断；缩减面板不充分
Limits: 未写的测试、缺失输入/运行时、未证的质量/棋力
```

证据中不得包含凭据。失败、缺失必需观察、静默跳过或身份不匹配都会阻断受影响事项的验收。纯文档变更只跑文档、链接与差异检查。本计划没有运行时结论。
