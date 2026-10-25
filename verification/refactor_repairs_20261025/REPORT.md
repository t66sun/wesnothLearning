# V1–V6 专项修复与最小验收 — 2026-10-25

**结论：六项已证实缺陷已修复，12 项 Ubuntu 隔离微型回归通过。** 这只接受下述接线、身份和恢复行为，不宣称重构所有详细规格、SDK 交付包或棋力均通过。未启动真实对局、语料采集或正式训练；奖励、门限、局数配额与训练规模均未改变。

## 源码、范围与环境

- 起点：`ab4fa33`，其独立复核记录在只读的 [原报告](../refactor_review_20261025/REPORT.md)。先读 AGENTS、architecture、TEST 和该报告，再运行原 `reproduce_gaps.py`；六项均出现原报告的 `BUG_REPRODUCED` 信号，退出 0 仅代表复现成功。
- 六项实现合并完成于 `36cc99f8beb17dd186f397b983ffa2dee48eb382`。Ubuntu 测试源码/额外 holdout 重入断言在 `831eedbe08962ac755be563491d65e9fb45bc695`；后续文档与证据提交不改变这些 Python 实现或测试。
- 源码包：`git archive 831eedbe08962ac755be563491d65e9fb45bc695 learning lua tests vendor/arena engine_lite`，SHA256 `d07ed7e32329929e86c24e625ce151e829de697b135bc9e41c8d4e2a2a86f9a4`。服务器先验证此哈希再解包。
- Ubuntu 新隔离树：`/home/tongshu/myDev/wesnothLearning/acceptance_v1_v6_20261025_36cc99f_v2`；只读复用原验收树 `acceptance_refactor_20261025/master/data`，依赖复用 `/home/tongshu/venv/bin/python`，未改共享安装、原 run、原证据或已装模型。
- Ubuntu：Python 3.12.3 / PyTorch 2.9.1+cpu，Linux `7.0.0-38-generic`，扩展 `lite-0.2 / deterministic-expected_damage_v1 / expected_damage_v1`。完整实测身份见 [environment.log](ubuntu/environment.log)。未重编未变的扩展。
- 规则 SHA256：`d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`；教师 profile `expected_damage_v1`，源码 SHA256 `a5d4b3a69d5af0378fa22119f315c1300fb6ad965c79b08071eb4a37c0addbef`，脚本断言引擎/规则身份后才执行测试。
- Windows 只作参考：Python 3.12.14 / PyTorch 2.9.1+cpu；本地扩展仍为 `lite-0.1 / xoshiro256++-1`，未据此声称新引擎通过。工作树测试源码哈希与实际环境另存 [local_environment.json](local_environment.json)；Ubuntu 结论独立来自匹配的新扩展。

## 一行为一 PR

所有实现先在分支提交，经逐项差异审阅、对应最小本地验证、PR 合并及 master 推送完成；没有在 master 直接提交。

| 项 | PR / 实现 commit | 实际改动与会在还原后失败的断言 |
| --- | --- | --- |
| V1 | [#32](https://github.com/t66sun/wesnothLearning/pull/32) / `c61ecfc` | 最近完整候选先做完整 12-block Astra/冠军提名；欠面板/失败/时间不足有理由保留冠军。面板绑定 checkpoint/规则/教师/日程身份，冻结唯一 selected hash 后进入 holdout。`test_final_nomination` 经真实 schedule/comparisons、实际选择/最终入口/execute 和合成录制回复覆盖三赛制及已记录 holdout 重入。原缺文件反例不再崩溃。 |
| V2 | [#33](https://github.com/t66sun/wesnothLearning/pull/33) / `fe8d7db` | latest/last/best 共用完整 writer；best 在验证记账及 pending 清理后保存。实际 last_ppo/best_ppo/best/selected 三赛制检查身份、manifest、execution 和已完成记账；实际 export_checkpoints 检查身份及 Python/Lua 数值，错误身份仍拒绝。 |
| V3 | [#34](https://github.com/t66sun/wesnothLearning/pull/34) / `6145f9b` | PPO 恢复累计 committed/inspected，所有退出 cursor 保留累计计数；finish_train 中断时不提前结算，完成后只结算一次。真实保存/读回的两段 fixture 与连续对照均为 2 次 optimizer step、22 个已提交决策、2 个 effective passes；已完成 checkpoint 不留 pending。 |
| V4 | [#35](https://github.com/t66sun/wesnothLearning/pull/35) / `41b761d` | BC 抽样后、部分反传后、step 前取消均清梯度并恢复 batch 前 Python sampler RNG。实际 checkpoint 恢复后样本 ID、参数、optimizer 和 RNG 与连续参考一致；取消本身零更新。 |
| V5 | [#36](https://github.com/t66sun/wesnothLearning/pull/36) / `a3e7bc3` | content-v2 摘要绑定目标 ID、版本/来源、实际训练内容与合法原始记忆前缀；逐行计算且在本次调用内复用共享前缀摘要。20 种单字段/内容改动的记录先分别通过 validate_record，再在 finish_train 调用 train 前拒绝；等价数组/列表与原输入重读稳定。 |
| V6 | [#37](https://github.com/t66sun/wesnothLearning/pull/37) / `d166f7c` | Native Astra 与 deterministic-lite Astra 分别校验 engine/RNG/combat/profile 和已提供 source 身份。原生产路径缺 lite profile 的 native 行、新显式 native 行和 native DAgger 接受；12 种跨规则/缺身份反例拒绝。沿用既有 native source 标签，不将其声称为新测得的包哈希。 |

新增专题测试使用既有 helpers，未修改两份 grandfathered 超长测试。V1 另补的真实最终入口重入断言在 `831eedb`：第一次写入 60 个合成 holdout 回复（duel 的 30 个完整轮换块），第二次 collector 调用数仍为 1，selected hash 和结果一致；**60 是录制式 fixture job 数，真实游戏为 0**。

## 先失败、再修复的本地定位记录

这些失败均在修复前或修正测试 fixture 前观察到，没有把失败当成通过。

| 项 | 观察到的失败 |
| --- | --- |
| V1 | 新 3 项测试的 6 个子场景在真实 `_select_final` 读 v143 时报 FileNotFoundError。 |
| V2 | 新真实 writer 断言首先失败于 `last_ppo.pt` 的 `engine=None`。首次接通后又观察到真实 SDK 16 MiB 门禁失败，详见下节；另一个 cadence mock 缺 manifest 的 fixture 接缝已改到共用 writer。 |
| V3 | 两个新断言分别观察到运行级 11 而非 22，以及重复截止恢复的 committed=0 而非 11。 |
| V4 | 三个取消边界均观察到零更新但 Python RNG 前进。 |
| V5 | 新断言观察到 18 种改动摘要碰撞；其中 choice 反例最初没有同步实际动作而被 validator 拒绝，修正为合法动作标签后纳入最终 20 例。完整身份实现还揭示旧测试截取 suffix 时未带前缀，fixture 已先 attach_histories 再截取。 |
| V6 | 原 native 合法行被 lite profile 检查拒绝，同时 5 个混入反例未抛错。 |

还原各生产修复会恢复对应原始红色断言；新断言并未改成匹配错误输出。原诊断脚本及旧报告保持原字节，不把它们改写为修复后验收脚本。

## 本地执行结果

仓库根目录，`.venv/Scripts/python.exe -B -m unittest ...`；`OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1`。以下日志均保留首次真实结果，后续修正写新文件。

| 检查模块 | 状态 / 数量 / 时间 | 日志 |
| --- | --- | --- |
| `test_final_nomination test_selection` | PASS，8 项，4.906 s | [V1_local.log](V1_local.log) |
| `test_checkpoint_export_identity test_final_nomination test_validation_cadence` 首次接通 | FAIL，8 项/2 errors，36.610 s：实际 SDK 包超限、cadence fixture 接缝 | [V2_local.log](V2_local.log) |
| `test_checkpoint_export_identity test_validation_cadence` 修正后 | PASS，5 项，32.146 s；只接受身份/数值接线，包组装隔离 | [V2_local_fixed.log](V2_local_fixed.log) |
| `test_ppo_resume_counters test_ppo_plan` | PASS，10 项，18.441 s | [V3_local.log](V3_local.log) |
| `test_bc_cancel_rng test_learner_extraction` | PASS，5 项，3.650 s | [V4_local.log](V4_local.log) |
| `test_rollout_content_identity test_checkpoint_ops` 首次接通 | FAIL，6 项/1 error：旧 suffix fixture 缺完整前缀 | [V5_local.log](V5_local.log) |
| 同上，fixture 修正后 | PASS，6 项，8.332 s | [V5_local_fixed.log](V5_local_fixed.log) |
| `test_teacher_engine_identity test_astra_adaptation` | PASS，5 项，0.136 s | [V6_local.log](V6_local.log) |
| 六个新增专题组合 | PASS，11 项，55.238 s | [combined_local.log](combined_local.log) |
| 追加的 production final/execute 重入断言 | PASS，1 项，2.910 s | [V1_holdout_local.log](V1_holdout_local.log) |

V2 用实际新 checkpoint writer 和实际 export_checkpoints/verify_numerics；三格式各两回合、每回合一条合成公共记录，保留 128 候选，容差 1e-5。其版本/更新元数据是微型 fixture，未用新训练权重声称已训练模型质量。最终包组装在专项接线测试中明确隔离；生产 SDK 门禁未删除或降低。

## Ubuntu 隔离最小验收

只执行用户逐条授权的 SCP/SSH 命令。第一次 [run_ubuntu.sh](run_ubuntu.sh) 校验包哈希后，在目录前置检查以 1 退出，尚未生成环境/测试日志：**NOT RUN，不是测试失败或通过**。原输出不足以区分两个目录 guard，未编造具体失败目录；保留 [ubuntu_setup_failure.log](ubuntu_setup_failure.log)。

另获三条修正命令授权后，[run_ubuntu_v2.sh](run_ubuntu_v2.sh) 使用原验收报告明确记录的只读 provision 和独立 `_v2` 目录。它不覆盖首次目录，不重试任何失败测试、不重建扩展、不修改安装依赖。源码包与 12 个测试不变。执行命令：

```powershell
scp "$env:TEMP/wesnoth-v1-v6-36cc99f.tar" cpuServer:/tmp/wesnoth-v1-v6-36cc99f.tar
scp verification/refactor_repairs_20261025/run_ubuntu.sh cpuServer:/tmp/wesnoth-v1-v6-36cc99f.sh
ssh cpuServer "bash /tmp/wesnoth-v1-v6-36cc99f.sh 831eedbe08962ac755be563491d65e9fb45bc695 d07ed7e32329929e86c24e625ce151e829de697b135bc9e41c8d4e2a2a86f9a4"
# 上述首次准备退出 1；以下为另行授权的修正版。
scp verification/refactor_repairs_20261025/run_ubuntu_v2.sh cpuServer:/tmp/wesnoth-v1-v6-36cc99f-v2.sh
ssh cpuServer "bash /tmp/wesnoth-v1-v6-36cc99f-v2.sh 831eedbe08962ac755be563491d65e9fb45bc695 d07ed7e32329929e86c24e625ce151e829de697b135bc9e41c8d4e2a2a86f9a4"
scp cpuServer:/home/tongshu/myDev/wesnothLearning/acceptance_v1_v6_20261025_36cc99f_v2/logs/environment.log cpuServer:/home/tongshu/myDev/wesnothLearning/acceptance_v1_v6_20261025_36cc99f_v2/logs/targeted.log verification/refactor_repairs_20261025/ubuntu/
```

SCP 均退出 0；修正版 SSH 退出 0。首次授权的旧目录日志回传命令因测试未运行/日志不存在而未执行。

脚本在隔离树用 `/home/tongshu/venv/bin/python -B -m unittest -v` 运行六个新增专题（下列每项均 `ok`），不是全套验收：

| 专题 | 测试数 | 状态 |
| --- | ---: | --- |
| `tests.v5.test_final_nomination` | 4 | PASS |
| `tests.v5.test_checkpoint_export_identity` | 1 | PASS：身份/数值接线，非 SDK 包 |
| `tests.v5.test_ppo_resume_counters` | 2 | PASS |
| `tests.v5.test_bc_cancel_rng` | 1（3 个取消边界） | PASS |
| `tests.v5.test_rollout_content_identity` | 2（20 个有效输入变更） | PASS |
| `tests.v5.test_teacher_engine_identity` | 2 | PASS |

原始结果：[targeted.log](ubuntu/targeted.log)：**12 项 / 16.664 s / OK / exit 0**；`/usr/bin/time -v` 墙钟 17.64 s，峰值 RSS 520,768 KiB（约 508.6 MiB），swap=0。这是微型测试进程的观测，不是正式训练内存界限或吞吐结论。

fixture 固定使用已有 seeds（PPO 模型 41、plan 5、采样 13；BC 模型 73、采样 125）。PPO 每比较分支最多两 epoch/两 optimizer steps、11 个不同目标；BC 每分支一逻辑更新、两条输入；V2 无真实 learner step，三格式各两条数值审计记录。目标/参数/optimizer/RNG 身份相等由对应断言核对；这些临时 checkpoint 自动删除，不作为待交付训练模型。

## 复用、未运行和未通过

- **REUSED：** [原验收报告](../refactor_acceptance_20261025/REPORT.md) 的 Ubuntu 273 项 Python、17 项阶段、13 项 Rust，仅用于未变职责。`git diff --quiet e1181ea HEAD -- engine_lite/src engine_lite/lua lua learning/teachers` 返回 0，规则哈希一致；Rust/公共 Lua/教师值函数未改，不重跑它们。原 loader、控制器、存储/worker 证据按原限制复用，不重跑全语料或八 worker 矩阵。
- **FAIL，保留：** 本地真实 SDK 包组装触发既有 16 MiB 限制。当前架构早已记录三模型本地 add-on 超限；本轮不改该门禁、不修 SDK 体积、不把隔离包组装后的身份接线通过写成 SDK 交付通过。
- **NOT RUN：** 正式训练/新语料采集、完整新三赛制真实 BC→PPO→恢复→final 链、真实 native 游戏/迁移棋力、完整合法棋盘六战术 query/ranking 及教师棋力、30-block 真实 holdout 实力评测、完整语料重编码和完整测试矩阵。
- **未实现/仍待验：** P6/D1 外部推理未实现；N1 native 终态路径待验；原 TEST 中更广的梯度/完整重放等未证断言继续保留。原 L1 已观察到的 duel fallback 链事实保留，不扩成全流程/同未来/所有赛制通过。
- **兼容限制：** 内容摘要升级会拒绝旧 pending_train 的弱摘要，未自动迁移旧 run；冻结输入、历史报告、manifest、权重和哈希均未回填。新的预算显式预留仍是未来 manifest 的提案，现有时钟未延长；最终面板超时仍为 inconclusive。

## 文档与交付状态

已同步英文/中文 architecture、TEST。C9 与 V1–V6 完成项从 TEST 整项删除，记录在本报告；其余未证断言仍按原范围保留。修正了 architecture 10.9 将已实现阶段仍称为“未开始”的陈旧状态表述，不改变任何设计决策、奖励或训练参数。

本轮允许关闭的是六项已证实修复的微型接线/恢复验收。完整重构、SDK 包、教师或模型棋力没有由此获得额外通过结论；本报告与代码不授权启动正式训练。
