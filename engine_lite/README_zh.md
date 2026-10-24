# 独立 Rust 精简规则核

> 语言：[English](README.md) | 中文

本目录提供原生数组状态、PyO3 JSON 批量 API、直接嵌入的常驻 Lua 5.4 VM。没有复制无明确再分发许可的参考模拟器代码。本次没有构建或运行引擎；本机缺少 cargo/rustc、原版 1.18.8 发行数据，原版规则及性能验收均未完成。

构建入口：安装 Rust 工具链后，在本目录使用 `maturin develop --release`。Python 模块 `_engine_lite.LiteEngine(rules_json,spec_json)`；所有 JSON 坐标 `pos/to` 为零起始行优先索引，Lua 转换为一基六角坐标；武器 JSON 从 0 起始，Lua 从 1 起始。

`GameSpec` 必须明确给出 width/height、扁平 terrain、sides、units、seed、max_turns。side.id 连续从 1 起始、team 非空；单位包含 id/unit_type/side/pos/hp/moves/attacks_left/xp/leader/status/traits。`allow_approximate=true` 必须显式提供。未实现声明的单位、招募链、升级链和瘟疫链拒绝运行，不静默降为普通攻击；全量定义仍可保留在规则表枚举。当前新引擎所有游戏都标记 approximate。

接口：reset、observe/observe_batch、legal_actions/legal_batch、step/step_batch、snapshot/restore、inject_hits、forecast、configure_host、decision、execute_candidate。step_batch 遇到非法动作恢复批前状态与 RNG。snapshot 是裁判真状态，不提供给策略；直接 Lua 桥固定观察方，不允许 Astra 切换其他方视图。原始奖励裁判只导出标量，策略回调收不到它们。

`learning.lite_host.LiteHost` 加载项目同一份 observation/candidates/spatial/rewards 和 `data/opponents/gpt6astra.zip` 中真正 Astra，不另造教师；Lua 路径、战斗预测和结算直接调用 Rust，不经 Python 逐格往返。共享 Lua 支持的原版 API 以外调用明确报错。`learning.lite_policy` 可从固定标准时代阵营和冻结地图创建 GameSpec，读取导出 addon 旁的 model.pt 进行 CPU 张量推理；官方 baseline 仅原版可用。默认要求规则、语义、性能验收通过，因此当前正常训练会明确拒绝使用未验收引擎。

`NativeAdapter` 默认接入 `learning.native_transport.NativeTransport` 和 `native_rpc.lua`：独立临时用户目录、常驻原版进程、共同 Lua 观测/候选及串行文件 RPC；原版 snapshot 使用冻结种子与完整请求日志重启重放，成本较高。该实现尚未运行原版核验；日常 native 整局采样继续使用 `match.play_game`。

已编写规则：地形代价移动、可见敌方 ZOC、己方穿越、连接城堡招募、村庄占领/经济、fog/shroud/历史地形与敌情、配置化盟友地图/视野共享、多方轮转/领袖淘汰/团队终局、逐击命中死亡/反击/经验升级、减速/毒/吸血/先攻/精准/魔法/冲锋/30轮狂暴/基础瘟疫、基本治疗/休息、声明隐匿/夜隐/传送、分离战斗/招募 RNG 与命中注入。此清单描述代码路径，不代表规则差分已通过。

常见标准声明另有明确近似路径：相邻高等级 leadership 每等级差 +25%、illuminates 附近时段 +25 并限幅、背面盟友 backstab、守方 steadfast 双倍正抗性上限50%、反击瘟疫、一步传送代价。预测同样使用这些规则，但仅使用合法可见上下文。捕获保留每项原始条件并写 approximation_reasons，运行必须显式 allow_approximate。

明确差异与实现缺口：复合伤害修正舍入、反击武器选择、上述声明式条件的原版完整过滤语义、变体运行实例、随机traits生成、AMLA/升级选择、精确治疗与减速清除时机、独立 vision_costs/jamming、盟友定向共享细节、远程寻路/ZOC、传送失败细节及战役事件。已有traits可由调用方注入 resolved_max_hp/resolved_max_moves/resolved_max_experience/resolved_weapon_damage；跨升级保留trait效果仍缺实现，不能称为完整traits系统。未知能力/任意脚本由捕获 coverage 标记并阻止相关链使用；有声明且实施的标准近似能力不会被当作普通攻击。预测为独立固定 RNG 的 128 次采样近似，不消耗对战随机流；不能用它证明战斗概率已达到统计门槛。完整视野重算、每回合/动作 JSON、clone预测尚需性能优化，不能声称达到 5 倍。

当前没有生成真实全量规则、地图或验收报告，没有启动采样、游戏、训练或测试。后续测试与报告要求见 TEST_SCOPE.md；所有验收仍待执行。
