# 精简验收方案

> 语言：[English](TEST.md) | 中文

更新日期：2026-10-24。按本次用户要求，清空旧清单，重新设计覆盖 [重构计划第 10 章](architecture_zh.md) 的验收方案。**本文不授权实现、执行测试、SSH、采样或训练。** P1–P6 尚未实现；下述新增断言除明确引用已有证据外，均未编写。N1 是已实现但未验收的既有缺口。本文没有新增运行结果。

本次按用户要求纳入计划项。对应改动实现后补实现 commit 和真实测试入口，仅保留其待验收范围；通过后归档证据、删除整项。只重开受影响行为。

## 边界与共享输入

- Ubuntu 负责验收，Windows 仅作参考。在隔离目录、临时 run 内工作；冻结输入、manifest、历史证据与已安装模型只读。
- 只激活所有者或依赖发生变化的测试。每项行为改动必须有还原改动后会失败的断言。缺 fixture、测试或运行环境记 NOT RUN，不能静默跳过后算通过。
- 复用已验收检查，不重复实现。不跑阵营/规则/worker/seed 全排列，不新建语料、不做长期收敛或调参，也不因代码搬家重跑已通过的 100 局面过拟合、8-worker 压测。
- D1/N1 仅阻塞对应可选交付/native 路径。短链路只能证明接线，不能证明质量、晋升资格、收敛或棋力；生产门禁保留。

以下 fixture 只准备一份，派生文件单独存放、记录父输入 hash，不修改历史证据：

| Fixture | 最小输入 | 复用范围 |
| --- | --- | --- |
| F1：合成序列 | 两个可接纳对局族、长度不同的窗口；第三族被字节预算排除；可区分的 game/side/format ID；一个教师 choice 为 `-1` | C1–C5 |
| F2：真实记录 | `verification/model_strength_20261024_2120/` 中既有教师/on-policy 数据及匹配行为权重；每赛制取连续短片段，保留完整合法前缀，含 128 候选 | C1–C3/D1；完整长 2v2 仅供 C3/C8 |
| F3：状态/调度 | 两个权重、optimizer/RNG/cursor 不同的微型完整 checkpoint；录制的 collector/面板回复 | C4–C7/C9 |
| F4：终态 | 既有 lite 提前终态与预算截断反例 | C7/N1 |

默认体量：seed 20261024；F1 learner 窗口各 17/41 条目标，每个对照分支最多两个 epoch/四次 optimizer step，同一逻辑 batch 对比 micro=8/32。C3 可复用更多窗口，最多请求 256 条目标以暴露回填。F2 等价检查每赛制最多八条监督目标、跨两个自身回合，原始前缀完整保留。三赛制共享一个微型路由/解析参数化检查，深入故障注入用 team2v2。只有尚未解释的赛制差异才加 seed/赛制。下述编号是规格，不是已经存在的可执行测试名。

## C1：公共输入、路由与循环记忆

**状态/触发：** 既有语义已验收，新增组合断言未写。learner、loader、adapter 边界变化时激活（P1/P2/P3/P6）。

**最小 Ubuntu 操作：** F1 加 F2 短片段；交错两侧、跨自身回合、淘汰队友，在动作与确认之间插 query/bootstrap。一次参数更新前后，对照独立参考实现与改后的共享重放。

**通过条件：** 保持合法公共视图不变，毒化裁判隐藏字段，特征/预测/教师请求仍一致；诊断/终态行不进入策略输入。淘汰后 format/model 路由不变，game/side 记忆隔离。只有已确认提交的动作在既定首次写入点写记忆，query/bootstrap/no-op/重复确认不能重复写。输出**及梯度**与参考一致，权重变化后缓存失效。choice `-1` 只作历史，前缀、候选顺序及索引经过加载保持一致。

**阻塞/证据：** 阻塞受影响 BC/PPO 路径；`C1/` 保存公共字段审计、输入 ID、数值误差。所有者未变时复用 [状态/重放证据](../verification/bc_rootcause_20261023_2318/REPORT.md)。

## C2：learner 拆分、BC 目标与准确率

**状态/触发：** P1 等价检查未写；既有移动/小集拟合结果可复用。机械拆分必须保留旧采样与停止行为。

**最小 Ubuntu 操作：** 固定微型 BC/PPO 输入、model/optimizer/RNG；冻结旧实现与新实现各做一次逻辑更新。BC 包含不等长窗口、不满的最后一个 micro-batch、move/attack/recruit。独立计算加权 loss 和 correct/total。

**通过条件：** import/返回合同、loss、梯度、更新后参数/optimizer/RNG 在预先声明容差内与基线一致。窗口等权、窗口内部决策等权不受 micro 切分影响，CE/辅助/value 系数不变。准确率与 loss 使用相同合法标签/mask，按动作类型/赛制报告分子分母，不能平均 batch 百分比。训练/验证族不重叠；必需动作类型的验证目标不足 32 条不能过门。C2 保留旧 PPO 行为，新遍历/KL 要求归 C4/C5。

**阻塞/证据：** 阻塞 P1 与受影响 BC 门禁；`C2/` 保存基线身份、误差和计数。没有剩余质量问题对应的新假设，不重跑长过拟合、top-k 或容量实验。

## C3：BC 补量与有界解码

**状态/触发：** P2 未实现，预算/回填断言未写。

**最小 Ubuntu 操作：** F1 请求量高于首轮分配，回填已解码的族，第三族仍被压缩预算挡住。分别限制保留字节、可用数据、窗口数量做小反例；Ubuntu 读取一次 F2 既有长 2v2。

**通过条件：** 已接纳数据够用时补足目标，不多解码 gz、不引入被挡族。engine/source 配额、族切分、确定性目标 ID 正确，增加窗口不能虚增族数。完整原始前缀只计一次，只裁监督目标。首个超大族不能绕过上限。独立行数/字节/解码计数一致；欠量明确为 `gz_budget`、`retain_budget`、`insufficient_data` 或 `window_limit`。缺失/身份错误的索引按声明的兼容路径读原始数据或明确失败，不能悄悄读别的数据集。

**阻塞/证据：** 阻塞 P2 就绪；`C3/` 保存计数、原因和真实输入峰值 RSS/PSS。96 MiB 压缩与 768 MiB 估算保留预算不等于总 RAM 上限，不能提预算求通过。

## C4：PPO 遍历覆盖与保存边界恢复

**状态/触发：** P3 未实现，epoch-plan/cursor 断言未写，必须随本项一起完成。

**最小 Ubuntu 操作：** 不等长窗口跑两个 epoch；不中断与一次已应用 batch 后保存/恢复对照。另用 F3 在逻辑 batch 内、step 前中断。

**通过条件：** 完整 epoch 内每个目标恰好一次、无放回；窗口内时间有序，重叠历史不重复算目标。保存 rollout/model 身份、epoch 顺序、下一个未应用 batch。恢复后的未来 ID、RNG、optimizer、最终权重与相同提交边界的连续运行一致。batch 内停止丢梯度、恢复 batch 前 RNG，含 rehearsal 抽样；崩溃只恢复最后原子保存，不假装保留未存步骤。新权重下重新计算历史。拒绝混用 behavior/reward 版本或非法 bootstrap，BC rehearsal 不计作 on-policy 暴露。

**阻塞/证据：** 阻塞 P3/精确恢复声明；`C4/` 保存目标顺序与状态对照。换回旧有放回抽样或删除 cursor 后，新增断言必须失败。

## C5：逻辑 batch KL、退出与计数

**状态/触发：** P4 未实现，聚合/退出断言未写，与 P3 分开。

**最小 Ubuntu 操作：** 固定逻辑 batch，micro=8/32，含一个单独判断与总体加权判断不同的高 KL 小块。覆盖 completed/KL-stop/deadline，含零 step 与一次已应用 step。

**通过条件：** 独立计算 `exp(logp-old_logp)-1-(logp-old_logp)` 的窗口内决策平均、再窗口等权平均，与实现一致。两种切分的加权 loss/KL/梯度与停止决定在声明容差内一致。逻辑 KL 超 .02 必须在 optimizer step 前拒绝，清空整 batch 梯度。只有 step 完成才累计 committed decisions/version；所有退出都区分已检查未应用、unique IDs、effective passes、聚合 loss/KL/clip、前后 policy 身份。零 step 必须零提交；异常仍失败。clip .2、奖励与门限不变。

**阻塞/证据：** 阻塞 P4；`C5/` 保存手算聚合、前后 optimizer/参数身份。仅看到继续跑不证明更新正确。

## C6：原子检查点与显式分支续训

**状态/触发：** P5a 待实现；复用 hash 检查，缺少的操作/cursor 断言再补。

**最小 Ubuntu 操作：** F3 latest/champion；在原子替换前注入失败；检查 latest 恢复、旧 checkpoint 显式 fork、缺 epoch plan 的旧检查点。只在临时副本逐个损坏身份字段。

**通过条件：** 保存中断后旧完整 checkpoint 可读；不能拼接不同保存的 model/optimizer/RNG/cursor。latest 恢复保留 clock/plan；显式 fork 记录父 hash、新计划/seed/optimizer 选择，不改父记录。不支持的旧半更新恢复拒绝，或仅在明确支持的完整边界迁移。错误 hash/schema/rules 在更新前失败。内部恢复不套 SDK 体积限制，SDK 交付保留自己的门禁。

**阻塞/证据：** 阻塞受影响恢复操作；`C6/` 保存血缘、失败写入结果及状态身份。不重演线上事故。

## C7：阶段链路、控制器与终态真值

**状态/触发：** 既有阶段/控制器检查已验收；新组合轨迹未写，仅相关编排变化后激活。

**最小 Ubuntu 操作：** F3 驱动生产编排：BC → 两次 PPO 更新 → checkpoint/读回 → pending 更新恢复 → PPO 完成 → 提名/冻结 → 最终评估入口。三赛制做微型路由；只在变化边界注入：BC 门失败、v100 指标异常、optimizer/collector 故障、pending 方法与新阶段冲突。复用 F4 及既有奖励窗口边界断言。

**通过条件：** 自动 BC 门失败挡住 PPO，显式 force 保留 `effective=false`/原因。指标异常记录缺测、冻结 adaptive，真实开局/门禁照常；训练真故障保留 pending/failed stage，失败退出，不消费最终留出。恢复先完成 pending 原方法。已有三个窗口后仍消费每个完整 12-block 窗口，保留最新三个和余数；恢复/重复证据不能产生重复奖励事件。刷新不必改变系数。真终态与截断产生正确 bootstrap/吸收态；缺观测仍缺测，裁判事件不进策略。

**阻塞/证据：** 阻塞改动阶段路径；`C7/` 保存事件顺序、计数、clock 轨迹。未变所有者复用 [阶段链路](../verification/training_repair_20261023/REPORT.md) 与 [窗口证据](../verification/reward_window_fix_20261024_1607/REPORT.md)。以后另获执行授权，才在每个受影响赛制跑一次真实 lite Ubuntu 短链：一次 BC、两次 PPO、一次保存/恢复和最终入口；每局最多三回合，每个被调用面板一个完整评估轮换块。启动前按生产 schedule 列清实际局数，不为刷好分重跑短链。可从版本 99 覆盖 v100，但不能声称做了 100 次更新。BC 不过门若继续须显式记录 force；缩小的验证/最终面板均 inconclusive，不算通过 12/30-block 门。

## C8：存储内存与 worker 退出

**状态/触发：** 既有修复已验收；仅存储、物化、进程或队列所有权变化时激活。默认不重跑 8-worker。

**最小 Ubuntu 操作：** F2 长 2v2 经过变更后的存储/index/metrics 一次，检查成功/异常清理。生命周期变更复用一次真实 worker 丢失 spawn 探针，沿用 45 秒外层超时，只管理自身进程组。

**通过条件：** 不重新聚合完整轨迹对象/JSON；保留全部决策/前缀/精度/标签，序列化合同未变时 payload 一致。直接断言预算与临时文件清理，测瞬时峰值 RSS/PSS。worker 丢失抛原异常、终止等待 trainer、自有子进程归零，不暗中重试，不向无关进程发信号。全局 worker 上限、赛制状态隔离不变。

**阻塞/证据：** 阻塞变化的 collector/coordinator；`C8/` 保存 payload、计数、资源和子进程退出。复用 [5.40 GiB 录制压测](../verification/bc_memory_repair_20261024_1321/REPORT.md) 与 [进程池故障](../verification/bc_pool_exit_20261024/REPORT.md) 的既定范围。若内存所有权变化使压测证据失效，先声明一个有界负载/主机保留量再执行，不跑 worker 数量矩阵、不宣称永不 OOM。

## C9：最终选择与留出隔离

**状态/触发：** P5b 待实现，提名断言未写；复用既有欠面板不晋升检查。

**最小 Ubuntu 操作：** 录制 collector 提供 champion、有效的最近周期外候选、欠面板候选。先让有效候选胜出，再删除一个必需块/耗尽提名时间。跨 checkpoint 恢复重复进入最终阶段。

**通过条件：** 复用验证前匹配 model/source/rule/schedule。保留 12 个完整验证块，欠量不能晋升；提名时间不足保留声明的 champion/fallback 并记原因。完成验证记账后再保存选中 checkpoint。先冻结唯一 selected hash，再启动未触碰的 30-block holdout；holdout 不选候选、不进入训练/参考。文件/hash/`selected_kind` 一致，含 fallback。恢复不能把 pending 改成完成或重复已完成评估。缩小面板保持 inconclusive。

**阻塞/证据：** 阻塞 P5b/最终选择；`C9/` 保存 schedule、真实块数、选择原因、先冻结后 holdout 轨迹。一块不能冒充 12/30 个真实块。

## D1：可选外部推理

**状态/触发：** P6 未实现，通信原型/测试未写；仅阻塞外部交付。

**最小 Ubuntu 操作：** 先在普通原版 Wesnoth 1.18.8 add-on 证明一次请求/回复/确认提交，不假设 LuaSocket，不套裁判 RPC。再用 F2 三赛制/连续两个自身回合/128 候选/侧交错/reset。注入过期身份/索引、重复提交、pending 动作间 bootstrap、进程退出。另获授权后，最终运行一次原版合法动作/干净退出短场景。

**通过条件：** logits/value 与参考误差不超过 1e-5；确定性选择一致，近似平局差异需调查。校验 game/side/model/rule/feature/request/candidate 身份，0 基到 Lua 1 基只转换一次。线上无隐藏字段。只提交一次，bootstrap 保留 pending，reset 隔离游戏。过期/失败回复不能执行或静默换策略。每局一个常驻进程、一次模型加载，退出干净。存档/重连重建绑定版本的合法记忆或明确不支持。报告包体积、冷/热/往返耗时，不编造速度目标或 SDK 兼容结论。

**证据：** `D1/` 保存协议、数值与真实运行产物；Windows 打包/棋力另验。

## N1：可选原版终态采集（原 T6）

**状态/触发：** 已实现未验收，固定场景 helper 未写。仅阻塞新 native 终态路径，不阻塞 lite。

**最小 Ubuntu 操作/通过：** 一次原版 1.18.8 固定提前淘汰/终局，最多五回合，加既有截断反例。真实 initial/eliminated/terminal 事件保留存活侧和真实自身 HP；只有真终态可吸收到 T5/T10。故障/截断不能编终态，缺事件记缺证据，不能用零值算成功。诊断行不进 actor/BC/PPO shard 或记忆写入。`N1/` 保存原始事件、命令与身份；不跑原版规则/性能矩阵。

## 执行顺序与汇报

1. 先列变更所有者、激活项、复用证据和缺失 fixture；预先声明最大 rows/windows/steps/games 与数值容差。只实现需要的断言/helper，执行前写清真实命令。
2. 本地受影响确定性检查，再在 Ubuntu 验相关项。C4/C5/C6 共用恢复轨迹，C7/C9 共用录制编排；真实进程/游戏须按需激活并获执行授权。非 C3/C8 所需不读全量记录。
3. 相关项通过即停；修复后仅重跑失败项/变化依赖。没有指示不新增采样或正式训练。

一份新的 `verification/acceptance_<日期>/REPORT.md`，实际用到才建产物子目录：

```text
Scope：行为/commit；激活 C*/D*/N*；排除范围与原因
Identity：source/扩展构建、Ubuntu/Python/torch、rules/schema，
          input/model/optimizer hash、相关 seed/plan/cursor
Commands：解释器、cwd、参数、退出码、耗时
Results：编号 | PASS / FAIL / NOT RUN / REUSED | 断言/计数 | 产物
Reuse：原报告 + 相关身份匹配；复用不是本轮新跑
Failure：首个不同输入/step、预期/实际、复现方式
Resources：rows/windows/families/decodes/steps/children；相关时峰值 RSS/PSS
Gate：可进入具名下一阶段 / 阻塞；缩小面板 inconclusive
Limits：未写测试、缺失输入/环境、未证明的质量/棋力
```

证据不含凭据。断言失败、必需观测缺失、静默跳过或身份不匹配，阻塞对应验收。纯文档改动只检查文档/链接/diff。本文没有运行结果。
