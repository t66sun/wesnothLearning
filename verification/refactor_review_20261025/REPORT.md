# 重构独立验收复核 — 2026-10-25

**结论：当前不能完整验收，也不建议直接启动正式训练。** 已有 Ubuntu 最小检查可复用，但本次独立复核复现了两个交付阻塞和四个恢复/兼容缺口。这里只记录问题，没有修复生产代码。

## 身份、范围与已有证据

- 审查基线：`768db294ced6c1b0b10aa46ccb08da489f85a7d8`（计划交付）。被审查 HEAD：`642a890f552d5daafe42f850c03a87ff984ea0ae`。
- 对照：`git diff 768db29...642a890`、`git log 768db29..642a890 --oneline`，规格为基线的 architecture 第 10 章、TEST，以及确定性战斗需求；标准为 AGENTS.md。
- 复用 [原验收报告](../refactor_acceptance_20261025/REPORT.md) 及其原始日志：Ubuntu Python 273 项、阶段 17 项、Rust 13 项通过，面板源码 `e1181ea`；L1 源码 `34cbe94`。这些是原报告记录的结果，不是本轮重跑。
- 本轮 Windows 本地参考环境完成静态审查和微型 Python 复现。没有 SSH、修改服务器、启动游戏/语料采集/正式训练，也没有重跑上述已通过大套件。PPO 复现仅用既有合成 fixture 做两个微型 optimizer step。
- 本地 `_engine_lite` 仍为 `lite-0.1 / xoshiro256++-1`；未重编，也没有用它声称新 `lite-0.2` 通过。新引擎算式/状态结算的观察依据是源码及既有 Ubuntu 证据。
- 源文件长度检查仅发现两份既有 grandfathered 测试仍为 1804/1050 行；本轮没有修改它们，不把局部 fixture 更新直接定性为新增超限文件。

## Spec 轴：计划实现缺口

### V1 [P1] 有冠军时，最新候选没有验证文件会让最终评估崩溃

- 位置：`learning/experiment.py:568–573`，尤其直接读 `validation/v{candidate_version}.json` 的第 571 行。
- 计划要求：10.7/P5b 的最近完整 checkpoint 周期外提名；先做完整验证，证据/时间不足则保留冠军，冻结后才进入 holdout。
- 最小复现：保留已验证 v100 冠军，最新 `last_ppo` 为 v143，只提供 v100 的验证文件。调用真实 `_select_final()`，得到 `FileNotFoundError: v000143.json`，collector/validate_model 调用均为 0。
- 影响：在验证周期之间结束训练是正常情况；这个分支无法进入最终评估。L1 的 `no retained champion` fallback 绕过了本分支，所以其成功不证明 P5b 完成。
- 最小修复验收：同一 fixture 必须先提名/验证最新候选，或在明确不具备提名条件时有理由地保留冠军；欠面板不能晋升；已有选中 hash 的恢复不能重跑 holdout。复用 C9，不再新跑整轮训练。

### V3 [P2] PPO 恢复后漏记此前已经提交的决策

- 位置：`learning/ppo.py:83–88,97–105,178–179` 与 `learning/experiment.py:338–351`。
- 计划要求：10.6/C4/C5 的已应用/仅访问工作真实统计，恢复后不丢计数。
- 最小复现：既有合成 fixture 共 11 个目标，第一段提交 11；保存 cursor 后继续第二个 epoch，返回 `updates=2, decisions_seen=22, committed_decisions=11`。`finish_train` 在 interrupted 时不结算，最后却只将 committed 加入全局计数，漏掉第一段 11。
- 影响：恢复后的训练暴露、吞吐等判断不可信；这不等于已经证明权重恢复不一致。
- 最小修复验收：同一两段 fixture 的最终运行级 optimizer/decision/pass 计数等于不中断对照，边界重复恢复不能重复加；不扩大真实对局量。

### V4 [P2] BC 在 batch 内截止，丢梯度却没有恢复采样 RNG

- 位置：`learning/bc.py:31–40,58–60`。
- 计划要求：10.7 的逻辑 batch 中途取消恢复 batch 前采样 RNG、从保存边界继续。
- 最小复现：在抽样前后分别给时钟 0/2，deadline=1；返回 interrupted、零更新、权重不变，但 Python RNG 已前进。
- 影响：保存后恢复将走另一组 BC 样本，不能声称该路径与不中断未来完全相同。此行为承自拆分前逻辑，属于本次计划要求未补齐，并非把原有行为全部归为重构新回归。
- 最小修复验收：取消时梯度/权重/optimizer 不变且恢复采样 RNG；随后恢复的样本 ID、参数与连续对照一致，用同一小 fixture 即可。

### V5 [P2] rollout 身份摘要没有包含目标身份或训练内容

- 位置：`learning/updates.py:44–59`；调用方 `learning/experiment.py:324–327`。
- 计划要求：Batch/EpochPlan、C4/C6 的冻结输入身份及变更拒绝。
- 最小复现：函数虽然按 game/side/turn/decision 排序，实际只 hash 少量版本/来源元数据。改变 game ID、动作/log-probability/reward 可得到同一摘要；补充探针还确认两条分别通过 `validate_record` 的 policy 记录，game ID/old logp/reward 不同仍摘要相同。
- 影响：`scheduled rollout changed` 检查不能识别这类错换输入。尚未观察到线上冻结语料实际被篡改；这是恢复合同中的确定性检测缺口。
- 最小修复验收：绑定原始输入/目标 ID、影响训练的内容及版本；逐个改变这些字段必须在更新前拒绝，原输入重读/恢复保持一致。复用 C4/C6，不重编码全语料。

## Standards 轴：身份约束和实际交付路径未闭合

### V2 [P1] 最后/最佳 checkpoint 遗漏身份，正常选中模型无法导出

- 位置：`learning/experiment.py:369,422–424` 对比 `:222–223`；拒绝点 `learning/export.py:92–95`。
- 合同：AGENTS 规则 4 的行为断言、规则 5 的实测验收；architecture 10.13 要求 checkpoint/export 保留 combat/teacher 身份。
- 最小复现：用真实 `finish_train()` 和真实 checkpoint writer、微型模型，替换 collector/learner 输入以隔离保存逻辑。生成的 `last_ppo.pt` 缺少全部七项 engine/combat/teacher 身份。真实 `export_checkpoints()` 在第一个格式立即报 `checkpoint lacks combat or teacher profile identity`。best 保存同样遗漏，复制为 selected 不会补齐。
- 影响：默认最终产物不能走新正式导出入口；latest 带身份不能代替实际被选中的 last/best。
- 最小修复验收：走实际 last/best → selected → export 身份检查，验证所有格式及规则/教师一致；保留错误身份拒绝，不删除导出门禁。先复用少量公共输入检查导出接线，无需训练新模型。

### V6 [P2，native 路径] 原版 Astra 数据被强制当成确定性 lite 教师

- 位置：`learning/data.py:61–63`；原版生产路径 `learning/sample.py:89–100`。
- 合同：规则 4 的受影响行为断言；计划明确保留 native 1.18.8 原规则，并隔离两种规则身份。
- 最小复现：合法 Astra row 改为原版 engine/rng/combat 身份、按原版生产路径不提供 lite teacher_profile；`validate_record` 无条件要求 `expected_damage_v1` 而报错。
- 影响：原版教师采样/非零 native BC 配额失效；不阻塞默认零 native 的纯 lite 路径。
- 最小修复验收：一条合法 native Astra、一条合法 deterministic-lite Astra 均按对应身份接受，跨规则混入拒绝；纯记录级检查，无需启动原版游戏。

两轴没有把同一缺陷重复计数：Spec 4 项，Standards 2 项；各轴最严重项为 V1、V2。这里列的是可执行反例，不是要求另建泛化框架或全面重写。

## 执行记录

从仓库根目录执行，使用本地 `.venv/Scripts/python.exe`：

```powershell
$env:PYTHONPATH=(Get-Location).Path
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
$env:OPENBLAS_NUM_THREADS='1'
.venv/Scripts/python.exe -B verification/refactor_review_20261025/reproduce_gaps.py
```

- 成功复现日志：[reproduce_with_pythonpath.log](reproduce_with_pythonpath.log)，退出码 0，仅表示六个缺陷均按预期被复现，**不表示验收通过**。脚本为 [reproduce_gaps.py](reproduce_gaps.py)，需要真实 fixture/torch，不依赖 Rust 扩展。
- 首次脚本按文件路径启动遗漏 PYTHONPATH，import `learning` 失败；保留原始 [reproduce.log](reproduce.log)。补正确仓库路径后执行上述命令，没有将失败记录覆盖为成功。
- V5 的合法 policy 记录补充验证见 [identity_valid_records.log](identity_valid_records.log)；两条记录分别通过 `validate_record` 后摘要仍相同。
- 所有临时 checkpoint/输入在系统临时目录，自动删除；历史验证证据、data、run、安装模型未改。

## 范围结论与下一步

确定性单击公式、75% 减速伤害、6 点毒伤的实现方向与要求一致；已有 Ubuntu Rust/接口检查只在其记录范围内复用。R3 仅 value-level 六例，完整合法棋盘上的教师 query/ranking 轨迹和同规则教师棋力仍未验证。P6/D1 未实现，N1 原版终态路径待验，均不作为默认 lite 的额外交付前置条件。

L1 只覆盖 duel、无冠军 fallback，且没有与不中断的同未来对照；不能替代三赛制关键路径或 V1/V2。其已观察到的 BC→PPO→恢复→final 事实保留，不抹掉真实成功部分，也不扩成全部验收通过。

先修 V1/V2；合并修复时补各自会在撤销修复后失败的最小断言。V3–V5 补恢复合同，V6 补 native 兼容。只在对应代码变化后跑相关本地/Ubuntu 最小项，复用原通过证据；不重跑 273 项矩阵、不增加训练局数、不以调奖励掩盖接线问题。完整通过前不宣称重构全部验收完成。
