# 2026-10-23 服务器历史训练归档

按用户“归档清理之前的训练记录和产物，只留最近两次”执行完成。按 manifest/clock 的实际开始时间选择正式实验，短测和后来修改的 mtime 不参与“最近两次”排序。本轮未启动训练、未修改训练参数、未停止其他进程。

保留在原 `runs/` 的两次正式实验与两份对应主日志：

- `v5_lite20h_20261022_210712`
- `v5_lite6000_replay_20261022_012336`

归档目录：

```text
/home/tongshu/myDev/wesnothLearning/training_archives/20261023_212221/
```

该目录含 6 个 `.tar.zst`、`index.json`、`SHA256SUMS` 和恢复说明 `README.md`。原项目为 `/home/tongshu/myDev/wesnothLearning/WesnothLearning`。

## 归档与清理范围

| 归档 | 原目录相对项目根 |
| --- | --- |
| v5_20261021_203930 | runs/v5_20261021_203930 |
| v5_20261022_000850 | runs/v5_20261022_000850 |
| v5_lite6000_replay_20261022_011309 | runs/v5_lite6000_replay_20261022_011309 |
| loopback_20261021_232345 | runs/loopback_20261021_232345 |
| bc_v4_cpu_72h_20261019 | releases/bc_v4_20261018/runs/bc_v4_cpu_72h_20261019 |
| bc_v4_cpu_72h_w8_20261019 | releases/bc_v4_20261018/runs/bc_v4_cpu_72h_w8_20261019 |

每个训练归档同时包含对应 `runs/logs` 日志或 V4 `.ops` 中按 run 名标识的启动/停止记录。完整冻结配置、源码、数据、策略、检查点和 V4 导出产物一并保留；tar 保留原文件时间和相对路径，不重写历史报告或规则哈希。仅上述已验证内容的原始路径被清理。

源码、规则、教师 ZIP、人类数据、已安装 AI、历史规则/验收报告及最近 `validation_training_repair_20261023_194022` 隔离环境没有清理。V4 release 源码保留，其 `runs/` 已空；主项目 `runs/` 仅余上述两次正式实验和 `logs/`。未按文件名全局删除日志或权重。

## 验证结果

由 `archive_remote.py` 经 SSH stdin 在 Ubuntu 执行，退出码 0。该文件为本次精确列举路径的一次性操作记录，源目录已删除，不应再次直接运行。

1. 清理前确认无活动训练，检查进程 cwd、命令和打开文件没有使用待归档目录。操作前后均未发现活动训练。
2. 使用 GNU tar `--sparse -I 'zstd -T2 -3'` 创建归档；每份执行 `tar --zstd --compare` 与源目录比较完整内容及元数据，6 份退出码均为 0。
3. 记录归档 SHA-256 后，检查解析后的精确路径及受保留目录边界，才删除已比对的原目录/对应日志。归档目录在原项目之外，不与待清理路径重叠。
4. 保留两次实验的 32 个关键 manifest、clock、summary、state、BC gate 和检查点 SHA-256 前后一致。最后断言保留 run 集合与两份日志精确匹配，旧 V4 runs 为空。

原目录占用合计约 **24.10 GiB**，6 份压缩归档约 **11.31 GiB**，服务器可用空间净增加 **12.80 GiB**（13,740,785,664 字节）。归档索引含每份大小、SHA、比较结果和源路径；本目录 `index.json` 是服务器完成状态的副本。原始执行输出保留在本地同目录 `archive_remote.output.txt`。

## 查找与恢复

在服务器归档目录中可执行 `sha256sum -c SHA256SUMS` 复核，或按 index 只验证所需一份。本轮创建时已经逐份完整比对；没有为了测试恢复而重新展开全部旧产物。

按需选中归档，在确认原路径不存在后恢复：

```bash
tar --zstd -xf /home/tongshu/myDev/wesnothLearning/training_archives/20261023_212221/NAME.tar.zst \
  -C /home/tongshu/myDev/wesnothLearning/WesnothLearning
```

`NAME` 替换为表中归档名。成员已经带有 `runs/` 或 `releases/...` 原路径，不额外指定 run 子目录。恢复训练仍需使用该实验原源码/schema 和操作授权；本次没有建立周期性清理规则。
