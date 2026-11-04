# WesnothLearning

> 语言：[English](../README.md) | 中文

面向 Wesnoth 1.18.8 的三个独立模型：单挑 `duel`、四人混战 `ffa4`、团队 `team2v2`。训练使用 Python/PyTorch、原版与 Rust 精简引擎，最终部署为原版游戏内的纯 Lua AI。

## 文档入口

- [架构与参数](architecture_zh.md)：当前实现、其契约与限制。
- [待验收清单](TEST_zh.md)：只列仍未完成的验收工作，每项给出最小 Ubuntu 流程。
- [Agent 训练操作指南](instructions_zh.md)：接手环境、启动/恢复、维护排障及按指令调参。
- [来源与许可](THIRD_PARTY_zh.md)：第三方代码、参考选手包与官方组件许可。

采集输入位于 `data/`，训练状态位于 `runs/`，导出模型位于 `delivery/`，验收证据位于 `verification/`。

## 开发入口

```bash
./setup.sh --device cpu
./run.sh --help
```

训练和采集需按用户指令启动。
