# WesnothLearning

> 语言：[English](../README.md) | 中文

面向 Wesnoth 1.18.8 的三个独立模型：单挑 `duel`、四人混战 `ffa4`、团队 `team2v2`。训练使用 Python/PyTorch、原版与 Rust 精简引擎，最终部署为原版游戏内的纯 Lua AI。

## 文档入口

- [架构、参数与已实现/未实现项](architecture_zh.md)：后续统一维护的架构文档，替代旧 PLAN。
- [待验收清单](TEST_zh.md)：已实现修改通向正式训练的最小 Ubuntu 验收方案。
- [Agent 训练操作指南](instructions_zh.md)：接手环境、启动/恢复、维护排障及按指令调参。
- [Ubuntu 24.04 训练归档包](bundle_zh.md)：构建并校验可解压即用的归档包，在干净机器上安装并启动训练。
- [来源与许可](THIRD_PARTY_zh.md)：第三方代码、参考选手包与官方组件许可。

当前预训练采集目标为单挑 **300**、FF4 **600**、2v2 **400** 个有效 Astra 教师对局，合计 **1300 局**，全部使用 lite、0 原版锚点；默认全局 **8 workers**。上述默认值已在 Ubuntu 通过受限验收；此前正式实验已失败结束，当前未启动新正式训练。

Rust 规则核、空间/关系/记忆模型、BC/PPO/DAgger、奖励在线控制、纯 Lua 导出均已有实现。新实验默认 lite，使用 `data/rules/1.18.8-training` 的 587 单位和 438 地形，按六阵营 158 单位训练闭包检查启动，三赛制接入真实 Astra 教师。完整战役行为、全流水线性能与正式训练强度的边界见架构文档。

当前实现为 schema 5 / 候选 v3，补充四人 BC 所需的公开战术输入；Ubuntu 已通过 BC→PPO→最终评测的受限链路，质量证据余项见 `docs/TEST_zh.md`。支持 `run --phase bc`、`phase ppo` 和 `phase evaluate` 分阶段运行，显式 `--force --reason` 可跳过 BC 资格并保留真实门结果。旧正式实验冻结 schema 4/v2，新旧数据和检查点不自动迁移。

原始验证证据位于 `verification/`，实验与交付产物位于 `runs/`、`delivery/`，全部采集输入（规则包、人类与教师数据集、回放转储、参考对手）位于 `data/`；开发源码包默认不包含原始验证结果。V4 权重、旧实验与已安装 AI 保持历史状态，新架构不兼容旧 schema 3 的权重和优化器。

面向干净 Ubuntu 24.04 机器只有一个可解压即用的归档包：`python -m learning bundle --output PATH` 生成，`python -m learning verify-bundle ARCHIVE` 做静态校验，其中不含 `.git`、虚拟环境、运行状态、验证证据、交付产物或原始回放转储。解压副本中的 `./setup.sh` 安装系统包、固定版本 torch 2.9.1、`_engine_lite` 与 Wesnoth 1.18.8，不启动采样或训练；`./train.sh` 仅在用户明确指令后启动一次实验。构建并校验归档包只证明安装可用，从不证明收敛或棋力；Ubuntu 24.04 运行时尚未执行，作为 `PKG1` 跟踪于 `docs/TEST_zh.md`。详见 [docs/bundle_zh.md](bundle_zh.md)。

## 开发入口

```bash
./setup.sh --device cpu
./run.sh --help
```

训练和采集需按用户指令启动。修改后仅验证受影响的最小行为，已通过项按有效证据复用；文档整理不触发重新训练、全量测试或性能矩阵。
