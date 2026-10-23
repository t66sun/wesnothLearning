# 已实现但待验收

> 语言：[English](TEST.md) | 中文

更新日期：2026-10-24。仅余原版新增终态采集待验收。已通过的阶段/PPO 证据见 [修复报告](../verification/training_repair_20261023/REPORT.md)，修正后移动质量与状态复用见 [后续报告](../verification/bc_rootcause_20261023_2318/REPORT.md)。已通过范围归档，不重复测试。

## T6：原版新增终态观测采集

**状态/原因：** native runtime 与解析器已接入独立 METRIC 事件，共用终态统计合同；本轮 Ubuntu 实际采集验证覆盖 lite，未执行新的原版终态游戏。现有原版验收不能代替这段新增生产路径。

**最小 Ubuntu 方案：** 后续需要 native 训练/评测时，复用原版 1.18.8 和当前规则/轻量 LearningSupport，执行一个限定 5 回合的固定提前淘汰/终局场景，再复用已有预算截断反例。只核对 initial/eliminated/terminal 事件、存活侧与真实自身 HP、结果解析和 shard 不含 metric_event；缺事件报缺测。场景 helper 尚未编写，不需要重复原版规则或性能矩阵。

**通过/阻塞/证据：** 真实终态可构成 T5/T10 吸收态，故障与预算截断不能补终态，actor/BC/PPO 行不被污染。仅阻塞新增 native 终态采集的验收，不阻塞默认纯 lite 流程。命令、源码/规则身份与原始事件归档至 `verification/native_terminal_<日期>/`，通过后删除整项。
