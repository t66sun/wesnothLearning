# 精简验收方案

> 语言：[English](TEST.md) | 中文

更新日期：2026-10-25。V1–V6 六项已复现缺陷已修复，12 项 Ubuntu 专项检查通过；命令、身份、失败和限制见[修复验收报告](../verification/refactor_repairs_20261025/REPORT.md)。已完成修复项和 C9 已归档并从下文删除；其余条目只保留原有待验收或测试未写范围。受限通过不等于整体验收或棋力证明。P6 未实现，N1 待验收。

这里只保留剩余验收和用户明确要求的前瞻项，复用有效证据；本计划不授权重跑全套、新对局或正式训练。报告中的 SDK 包大小尝试仍为失败，原门禁未改，不属于这六项修复。

最终预算预留 B1 的 6 项 Ubuntu 检查已通过，归档于[启动报告](../verification/final_review_lite30h_20261025/REPORT.md)，已删除整项。

PPO 重构 R1 已通过 27 项 Ubuntu 专项检查，还原/恢复证据归档于 [R1 报告](../verification/ppo_refactor_r1_20261027/REPORT.md)。R2 已通过 20 项专项检查及 1 项 FFA4/2v2 更新检查，还原/恢复证据见 [R2 报告](../verification/ppo_refactor_r2_20261027/REPORT.md)。不再保留 R1/R2 验收条目。R3 已通过 14 项 Ubuntu 专项检查，见 [R3 报告](../verification/ppo_refactor_r3_20261027/REPORT.md)，无待验收条目；R4 已通过 30 项 Ubuntu 专项检查，见 [R4 报告](../verification/ppo_refactor_r4_20261027/REPORT.md)，无待验收条目；R5 已通过 23 项 Ubuntu 专项检查，见 [R5 报告](../verification/ppo_refactor_r5_20261027/REPORT.md)，无待验收条目；R6 通过 37 项 Ubuntu 合同检查及 421 行逐位算术对照，本地旧夹具/扩展未通过项见 [R6 报告](../verification/ppo_refactor_r6_20261027/REPORT.md)；R7 已通过 39 项 Ubuntu 身份/接线检查及 Lua 语法检查，见 [R7 报告](../verification/ppo_refactor_r7_20261027/REPORT.md)，不代表原版采集能力；R8 已按能力证据验收：19 项专项 Ubuntu 检查与受控三局原版 fixture 通过，见[复跑报告](../verification/ppo_refactor_r8_20261028/RERUN.md)；R9/R10 尚未实现，见[重构计划](ppo_refactor_plan_zh.md)；N1 与既有数值/打包失败保留原范围和门禁。

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
| F5：确定性战斗 | 微型手算战斗/状态初态；六个公共战术局面；新 profile 的 F3 状态/调度 | R1–R3/C7；不新建语料，不把旧随机 returns 改标签 |

默认体量：seed 20261024；F1 learner 窗口各 17/41 条目标，每个对照分支最多两个 epoch/四次 optimizer step，同一逻辑 batch 对比 micro=8/32。C3 可复用更多窗口，最多请求 256 条目标以暴露回填。F2 等价检查每赛制最多八条监督目标、跨两个自身回合，原始前缀完整保留。三赛制共享一个微型路由/解析参数化检查，深入故障注入用 team2v2。只有尚未解释的赛制差异才加 seed/赛制。下述编号是规格，不是已经存在的可执行测试名。

R1–R3 仅由 P7 激活。C1–C9 未变部分复用证据，刷新规则相关特征/fixture 及受影响 C1/C6/C7/C9 路径，不重跑全套。F2 旧公共上下文可重算，旧转移/教师标签/log-probabilities/returns 不能作为新规则 BC/PPO 输入。原数值拆分等价检查仍绑定原规则。

## C1：公共输入、路由与循环记忆

**状态/触发：** 既有语义已验收，新增组合断言未写。learner、loader、adapter 边界变化时激活（P1/P2/P3/P6）。

**最小 Ubuntu 操作：** F1 加 F2 短片段；交错两侧、跨自身回合、淘汰队友，在动作与确认之间插 query/bootstrap。一次参数更新前后，对照独立参考实现与改后的共享重放。

**通过条件：** 保持合法公共视图不变，毒化裁判隐藏字段，特征/预测/教师请求仍一致；诊断/终态行不进入策略输入。淘汰后 format/model 路由不变，game/side 记忆隔离。只有已确认提交的动作在既定首次写入点写记忆，query/bootstrap/no-op/重复确认不能重复写。输出**及梯度**与参考一致，权重变化后缓存失效。choice `-1` 只作历史，前缀、候选顺序及索引经过加载保持一致。

**阻塞/证据：** 阻塞受影响 BC/PPO 路径；`C1/` 保存公共字段审计、输入 ID、数值误差。所有者未变时复用 [状态/重放证据](../verification/bc_rootcause_20261023_2318/REPORT.md)。

## C2：learner 拆分、BC 目标与准确率

**状态/触发：** P1 已实现，报告四项标量/导入检查；不能仅从 loss 推断完整梯度/optimizer/RNG 等价，复用既有小集拟合证据。

**最小 Ubuntu 操作：** 固定微型 BC/PPO 输入、model/optimizer/RNG；冻结旧实现与新实现各做一次逻辑更新。BC 包含不等长窗口、不满的最后一个 micro-batch、move/attack/recruit。独立计算加权 loss 和 correct/total。

**通过条件：** import/返回合同、loss、梯度、更新后参数/optimizer/RNG 在预先声明容差内与基线一致。窗口等权、窗口内部决策等权不受 micro 切分影响，CE/辅助/value 系数不变。准确率与 loss 使用相同合法标签/mask，按动作类型/赛制报告分子分母，不能平均 batch 百分比。训练/验证族不重叠；必需动作类型的验证目标不足 32 条不能过门。C2 保留旧 PPO 行为，新遍历/KL 要求归 C4/C5。

**阻塞/证据：** 阻塞 P1 与受影响 BC 门禁；`C2/` 保存基线身份、误差和计数。没有剩余质量问题对应的新假设，不重跑长过拟合、top-k 或容量实验。

## C3：BC 补量与有界解码

**状态/触发：** P2 已实现，空读取修复后报告九项 loader 检查；超出这些断言的真实记录峰值内存/完整前缀证据尚不能宣称。

**最小 Ubuntu 操作：** F1 请求量高于首轮分配，回填已解码的族，第三族仍被压缩预算挡住。分别限制保留字节、可用数据、窗口数量做小反例；Ubuntu 读取一次 F2 既有长 2v2。

**通过条件：** 已接纳数据够用时补足目标，不多解码 gz、不引入被挡族。engine/source 配额、族切分、确定性目标 ID 正确，增加窗口不能虚增族数。完整原始前缀只计一次，只裁监督目标。首个超大族不能绕过上限。独立行数/字节/解码计数一致；欠量明确为 `gz_budget`、`retain_budget`、`insufficient_data` 或 `window_limit`。缺失/身份错误的索引按声明的兼容路径读原始数据或明确失败，不能悄悄读别的数据集。

**阻塞/证据：** 阻塞 P2 就绪；`C3/` 保存计数、原因和真实输入峰值 RSS/PSS。96 MiB 压缩与 768 MiB 估算保留预算不等于总 RAM 上限，不能提预算求通过。

## C4：PPO 遍历覆盖与保存边界恢复

**状态/触发：** P3 已实现。V3/V5 的恢复、计数和内容身份专项 Ubuntu 断言已通过并归档；下文仅保留超出微型 fixture 的完整重放/梯度合同。

**最小 Ubuntu 操作：** 不等长窗口跑两个 epoch；不中断与一次已应用 batch 后保存/恢复对照。另用 F3 在逻辑 batch 内、step 前中断。

**通过条件：** 完整 epoch 内每个目标恰好一次、无放回；窗口内时间有序，重叠历史不重复算目标。保存 rollout/model 身份、epoch 顺序、下一个未应用 batch。恢复后的未来 ID、RNG、optimizer、最终权重与相同提交边界的连续运行一致。batch 内停止丢梯度、恢复 batch 前 RNG，含 rehearsal 抽样；崩溃只恢复最后原子保存，不假装保留未存步骤。新权重下重新计算历史。拒绝混用 behavior/reward 版本或非法 bootstrap，BC rehearsal 不计作 on-policy 暴露。

**阻塞/证据：** 阻塞 P3/精确恢复声明；`C4/` 保存目标顺序与状态对照。换回旧有放回抽样或删除 cursor 后，新增断言必须失败。

## C5：逻辑 batch KL、退出与计数

**状态/触发：** P4 已实现，复用逻辑 KL/退出证据；V3 累计恢复计数已通过专项 Ubuntu 验收。下文只保留这些 fixture 尚未证明的更广数值/梯度断言。

**最小 Ubuntu 操作：** 固定逻辑 batch，micro=8/32，含一个单独判断与总体加权判断不同的高 KL 小块。覆盖 completed/KL-stop/deadline，含零 step 与一次已应用 step。

**通过条件：** 独立计算 `exp(logp-old_logp)-1-(logp-old_logp)` 的窗口内决策平均、再窗口等权平均，与实现一致。两种切分的加权 loss/KL/梯度与停止决定在声明容差内一致。逻辑 KL 超 .02 必须在 optimizer step 前拒绝，清空整 batch 梯度。只有 step 完成才累计 committed decisions/version；所有退出都区分已检查未应用、unique IDs、effective passes、聚合 loss/KL/clip、前后 policy 身份。零 step 必须零提交；异常仍失败。clip .2、奖励与门限不变。

**阻塞/证据：** 阻塞 P4；`C5/` 保存手算聚合、前后 optimizer/参数身份。仅看到继续跑不证明更新正确。

## C6：原子检查点与显式分支续训

**状态/触发：** P5a 已实现；V2/V4/V5 的身份、BC 取消 RNG、变更输入拒绝已通过 Ubuntu 专项检查。复用序列化/分支证据，不将下文更广的旧格式/fork 合同一并声称完成。

**最小 Ubuntu 操作：** F3 latest/champion；在原子替换前注入失败；检查 latest 恢复、旧 checkpoint 显式 fork、缺 epoch plan 的旧检查点。只在临时副本逐个损坏身份字段。

**通过条件：** 保存中断后旧完整 checkpoint 可读；不能拼接不同保存的 model/optimizer/RNG/cursor。latest 恢复保留 clock/plan；显式 fork 记录父 hash、新计划/seed/optimizer 选择，不改父记录。不支持的旧半更新恢复拒绝，或仅在明确支持的完整边界迁移。错误 hash/schema/rules 在更新前失败。内部恢复不套 SDK 体积限制，SDK 交付保留自己的门禁。

**阻塞/证据：** 阻塞受影响恢复操作；`C6/` 保存血缘、失败写入结果及状态身份。不重演线上事故。

## C7：阶段链路、控制器与终态真值

**状态/触发：** 复用 17 项 Ubuntu 阶段检查和已记录 duel 短链；V1 已补三赛制录制日程提名与重复最终入口证据。新的三赛制真实阶段链仍未运行，本计划不授权执行。

**最小 Ubuntu 操作：** F3 驱动生产编排：BC → 两次 PPO 更新 → checkpoint/读回 → pending 更新恢复 → PPO 完成 → 提名/冻结 → 最终评估入口。三赛制做微型路由；只在变化边界注入：BC 门失败、v100 指标异常、optimizer/collector 故障、pending 方法与新阶段冲突。复用 F4 及既有奖励窗口边界断言。

**通过条件：** 自动 BC 门失败挡住 PPO，显式 force 保留 `effective=false`/原因。指标异常记录缺测、冻结 adaptive，真实开局/门禁照常；训练真故障保留 pending/failed stage，失败退出，不消费最终留出。恢复先完成 pending 原方法。已有三个窗口后仍消费每个完整 12-block 窗口，保留最新三个和余数；恢复/重复证据不能产生重复奖励事件。刷新不必改变系数。真终态与截断产生正确 bootstrap/吸收态；缺观测仍缺测，裁判事件不进策略。

**阻塞/证据：** 阻塞改动阶段路径；`C7/` 保存事件顺序、计数、clock 轨迹。未变所有者复用 [阶段链路](../verification/training_repair_20261023/REPORT.md) 与 [窗口证据](../verification/reward_window_fix_20261024_1607/REPORT.md)。以后另获执行授权，才在每个受影响赛制跑一次真实 lite Ubuntu 短链：一次 BC、两次 PPO、一次保存/恢复和最终入口；每局最多三回合，每个被调用面板一个完整评估轮换块。启动前按生产 schedule 列清实际局数，不为刷好分重跑短链。可从版本 99 覆盖 v100，但不能声称做了 100 次更新。BC 不过门若继续须显式记录 force；缩小的验证/最终面板均 inconclusive，不算通过 12/30-block 门。

## C8：存储内存与 worker 退出

**状态/触发：** 既有修复已验收；仅存储、物化、进程或队列所有权变化时激活。默认不重跑 8-worker。

**最小 Ubuntu 操作：** F2 长 2v2 经过变更后的存储/index/metrics 一次，检查成功/异常清理。生命周期变更复用一次真实 worker 丢失 spawn 探针，沿用 45 秒外层超时，只管理自身进程组。

**通过条件：** 不重新聚合完整轨迹对象/JSON；保留全部决策/前缀/精度/标签，序列化合同未变时 payload 一致。直接断言预算与临时文件清理，测瞬时峰值 RSS/PSS。worker 丢失抛原异常、终止等待 trainer、自有子进程归零，不暗中重试，不向无关进程发信号。全局 worker 上限、赛制状态隔离不变。

**阻塞/证据：** 阻塞变化的 collector/coordinator；`C8/` 保存 payload、计数、资源和子进程退出。复用 [5.40 GiB 录制压测](../verification/bc_memory_repair_20261024_1321/REPORT.md) 与 [进程池故障](../verification/bc_pool_exit_20261024/REPORT.md) 的既定范围。若内存所有权变化使压测证据失效，先声明一个有界负载/主机保留量再执行，不跑 worker 数量矩阵、不宣称永不 OOM。

## R1：确定性逐击伤害与状态削弱

**状态/触发：** P7a 已实现，原 Ubuntu 面板中 13 项 Rust 和相关接口检查通过；复用受限证据，完整新 profile 就绪仍依赖 R2/R3。

**最小 Ubuntu 操作：** 一张小表经过真实 resolver，加三个短状态/时序脚本。不采游戏语料，不用概率置信采样。预期值由独立整数公式手算，不调用生产 helper 当答案。

| 输入/序列 | 必须结果 |
| --- | --- |
| 修正后伤害 10，原命中率 60% | 每个可执行单击 `ceil(10*.6*1.1)=7`，保留多刀，不合并整次攻击 |
| 伤害/概率边界 | 零基础伤害或 0% 命中扣零；0% 不触发命中特效；10 配 100% 为 11；1 配 1% 为 1，明确向上取整偏差 |
| 减速出手，伤害 10，命中率 60% | 先 `ceil(10*.75)=8`，再 `ceil(8*.6*1.1)=6`；不能沿用半伤或只在最后取整 |
| 地形/特效/修正 | 抗性/时段一例，加魔法/精准/降低命中各代表例，得到手算 `D,p`；概率与上调只算一次，攻击/反击一致 |
| 先攻/死亡/吸血 | 保留顺序/刀数，死亡后不反击；吸血按封顶后的真实扣血；新减速影响后续反击 |
| 中毒 10 HP，无休息/治疗 | 自身回合依次变 4、1 HP，毒不致死；其他 side 回合不结算；重复中毒不叠加 |
| 状态控制 | 除毒伤 6 外，免疫/治毒/抑制/休息优先级不变；减速保持地形移动代价翻倍/持续时间，不额外减半移动预算 |

**通过条件：** 整数/状态断言全部成立；检查新 runtime 确认旧 `Random`、战斗/招募 RNG 占位和命中注入已删除/明确退役，不是仅测试时绕过。确定命中的 poison/slow 不另掷骰，保留零伤害武器的命中特效资格。一个聚焦击杀后处理例覆盖 XP/plague/feeding 接线，不铺全特效矩阵。撤销新公式/减速/中毒常量后，对应断言必须失败。

**证据：** `verification/acceptance_<日期>/R1/` 保存手算表、状态轨迹、engine/profile/source 身份；原版随机分布不是有意改规则的答案。

## R2：精确公开预测、身份隔离与阶段链路

**状态/触发：** 复用未变更 P7a 预测/引擎/教师证据；V2/V5/V6 的身份、导出接线、native/lite 记录兼容已通过专项 Ubuntu 验收，不据此宣称下文完整真实对局阶段/预测合同已通过。

**最小 Ubuntu 操作：** 复用三个 R1 状态（普通/减速/中毒），在受控全可见初态先预测再执行，加一个隐藏上下文反例。初态/动作脚本固定，仅 seed 取 0/1/713；对照直接 step 与 snapshot/restore/step。若保留旧参数，对照 forecast 的 `samples=1/128`。三赛制参数化路由，然后共用 C7 新 profile 的 BC → 两次 PPO → 恢复 → 最终入口轨迹，不另跑第二条链。

**通过断言：**

- 相同公共上下文的预测精确给出 HP/状态/击杀，单点 `hp_chance` 和为 1，有效 samples=1，每次未缓存 forecast 只调用一次 resolver。查询不推进状态、不改 revision/记忆或剩余非战斗 RNG。假设攻击位置影响有关地形/修正。只改变隐藏字段不能影响预测/候选/Astra；隐藏战斗因素可以影响随后真实执行，因此预测/执行相等仅在公共上下文完整时要求。
- seed/旧命中列表不影响固定状态战斗；旧注入入口不存在或明确拒绝。新 snapshot 往返结果一致；旧随机快照按身份拒绝，不丢掉 RNG 后冒充恢复。
- 候选特征、击杀/状态评分、Astra `simulate_combat` 与实际 resolver 用同一新 profile，无二次概率/1.10、遗留 8 点毒或半伤假设。Native 调用方继续原规则并声明身份。
- 新 profile/hash、engine/snapshot 身份、teacher hash 贯穿 jobs、manifest、data/index/cache、checkpoint、panel、export；仅 catalog hash/schema 一致不能接受旧动力学。旧/缺失/混合 profile 临时副本在更新前失败。旧权重需显式新 run 初始化，旧 optimizer/rollout/clock 不得静默续用，原记录字节不变。
- 共享 C7 轨迹在三赛制保持新规则 data/model/teacher 身份。质量/force 来源、bootstrap、controller、最终选拔、留出隔离保留。短轨迹棋力仍 inconclusive。记录 resolver 调用次数、同输入 forecast 时间，不猜加速倍数、不重跑压力矩阵。

**证据：** `R2/` 保存预测/执行/公开输入差异、构建/profile 传播、拒绝混用日志及唯一 C7 轨迹链接。特征调用方变化若影响 D1，待实现后只重验其数值片段，不跑无关通信矩阵。

## R3：Astra 适配与独立棋力证据

**状态/触发：** P7b 已实现，六个 value-level 局面已有检查；真实合法棋盘教师 query/排序、配对棋力仍未跑。

**最小 Ubuntu 操作：** 六个公共局面，独立规定可接受最优动作/排序：(1) 确定击杀与不致死；(2) 先攻/反击生存；(3) 原命中率不同的两种武器；(4) 含移动限制的减速价值；(5) 每 tick 为 6 的毒价值；(6) 免疫/即将治毒时普通攻击更优。每例两个有意义选项，固定预算、确定性 tie-break。教师启发式改动至少有一个旧教师失败的反例。复用三赛制路由与 C1 查询/提交隔离。

**通过条件：** 教师查询合法、公共、只读，无执行/RNG/记忆泄漏；预测/排序符合新伤害/减速/中毒合同。不自动加教师预算，不顺带重写招募/团队逻辑。记录 teacher source/config/parent hash 与 profile，原冻结包不动，派生新版归档。战术与棋力分开汇报。

**棋力，另获游戏授权才做：** 冻结未适配 Astra 与适配 Astra 在**相同新规则**下，固定配对初始地图/阵营/角色，每赛制一个已有完整轮换块做有界 smoke，先声明真实局数和回合上限。角色/schedule 匹配时复用新 profile 的 C7 游戏；截断/欠面板仍 inconclusive。它只发现明显战术/运行退化，不能证明统计不退化。宣称棋力保持/增强，必须在冻结、留出的验证 schedule 上通过不变的完整 12-block 验证/冠军合同，不在该面板上调参。结论不确定或失败就保留状态、修正假设，不能加 seed 直到赢。正式最终/原版棋力保留独立 30-block 门；确定性 lite 与原版或旧规则历史得分不能证明等强。

**证据/阻塞：** `R3/` 保存六个决策/排序、预算、teacher/profile 身份，分别标注 tactical/smoke/full-validation 结果。最小就绪可支持明确授权的新规则训练，但完整匹配证据出现前，architecture 必须保留教师棋力未验证。本计划不触发采样。

## D1：可选外部推理

**状态/触发：** P6 未实现，通信原型/测试未写；仅阻塞外部交付。

**最小 Ubuntu 操作：** 先在普通原版 Wesnoth 1.18.8 add-on 证明一次请求/回复/确认提交，不假设 LuaSocket，不套裁判 RPC。再用 F2 三赛制/连续两个自身回合/128 候选/侧交错/reset。注入过期身份/索引、重复提交、pending 动作间 bootstrap、进程退出。另获授权后，最终运行一次原版合法动作/干净退出短场景。

**通过条件：** logits/value 与参考误差不超过 1e-5；确定性选择一致，近似平局差异需调查。校验 game/side/model/rule/feature/request/candidate 身份，0 基到 Lua 1 基只转换一次。线上无隐藏字段。只提交一次，bootstrap 保留 pending，reset 隔离游戏。过期/失败回复不能执行或静默换策略。每局一个常驻进程、一次模型加载，退出干净。存档/重连重建绑定版本的合法记忆或明确不支持。报告包体积、冷/热/往返耗时，不编造速度目标或 SDK 兼容结论。

**证据：** `D1/` 保存协议、数值与真实运行产物；Windows 打包/棋力另验。

## N1：可选原版终态采集（原 T6）

**状态/触发：** 已实现未验收，固定场景 helper 未写。仅阻塞新 native 终态路径，不阻塞 lite。

**最小 Ubuntu 操作/通过：** 一次原版 1.18.8 固定提前淘汰/终局，最多五回合，加既有截断反例。真实 initial/eliminated/terminal 事件保留存活侧和真实自身 HP；只有真终态可吸收到 T5/T10。故障/截断不能编终态，缺事件记缺证据，不能用零值算成功。诊断行不进 actor/BC/PPO shard 或记忆写入。`N1/` 保存原始事件、命令与身份；不跑原版规则/性能矩阵。

## L1——重构后的缩减全回环运行

**状态/触发：** 原报告记录 duel 的 BC→PPO→恢复→final fallback；缺同未来连续对照及运行中定时 tick，不证明有冠军/全赛制覆盖或整体验收。

**最小 Ubuntu 操作：** 在隔离源码树上冻结一份 lite 配置，采用能覆盖 BC、至少两次实际提交的 PPO 更新、一次从已提交 batch 检查点停止/恢复、以及最终评估入口的最小赛制/局数面板。启动前记录准确局数、seed、manifest 与检查点身份。每 30 分钟查看运行状态/日志，保留异常；运行期间不增加局数、不放宽门禁、不改冻结证据。

**通过条件：** 运行进入最终评估；两次 PPO 更新均提交；在身份匹配时，从保存边界恢复得到与未中断时一致的后续；记录入选检查点与导出；所有停止原因如实报告。缩减面板的局限标记为棋力 inconclusive，失败仍记失败。

**证据/阻塞：** 新的按日期命名 `verification/<run>_<date>/REPORT.md`，含命令、计数、身份、检查点/恢复轨迹、最终评估入口与资源读数。本项本身不授权新增采集或正式训练。

## PKG1：Ubuntu 24.04 训练归档包

**状态/触发：** 构建器与静态校验器已实现，并于 2026-10-25 在本地测试：`python -m learning bundle --help` 与 `python -m learning verify-bundle --help` 退出码 0，16 项构建器/校验器检查与 11 项 setup/train 脚本检查通过。尚未构建任何归档包，也没有干净 Ubuntu 24.04 机器解压、安装或启动过，这些步骤均为 NOT RUN。在把归档包交给没有本工作副本的机器之前启用；payload 清单、排除规则、manifest、`SHA256SUMS`、`setup.sh` 或 `train.sh` 变更后也需重跑。

**最小 Ubuntu 操作：** 在本工作副本上用 `python -m learning bundle --output tmp/bundle_<日期>/WesnothLearning-training.tar.gz --created-at <固定 ISO8601>` 构建一个归档包并记录 sha256；只有确实要打包 Linux wheel 时才传 `--wheel dist/<manylinux x86_64>.whl`，此时给 `verify-bundle` 加 `--require-wheel`。用 `python -m learning verify-bundle <archive>` 校验，并按 [bundle_zh.md](bundle_zh.md) 核对成员清单、权限位与排除项。把归档包复制到干净 Ubuntu 24.04 x86_64 机器解压，运行 `./setup.sh --preflight`（退出 0，不写入）。在副本中翻转一个 payload 字节，确认 preflight 退出非 0。然后 `./setup.sh --device cpu` 必须退出 0 并打印规则/引擎身份检查；`./train.sh --help` 前后对比目录树；在没有 `.runtime/environment.sh` 的副本中运行 `./train.sh` 必须拒绝。最后确认没有 `runs/` 目录或运行日志。

**通过条件：** 记录的归档包 sha256 与校验时读到的一致；preflight 接受完好副本并拒绝被篡改副本；归档包内不含 `.git`、虚拟环境、运行状态、验证证据、交付产物、历史 `1.18.8` 包或原始回放转储。安装在同一干净机器上退出 0，写出 `.runtime/environment.sh` 与 `.cache/setup.log`，其身份检查与 `rules.json`、`catalog-summary.json` 及 `_engine_lite` 一致。`--help` 不创建任何内容，`train.sh` 在未安装时拒绝而非开工。观察到的失败如实记为失败，不得缩小成通过。

**证据：** `verification/training_bundle_ubuntu24_<日期>/REPORT.md`，含归档包路径/sha256/manifest 身份、每条命令与退出码、完好与篡改两次 preflight 结果、身份检查输出、`--help` 前后目录树差异、拒绝输出与安装日志。缺少该报告时本项为 NOT RUN。

**训练阻塞：** 本项只证明安装可用，不授权采样、启动训练、收敛结论或棋力结论；启动实验仍需用户明确指令，安装完成或解压出归档包都不构成该指令。

## 执行顺序与汇报

1. 先列变更所有者、激活项、复用证据和缺失 fixture；预先声明最大 rows/windows/steps/games 与数值容差。只实现需要的断言/helper，执行前写清真实命令。
   P7 按 R1 → R2 → R3 战术顺序，共用 C7；真实游戏 smoke/棋力面板另获执行授权。新规则证据与旧随机规则验收分开归档。
2. 本地受影响确定性检查，再在 Ubuntu 验相关项。C4/C5/C6 共用恢复轨迹，C7/C9 共用录制编排；真实进程/游戏须按需激活并获执行授权。非 C3/C8 所需不读全量记录。
3. 相关项通过即停；修复后仅重跑失败项/变化依赖。没有指示不新增采样或正式训练。

一份新的 `verification/acceptance_<日期>/REPORT.md`，实际用到才建产物子目录：

```text
Scope：行为/commit；激活 C*/R*/D*/N*；排除范围与原因
Identity：source/扩展构建、Ubuntu/Python/torch、catalog/combat-profile/teacher/schema，
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
