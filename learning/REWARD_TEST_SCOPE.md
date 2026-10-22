# 奖励与在线控制：后续测试范围和接入契约

以下保留最初实现阶段的分项清单；当前状态与通过记录统一维护在 [docs/TEST.md](../docs/TEST.md)。

## 接入契约

- `RewardConfig` 冻结字段为 `economy/control/explore/mode/entropy/bc_aux/gamma/gae_lambda/reward_version/reward_formula_id`。终局权重固定为 1，不提供可改入口。
- `lua/rewards.lua.capture(obs,memory,true)` 只把裁判经济量放入返回的 `reward_raw`。返回的 `economy/control` 是当前潜势，`explored` 是扣除初始可见区之后累计归一化面积。下一快照减当前快照才是一次区间探索增量。不要把这些裁判标签并入公共价值输入、global、spatial 或候选。
- 在每方第一步动作前采集初始快照，每次动作后及末局采集快照；正常终局潜势归零但保留最后一次探索增量，截断保持匹配的最终 raw/value/turn bootstrap。
- Lua 默认均匀探索面积权重，整局 `explored<=1`；无 fog 时为零。shroud 关闭仍检查实际 fog 可见性。复杂/单向共享规则由宿主提供 `shared_exploration_scope/shared_exploration_members/shared_ledger`，不得自动扩大共享权限。默认按双方都启用 share_view 或 share_maps 的盟友生成共享域。运行时在初始单位及视野建立后、任意动作之前调用一次 `initialize_all()`，排除所有方初始可见区域。账本保存于游戏 Lua kernel 的唯一命名全局，LearningSupport 与不同导出策略 addon 共享该账本；只把本方允许的 scope 放入本方 memory，不把全局账本传 actor。每局进程/宿主重用时重新初始化；`reset()` 可清除账本。
- 地图控制默认使用合法地形上的四种移动代价指纹聚类、有界多源最短路、敌军历史按回合指数衰减。超过四种移动指纹时按四类中的最近指纹近似，属于明确的奖励计算近似。无单位/未知格为中立。地图总战略权重是裁判归一化标量；不可把隐藏战略位置传给 actor。
- `RewardController(run_dir,format_name,state=checkpoint_state,config=initial_dict)` 每赛制独立。`boundary(batch,metrics)` 仅在之前的采集和更新完全结束之后调用，返回值冻结到下一批每个 job/对局。`state_dict()` 进入原有检查点，不替换预算、优化器或 RNG 状态。
- CLI 调用 `queue_control(run_dir,format_name,changes)`，字段只允许 `economy/control/explore/mode/entropy/bc_aux`。`mode=fixed` 可暂停自动控制。`show_control` 返回有效配置、待应用命令、事件序号及最后错误。待应用命令按赛制原子写盘，应用时共用追加式 `control/events.jsonl`，事件包含完整 old/new、来源、原因、批次、序号、命令 ID、校验和和前一校验和；命令 ID 防止崩溃恢复重复应用。
- `scheduled` 模式构造参数 `schedule=[{'batch':50,'changes':{'explore':0.09}}]`；计划游标进入控制器状态。运行中人工改动和 scheduled 仍需通过相同 pending/event 通路。

## 自动控制证据格式

`learning/reward_metrics.py` 实现实际轨迹到控制器的证据链。采样结果保存 `reward_diagnostics=summarize_game(records,result,job)`；`build_control_metrics(validation_jobs,validation_results,teacher_evidence,comparison)` 将完整轮换块中的策略方指标与真实 Astra 参考配准，返回下述 metrics。参考必须是 validation 分区，严格匹配赛制、引擎、规则、地图名称及 SHA、阵营、队友上下文，每个分层至少四个独立 game_family。train 地图及 holdout 均不能替补，缺失记录进入 `excluded_evidence`，不生成可调参的完整块。

5/10 回合指标取该方当回合最后一个已提交决策的真实 reward_after/raw；缺少该回合不插值。领袖存活优先采用裁判终局 survivors 清单，无此清单时采用 10 回合公共己方领袖 HP；损失使用连续合法己方单位快照的 HP 减量（完整实体快照确认的死亡计剩余 HP），除以见过唯一己方单位的 max HP 容量；实体列表不完整则 loss 缺失，不猜测死亡。它是明确的 HP 损失指标，不是未知敌军损失或金币材料损失。只与相同定义的 Astra 记录比较。

参考采样应从 teacher job 骨架创建独立 `phase=reward_reference` 作业，改用 validation 地图，覆盖同阵营和队友上下文；只开 Astra 采集，保存诊断，不进入 BC 教师分片池。验证策略作业也要对 policy_sides 开启训练日志采集才能获得 raw 信号。原生与 lite 采样器都应挂接 summarize_game。构建器返回 `new_games=0`，PPO 收集继续单独提供增量无故障轨迹数，避免同一游戏重复计数。

`boundary` 的 `metrics` 是自上次提交以来的增量，不是重复累计统计：

```json
{
  "partition": "validation",
  "new_games": 64,
  "faulted_games": 0,
  "shaping_rms": 0.03,
  "terminal_rms": 0.4,
  "validation_blocks": [{
    "id": "duel-v100-map1-block0",
    "complete": true,
    "faults": [],
    "fixed_score": 0.2,
    "native_score": null,
    "strata": [{
      "map": "Hamlets",
      "faction": "Loyalists",
      "coverage5": 0.3,
      "coverage10": 0.5,
      "astra_coverage5": 0.4,
      "astra_coverage10": 0.6,
      "control": 0.3,
      "astra_control": 0.5,
      "leader_survival": 1.0,
      "astra_leader_survival": 1.0,
      "loss": 0.1,
      "astra_loss": 0.2
    }]
  }]
}
```

`new_games` 包含故障数时再通过 `faulted_games` 扣除；如上游已给无故障计数，`faulted_games` 应为零。轮换块 ID 全局唯一，完整才接收，按 ID 去重。每个窗口至少 12 个完整块，每 50 批且至少 64 个新无故障局才检查；探索/控制调整需要两个可比窗口，探索成熟下降需要三个窗口。强度回退要求三个窗口形成连续两次下降，同时控制指标连续上升；六局不能触发回退。无 native 证据不合成 native 分数。最终 test/holdout/final 分区不可调参。

## 必须覆盖的后续检查

| 范围 | 输入与判据 |
| --- | --- |
| 终局 | duel 胜平负 +1/0/-1；2v2 队员共同收益；FFA ties、全平、不同积分尺度，平均为零且最大绝对值为 1 或全零 |
| 经济 | 招募等额金币换健康兵力前后势能不变；受伤/治疗/死亡/升级/负金币；团队成员平均而非总和；结果有界 |
| 势能和 GAE | 一回合多动作不重复折扣；不同自身回合跨度；正常终局势能归零；截断 raw/value 同版本 bootstrap；最后动作探索增量保留；faulted game 排除 |
| 探索 | 初始全方/共享初始区域扣除；往返和重新揭 fog 不重复；盟友共享与不共享；关 shroud/开 fog；无 fog 默认为零；整局正奖励上限为冻结 explore 系数 |
| 合法地图控制 | 隐藏敌军位置/HP 改变而合法观测不变时分数和 actor 输入不变；仅 last-seen 年龄变化；合法格重新可见但旧敌军不在则遗忘；未知地形不构图；固定分母；同格战略权重 max 不叠加 |
| 图预算/缓存 | 至多四类代价图；多源距离与小地图手算一致；同回合同视图复用；地形、可见己军移动/HP、敌军合法出现/消失、回合衰减、归一化变化使缓存正确失效；缓存不会随每个候选扩张 |
| 原生 RNG | 敌军历史使用 detached clone；重复捕获不改变对战 RNG、单位/地图状态或策略合法候选 |
| 自动证据 | 49/50 批、63/64 局、11/12 块边界；faults/缺失/重复块；地图/阵营 Astra 配准；两个窗口门槛；探索三窗口下降；无证据保持；每次自动权重变化不超过 10% 和范围 |
| 实际证据采集 | 原生/lite sampler诊断接入；5/10回合实际raw采样；失去领袖及单位死亡；治疗和招募不掩盖HP损失；128实体截断不伪造死亡；无完整10回合轨迹保持缺证据；至少4个独立Astra对局族；相同地图名但不同SHA、不同引擎/规则、阵营或队友上下文禁止串用；BC数据池排除奖励参考 |
| 回退 | 固定对手和 native 分开；控制上升但成绩连续两个窗口下降；小面板波动不触发；只回退控制，不改经济/熵等无关项 |
| 人工控制 | 范围、NaN、未知字段和空命令报错；固定模式暂停自动；手工熵/BC辅助不混称奖励权重；批次内不变，新批次/新局生效 |
| 文件/恢复 | pending 原子替换；跨三个赛制并发队列；全局事件序号和hash链；应用前后各崩溃点；已追加未清pending不重复应用；checkpoint cursor落后可重放；cursor超前/校验损坏报错；恢复不重置统计/预算 |
| PPO 隔离 | 同一批冻结策略、奖励、引擎规则版本；新奖励不能复用旧advantage/bootstrap；BC动作标签可以复用；一个赛制热改动不影响另外两个赛制 |

## 报告要求与当前缺口

每项报告给出赛制、引擎、规则/RNG、奖励公式及配置版本、模型版本、地图/阵营、game_family/seed、输入摘要、预期与实际、状态（pass/fail/not_run/blocked）、证据路径。性能另记控制图构建/搜索/缓存命中耗时与峰值内存。行为按地图/阵营报告首次出城、5/10 回合探索率及村庄/战略控制、领袖生存、伤亡、正式胜平负，不能用 shaping 总分替代强度。

尚需原生与 lite 共同宿主确认：初始快照时点、最后动作后快照、共享账本生命周期及复杂单向共享、单位 clone 的历史保存、全地图标量裁判权限、地图地形变化后的固定战略集合策略、控制证据收集器是否已按上述完整轮换块格式接入。Python/Lua 控制算法采用相同有界指数影响形式；移动类聚类和地形战略标签需在实际规则表上做一致性与迁移审计。没有足够 Astra 分层/完整轮换证据时 adaptive 应保持初始值，而不是使用未校准的代理指标。
