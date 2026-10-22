# 精简引擎后续测试范围（本次未编写、未执行测试）

当前仅做 Python AST 与 Lua load 解析语法检查（未执行Lua模块）；没有 cargo/rustc，Rust/PyO3/mlua 尚未编译。没有 1.18.8 发行数据，catalog/rules/maps 未生成，真实全量覆盖、Astra 宿主兼容、规则正确性、5 倍性能均未验收。标准leadership/illumination/backstab/steadfast、攻反双方plague、一步teleport已有明确近似实现；完整声明条件过滤、随机traits生成/升级保留、变体运行实例、AMLA/升级选择、vision_costs/jamming仍是代码缺口，必须单独列出，不能称为仅未测试。

## 建议顺序与范围

1. 先构建 Rust/PyO3/mlua；核对包 ABI、Windows Lua vendored 构建、单个与批量 JSON API、批次非法动作原子回滚、所有错误可理解。不要将语法检查当运行通过。
2. 从可信 1.18.8 发行包独立生成数据/可执行哈希清单；在 core 与每个自带战役上下文捕获。核对所有已声明单位、性别/变体、升级/瘟疫链、traits、地形 base/overlay/aliases 和选定地图实际数量、来源、scope差异。原始 WML 保留与 compact runtime 实例化分别报告。每个能力/单位列 exact/approximate/unsupported_script 和原因，拒绝静默降级。
3. 确定性原版差分：奇偶列边缘六角邻接、地图坐标/距离、各移动类型、低移动余量、slowed、ZOC、游击、己方穿越、连接/断开城堡招募、多个领袖、占村耗尽、传送/隐匿/接敌路径中断、休息/毒/治疗/收入/维护、经验/升级/AMLA、淘汰轮序与团队胜负。未支持特性应明确拒绝，不以普通战斗替代。
4. 逐击命中注入差分：先攻/双方先攻、攻击/反击武器平局、逐击死亡与停击、减速即时作用、吸血实际伤害/四舍五入、中毒免疫、魔法/精准、冲锋、狂暴30轮、swarm、瘟疫与地形限制、攻击方/防守方升级。独立统计比较命中/死亡/状态概率误差≤1个百分点、平均HP误差≤0.5，报告样本数/区间/方差，不能把抽样噪声当语义偏差。
5. 信息隔离：改变隐藏敌兵/隐藏村庄归属/未知地形，公开观测/候选/预测和策略输入不得变化；raw裁判标量只进入训练标签。fog/shroud四组合、非共享盟友/共享地图/共享视野/定向共享、信息年龄/敌军过时记录、隐藏阻挡/伏击后重新观察、任意side切换拒绝。snapshot真状态永不提供教师或策略。候选/教师查询不消耗战斗/招募RNG，恢复命中流cursor及所有账本。
6. 实际Astra zip的duel/four规划、同一Lua O/C/S模块候选、最多128候选、移动/移动攻击/招募/结束、克隆单位/特征访问/战斗hp_chance整数键、断续路径执行、无变化动作记忆提交、教师原意与实际终点。原版接口与host shim分别列缺失API；不能用别的启发式替代Astra。官方baseline保留native。
7. 训练标签接通：原始economy/control/explored、所有方初始可见区扣除、队友探索去重、重复揭雾不增加、恢复共享账本、终局/截断bootstrap、完整provenance/奖励版本；政策回调不接收reward_only信息。整局结果 bots/teams/winner/winning_team/rank_points/survivors 与原版收益定义一致。多方淘汰并列顺位需明确比较。
8. 性能固定同工作量：单进程 cold/hot、相同CPU配额/地图/单位/策略/教师/动作脚本。分规则核/共享候选/真实Astra/模型/JSON与轨迹IO；全部子进程CPU核秒计入。wall和CPU分别≤native20%，报告p50/p95、RSS、置信区间；4/8worker吞吐另列。当前全量视野重算与128采样预测是潜在热点，需实际profiling后优化。

## 报告格式

保存机器可读JSON及简洁Markdown。至少包括 commit、构建/依赖版本、1.18.8发行哈希、catalog/rules/maps哈希、engine/rules/RNG/候选/schema版本、系统CPU/内存/线程配额、样本和seed、fixture/地图/阵营/赛制/位置、原版和lite输入、注入命中序列、预期/实际、偏差分类、通过/失败/未支持/inconclusive、故障与缺失块数量、复现命令。

P1定义覆盖、P1确定性语义、P1战斗统计、P2真实Astra宿主、P2单局wall、P2总CPU、并行吞吐分开签署。缺资料、未编译或未执行写 pending，不写通过或零错误。只有独立覆盖及验收证据才能更新catalog.complete/native_accepted/performance_accepted；未验收不得放开长采集默认gate。
