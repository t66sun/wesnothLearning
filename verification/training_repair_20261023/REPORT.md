# 2026-10-23 训练故障修复与最小验收

已完成默认 lite 流程的故障修复、独立阶段入口及 Ubuntu 受限验收。本轮没有新建正式训练，没有覆盖原主项目、旧 run、权重或原虚拟环境；服务器最终检查没有活动训练进程。

## 实现

- 保留 DeepSeek 的 `ref[name]` 修复；控制指标异常独立落盘、冻结 adaptive，继续执行真实 BC/开局检查。采样、优化器等真实训练故障保留 failed_stage/pending，以非零失败退出，不自动消费最终留出评测。
- Astra 参考按当前验证层补缺口，每次最多 12，后续调用继续前进；编号从全部尝试 ID 中找未用值，不再用成功数量猜下一个 ID。严格匹配规则、引擎、格式、地图、阵营、上下文、教师及统计版本，参考标签不混入验证标签。
- `terminal-horizons-v2` 使用独立初始/淘汰/终局合法观测。真实提前终态允许吸收至 T5/T10；淘汰控制/领袖为零，损失为真实自身 HP 减少除以已观测单位最大 HP 总量。预算截断/故障不补终态；缺观测仍缺测，快照不进入 actor、BC/PPO 或记忆写入。原版也接入事件生产/解析，但该生产路径实际游戏待 T6。
- 开局诊断保留 side，只检查学习方。合理结束回合使用已有合法移动候选对应的非领袖剩余移动量，阈值仍为 4，不增加寻路；保留 raw remaining_moves 供诊断。开局地图/对局族身份按实际探针地图记录。
- 修正 schema 5 插入动作字段后 repeated_move 误读 move_primary；从导出 schema 按名称索引。战术输入仍只复用公共信息，128 候选/16 次预测预算不变。
- 新增 `run --phase bc` 与 `phase {show,auto,bc,ppo,evaluate}`。运行中批次边界生效，停止后需 resume。强制 PPO 必须 `--force --reason`，保留真实 effective=false 和强转出处；阶段预算单独保存，不改原 manifest/clock；恢复先完成已有 pending_train 的原方法。
- 修复实际恢复暴露的内部策略目录误套 SDK 16 MiB 提交限制：内部恢复检查 schema、入口和权重 SHA；正式提交的 SDK 限制保留。
- 晋升要求实际达到 12 完整块，避免欠样本面板把旧 BC 写成 best；最终无 best 时优先 last_ppo，再 last_bc/latest。

## Ubuntu 身份和环境

```text
源码/测试目录：/home/tongshu/myDev/wesnothLearning/validation_training_repair_20261023_194022
Python：上述目录/.venv/bin/python
规则 SHA-256：d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca
数据 schema：5；候选：fixed-20000-v3；架构：relational_v5
每套模型：776178 参数；CPU，单线程
```

隔离环境复用已安装 torch/numpy/lupa 等依赖，拥有自己编译的 `_engine_lite`。现有 `/home/tongshu/venv/bin/maturin` ELF 在隔离 VIRTUAL_ENV 执行 `develop --release --manifest-path engine_lite/Cargo.toml`，构建成功（11.67 s）。初始 `python -m maturin` 环境入口失败；一次 pip 下载超时未安装包，随后直接使用已有 ELF，未继续安装依赖。扩展真实 `.so` 及关键源码的字节哈希见 `final_identity.json`，检查点/阶段/开局与数值摘要见 `acceptance_summary.json`。

Rust 通过 include_str! 嵌入 host.lua；换源码后必须重编对应环境。原服务器主项目没有 `.git`、未安装 git，本轮使用隔离部署测试，原目录未同步修复；下一位操作者应使用上述已验收目录及其 Python，或先部署本次已提交源码并重编。旧 schema 4 实验不直接迁移。

## 实际命令与结果

以下 Python 脚本从隔离根目录执行；投递方式为 SSH stdin，内容与本目录脚本一致。原始日志保留在同名 `.ubuntu.txt` 和远程测试目录。只补测改动影响范围，没有重跑规则/性能/并发全矩阵。

```text
python -u - < run_ubuntu_tests.py
  71 tests / 17.070 s / OK
python -u - < check_remaining.py
  后续新改动的 7 项受影响检查 / 0.409 s / OK（与上批部分重叠，不计作 78 个不同测试）
python -u - < smoke_stages.py
  STAGE_SMOKE_PASS duel
  STAGE_SMOKE_PASS ffa4
  STAGE_SMOKE_PASS team2v2
  ALL_STAGE_SMOKES_PASS / EXIT 0
python -u - < smoke_cli_boundary.py
  Experiment: stage_complete / CLI_COORDINATOR_BOUNDARY_PASS / EXIT 0
python -u - < check_real_opening_parity.py
  REAL_OPENING_PARITY_PASS / EXIT 0
python -B -m unittest tests.v5.test_candidate_provenance -v
  最终复核涉及的来源断言 / 3 tests / 0.322 s / OK
```

71 项覆盖战术输入、真实 early-kill、终态统计、参考补采、故障边界、控制器、lite 采集/默认入口和验证调度。后续 7 项专门验证内部导出恢复、欠面板不晋升及阶段预算/切换/待训练批次语义。Windows 仅参考，不替代 Ubuntu 结果。

### 关键节点的实际链路

| 赛制 | 真实更新方法 | 每次优化更新 | 恢复后的最终选择 | 最终面板 |
| --- | --- | --- | --- | --- |
| duel | BC → PPO → PPO | 1 / 1 / 1 | v102 / last_ppo | 1/30 块，inconclusive |
| ffa4 | BC → PPO → PPO | 1 / 1 / 1 | v102 / last_ppo | 1/30 块，inconclusive |
| team2v2 | BC → PPO → PPO | 1 / 1 / 1 | v102 / last_ppo | 1/30 块，两个队友上下文均执行，inconclusive |

使用真实 Astra、lite、采集轨迹、BC/PPO 优化器、检查点恢复和最终比较。为直接覆盖故障点，初始版本设 99，执行一次真实 BC 更新后进入 v100；**没有声称训练了 100 批**。每个游戏最多 3 回合，每族教师 2 局，BC 读取 128，epochs=1。验证/最终仅执行一个完整轮换块；最终原合同仍计划 30 块，缺 29 块明确 inconclusive。最终 selected.pt SHA 与 last_ppo.pt 一致，last_bc.pt SHA 未变。

短测真实 BC 门未过。正常 phase ppo 被拒绝，然后才通过实际 CLI `--force --reason 'isolated real stage-handoff smoke' --hours .25` 转 PPO，effective 始终 false，原因/ID/版本留存。自动正常切换的通过/未通过分支用最小调度检查分别验证；本次不宣称六阵营 BC 收敛或全部门已过。

CLI/协调器另以极短 BC 预算实跑一个 trainer 进程，确认停止于 bc_complete、根汇总 stage_complete、没有 selected.pt，phase show 无待处理请求。

### 实际开局和推理一致性

各赛制两局、最多 5 回合的 Astra 正例检查出城/占村/合理结束；duel 特意使用 Northerners。学习方首回合 raw remaining_moves=5、usable_moves=0 时合理结束通过，后续空余普通单位移动仍如实报告 14/25 等，不把所有结束都写成零。对手动作替学生过门的反例由新增回归覆盖。**Astra 正例不是学生 BC 质量达标证明。**

复用同一轮刚训练完的真实 PPO v102 权重及真实当前 schema 教师轨迹，每族 8 条、连续两回合、含 128 候选，PyTorch/Lua 最大绝对误差：

- duel：1.3925625232807937e-08
- ffa4：1.5902660563393844e-08
- team2v2：1.505338401153189e-08

均低于既定 1e-5。检查包含实际连续记忆写入，不是随机向量或初始化网络替代。

## 修复中发现并关闭的问题

首次真实恢复暴露内部导出 >16 MiB 被 SDK 拒绝，再暴露 JSON 列表/tuple schema 比较；分别修正后通过真实恢复和权重损坏反例。首次最终选择仍落在欠面板晋升的 BC best，修正为必须实际达到 12 块后，新的 `stage_outputs_v2/` 三族完整通过；旧 `stage_outputs/` 保留失败状态，没有改成新证据。

开局辅助脚本起初漏了显式 allow_approximate，并直接携带 native-only baseline，分别被已有门禁拒绝；补回生产调度已有的 lite 参数/对手映射后继续，只重跑未通过项，duel/ffa4 已通过证据复用。上述为测试脚本接入错误，不放宽生产门禁。

PR 复核补查发现旧来源测试把新增诊断观测也当作策略决策，导致 Windows 最小复现失败。更新断言区分诊断/策略/教师，明确诊断不生成完整候选且不进入 shard，三个受影响检查在 Ubuntu 通过（`candidate_provenance.ubuntu.txt`）；生产代码无需再改，已通过的真实阶段链路不重跑。

## 剩余验收和下一轮入口

`docs/TEST.md` 只保留 T5 修正后六阵营受限 BC 质量、T6 原版新增终态生产路径。当前证据不证明 adaptive 长期效果、正式收敛、原版棋力或完整最终验收。默认 300/600/400、8 workers、Astra、原 BC/晋升/最终门均保留。

分阶段使用方法已写入 `docs/instructions.md`。新正式训练仍需用户明确启动指令；本轮没有新建常驻任务或训练。最后 `pgrep -af 'python.*learning.*run'` 为空，SSH 测试会话已结束。
