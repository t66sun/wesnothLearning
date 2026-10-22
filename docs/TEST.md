# 正式训练前待验收清单

更新日期：2026-10-22（T1–T4 已在 Ubuntu 执行完毕）。本文件按维护规则只保留**已实现、尚未通过当前版本验收**的事项；本轮四项全部通过，已通过项的详细方案删除，结论、命令、指标与证据保留在下面的验收结果表中。当前本文件**没有未验收事项**；后续新增功能按同样格式追加。

架构、参数和门槛以 [architecture.md](architecture.md) 为准，服务器操作按 [instructions.md](instructions.md)。原始输出、身份哈希与逐项数据在 [verification/pretrain_acceptance_20261022/](../verification/pretrain_acceptance_20261022/)（含 `identity.json`、`T1_ubuntu.txt`、`T2_T3_items.txt`、`T123_affected_suite.txt`、`t3_coverage.json`、`t4_plan.json`、`T4_summary.json`）。

## 共用准备（已执行）

Ubuntu 主项目 `/home/tongshu/myDev/wesnothLearning/WesnothLearning`，venv `/home/tongshu/venv/bin/python`。按本批源码重新编译扩展：`maturin develop --release --manifest-path engine_lite/Cargo.toml`（增量 3.22 s），实际加载 `/home/tongshu/venv/lib/python3.12/site-packages/_engine_lite`。核对的批内身份：python 3.12.3、torch 2.9.1+cpu、8 逻辑核；`_engine_lite` md5 `d95534897b41ae8ebefcd34ffc45ade7`，ENGINE_VERSION `lite-0.1`、RNG `xoshiro256++-1`；Astra ZIP sha256 `2a216c96…dc933`；`rules/1.18.8-training/rules.json` `d6fceafe…26dca`；`lua/candidates.lua` `8f621091…b633`；`engine_lite/lua/host.lua` `04d990d0…eff0`；`learning/experiment.py` `ea7fe575…19dc`；`learning/lite_host.py` `243522fc…9cb`。同步只覆盖学习/测试源码，未改动 `runs/`、`humanData_curated/`、`releases/`、`vendor/`、`tmp/`。

受影响的 13 个测试模块合并复跑：`Ran 149 tests in 31.889 s — OK`（`T123_affected_suite.txt`），覆盖 T1–T3 全部新增用例及相邻的 `tests.v5.test_lite_policy_memory`、`tests.v5.test_friendly_transit`。

## 验收结果（2026-10-22，Ubuntu）

| 项 | 结论 | 命令 / 规模 | 关键指标 | 阻塞 |
| --- | --- | --- | --- | --- |
| T1 BC 默认配额与全局并发 | pass | `python -m unittest tests.test_training_revision.RevisionTests.test_targets_and_cpu_preset tests.v5.test_lite_default` → `Ran 9 tests in 0.890 s OK` | 默认 duel/ffa4/team2v2 = 300/600/400，workers 8，每 trainer 1 线程，lite native 锚点 0/0/0；`--engine native` 时锚点等于各目标；CLI 省略参数与程序默认一致；显式 `--bc-games`/`--workers` 覆盖生效；`--resume` 读回冻结的 config/clock，不被 CLI 改写；末批按剩余额度截断（目标 5 的 4 条有效）且失败局不计有效配额 | 解除 |
| T2 未采集座位跳过完整候选 | pass | `python -m unittest tests.v5.test_candidate_gating tests.v5.test_pipeline_contract` → `Ran 101 tests in 25.331 s OK` | 未采集 Astra 座位 `C.generate` 调用数 0（`timing` 无 `budget`，候选只有 1 个 `end_turn`，`truncated=false`）；采集座位/学生策略/DAgger/截断 bootstrap 每次决策恰好 1 次完整生成且带 `budget='fixed-20000-v2'`；team2v2 learner{1,3} 与 ffa4 learner{1} 各 12 步双引擎对照：`teacher_action`、去 `timing` 的 DTO、执行后快照与 `reward_raw` 逐项相等；DAgger 查询 ≤32 | 解除 |
| T3 duel/2v2 覆盖与候选 v2 来源 | pass | 五个新模块 + `tests.test_lua_contracts` → `Ran 27 tests in 0.679 s OK`；真实样本 `python verification/pretrain_acceptance_20261022/t3_coverage.py --turns 12`（每赛制 1 局，wall 67.5 s） | 固定状态：村庄记忆键 `x*1000+y`、失视野后保留归属、side 隔离、snapshot/restore 往返；候选池 128 上限 + 每单位保留一条 `full` 移动 + 战斗预测 16；2v2 友军占村影响战略目标但不可落脚；单挑受伤分支放弃敌方目标。真实覆盖（原生训练地图，train 分区）：duel `the_freelands` move 84/84、attack 88/92、move_attack 67/71、recruit 34/34、end_turn 24/24（234 决策），team2v2 `clash` move 135/135、attack 105/111、move_attack 91/97、recruit 49/49、end_turn 48/48（343 决策）；`audit_bc` 两赛制 `coverage` 0.983、`coverage_pass: true`、`missing_intent 0`；v1/v2 来源经人类导入路径双向核对 | 解除 |
| T4 8 workers 最小真实链路 | pass | `python tests/smoke_training_lite_8worker.py`（用户授权后执行）→ 15 项检查全绿，`duration 37.5 s`，12 个任务（9 教师 + 3 rollout） | broker `peak_native_games=8`，scheduler `active_peak=8`（24 行 / 12 区间），跨赛制 54 对；采样与更新重叠 6 次；三个 trainer 退出码 0/0/0、结果 `complete`；语料 duel 207 / ffa4 224 / team2v2 195 行，来源 `astra`+`lite`、`candidate_version` v2；BC 更新 1 批（loss 4.66/4.46/4.33，检查点版本 1 回读）；rollout 各 1 局，on-policy 5/17/6 行 + 同数 bootstrap，DAgger 查询 1/4/1，PPO 更新 1 批（loss 0.380/0.392/0.308，版本 2 回读）；138 次内存采样：峰值 PSS 4.02 GiB（上限 12）、峰值 RSS 4.85 GiB、最低 available 10.46 GiB、swap 增长 0；无残留进程；`state.effective` 保持 false | 解除 |

教师局与 rollout 口径：教师任务 `turn_cap=10`，`turns` 字段来自 `learning/lite_host.py:232` 回传的引擎回合计数（截断局报 11），验证按 `turn_cap≤10` 判定。原生训练地图出现在教师阶段：duel `the_freelands`、ffa4/team2v2 `clash`。T4 的 8 worker 结论不要求相对 4 worker 的固定加速比，也不证明收敛或长时间稳定性。

## 执行中的偏差与遗留

- T4 harness 自身两处缺陷在首次运行暴露并修复后重跑；两次失败均属 harness 判定，不是产品缺陷：`reward_version` 为 0 被真假值判定误判为缺失（`tests/smoke_training_lite_8worker.py:507`）、DAgger 查询计数直接 `json.loads` 未解包 rowpack 行（`:594`）。失败输出保留为 `T4_ubuntu_run.txt`、`T4_ubuntu_run2.txt`。
- T3 第 1 步把“未采集座位写出 v1 行”按字面实现不可达：`learning/lite_host.py:133` 的精简路径只给 `learning.sides` 之外的教师座位，而 `:137` 只记录学习者座位，因此 `play_lite_job` 不会把 v1 行落盘。用例改为断言可达事实（落盘行全为 v2，未采集座位捕获的 DTO 经 `:162` 表达式推出 v1），v1 分支由人类导入路径双向覆盖。
- 记录但未断言的产品观察：`snapshot()`/`restore()` 往返 `game` 与 `host['teacher_memory']` 完全一致，但已行动一方在 `host['memory'][side]['reward']` 上不一致（side 1 一致）。写在 `tests/v5/test_village_memory_ledger.py` 模块说明中，未作为通过条件。
- 本地 Windows 的 `_engine_lite.pyd` 早于本批 Lua（内嵌 `host.lua` 未含 `x*1000+y`，`decision` 仍为 3 参数），Windows 上相关断言会失败且无 cargo 可重编；验收以 Ubuntu 为准。
- 真实覆盖样本需要 `rules/1.18.8-training`（`resolve_dir()`）与 `allow_approximate=True`：旧 `rules/1.18.8` 缺训练闭包（`Fugitive`、`Ghast`、`Mage of Light`、`Necrophage`）且地形表拒绝原生地图（`unknown terrain _off^_usr`）。
- 本轮只证明最小接入与资源边界：未采满 1300 局、未跑 PPO 收敛、未重做全流水线性能与最终原版评测；旧覆盖统计不随源码修改自动更新。正式训练仍需用户指定时长、实验目录和启动指令。
