# GitHub 训练重构经验与本项目建议 — 2026-10-24

结论：值得重构**训练侧的数据批次、BC/PPO 更新和检查点用途**。
保留 lite 规则引擎、公开观测、候选动作、三个独立网络和 Lua 部署。
采用上游已验证的组织方式，不直接把项目改装成另一个完整 RL 框架。
本文是研究建议，未修改训练实现、参数、门槛或历史数据，未 SSH、采样或训练。

## 1. 依据与范围

本地依据为 master `c48d276c2c86ce9ad01467fad5f05151ff778885` 及
[上一轮实力复盘](../model_strength_20261024_2120/REPORT.md)：2v2 BC 攻击
14.1%，BC 复习读取中位数约 550/2048；多数 PPO 批次触发 KL 提前停止；
Duel 回滚后 v110/v200 重现旧权重；最终入选与最新训练版本并不相同。
这些现象不能直接证明换框架、加网络或增加奖励能提升强度。

查阅项目及适用范围：

| 一手项目 | 借鉴的内容 | 不直接移植的内容 |
| --- | --- | --- |
| HumanCompatibleAI/imitation | BC 数据迭代、有效批次与微批次分离 | 展平轨迹、普通固定动作策略 |
| ARISE-Initiative/robomimic | 用索引取序列，读取与缓存策略独立 | HDF5 全量缓存、固定短序列替代完整历史 |
| SB3-Contrib RecurrentPPO | 有序序列、mask、PPO 统计与停止条件 | 用采集时隐藏状态替代本项目当前权重重放 |
| CleanRL LSTM PPO | 可读的 epoch 与优化 minibatch 遍历 | 将最后一个 minibatch KL 当成整轮平均 |
| PyTorch TorchRL | 存储与采样器分离 | 加入整个依赖或直接重放旧策略数据做 PPO |
| Stable-Baselines3 callbacks | 周期性恢复检查点与评估最优模型分开 | 仅按小样本均分选最强模型 |

主研究的完整 commit、文件 SHA-256 与链接见 [sources.json](sources.json)；
循环 PPO 的固定源码与比较见 [RECURRENT_PPO.md](RECURRENT_PPO.md)。
只下载少量源码到忽略的 `data/references/github_refactor_20261024/`，没有引入运行依赖。

## 2. 可以借鉴的上游做法

### BC：优化批次不应等于内存微块

imitation 明确区分 `batch_size` 与 `minibatch_size`：后者只决定每次前向/
反向的内存，损失按其占完整批次的比例缩放，累积后再 optimizer.step。
其有限数据入口还检查实际批次大小，区分 n_epochs 与 n_batches。
[BC 更新源码](https://github.com/HumanCompatibleAI/imitation/blob/e5ef18806c449ca47153b494a02471c5e2ae3a14/src/imitation/algorithms/bc.py#L443-L509)，
[数据入口](https://github.com/HumanCompatibleAI/imitation/blob/e5ef18806c449ca47153b494a02471c5e2ae3a14/src/imitation/algorithms/base.py#L191-L286)。

**本项目推论：** 当前 `minibatch=256` 并不表示每步用了 256 条；CPU 实际是
4 个窗口，每窗口再切为至多 32 条。应让配置与日志明确这三个不同数量。
BC 和 PPO 各有自己的采样语义，适合拆成两个更新模块；无需为两个方法建立
插件注册系统。原有每窗口均权和教师/DAgger 家族配额先保留，不能在拆分时
悄悄改成按长局决策数量加权。

### 序列数据：先决定取什么，再决定怎样读

robomimic 的 SequenceDataset 建立索引到示范及位置的映射，取样时从相应
示范截取序列，提供 padding mask；缓存有 all/low_dim/None 等不同选择。
[索引及缓存](https://github.com/ARISE-Initiative/robomimic/blob/d309eaecc18acf4152a830a895a6984b8ac71b05/robomimic/utils/dataset.py#L140-L243)，
[序列读取](https://github.com/ARISE-Initiative/robomimic/blob/d309eaecc18acf4152a830a895a6984b8ac71b05/robomimic/utils/dataset.py#L536-L580)。
TorchRL 的 buffer 同样把 storage 与 sampler 分开，并展示有限的无放回
迭代；磁盘映射只是可选存储实现。
[存储](https://github.com/pytorch/rl/blob/b763b5cf3056c615b104775ece1ef529b7b6f22c/tutorials/sphinx-tutorials/rb_tutorial.py#L111-L136)，
[有限采样](https://github.com/pytorch/rl/blob/b763b5cf3056c615b104775ece1ef529b7b6f22c/tutorials/sphinx-tutorials/rb_tutorial.py#L409-L436)。

**本项目推论：** 优先使用已经存在的 SQLite 元数据制定窗口计划，加载器
只负责带完整原始前缀的窗口与内存预算。当前按 64 家族先分摊、读到 gz
上限就结束的办法，应改为在可读取家族内回填仍可容纳的窗口，并明确记录
请求数、实际数、来源/家族/动作类别与欠填原因。有足够数据和预算才要求
补足，不能保证任何预算下都读满 2048，也不能以反复读同一个家族掩盖多样性下降。

不马上改为 HDF5、mmap 或整库常驻缓存。当前 SQLite 每个 payload 仍是一条
完整压缩序列，gzip 也不支持任意窗口的廉价随机访问；仅改类名不会减少解码。
先保留现有存储、复用单次解码、回填实际可用配额；若仍由长局解码主导，再
单独立项做分块索引。完整历史以原始公开观测保留，不能缓存跨参数更新的隐藏状态。

### PPO：学习语义要与微块大小解耦

SB3 RecurrentPPO 也会根据**单个优化 minibatch** 的 KL 停止余下更新，
所以不能把“minibatch 早停”本身叫错误；CleanRL 的检查位置也不是直接可复制的答案。
源码细节及限制见 [循环 PPO 调研](RECURRENT_PPO.md)。

**本项目建议：** 为每个 PPO epoch 固定一份打乱后的窗口顺序，无放回遍历；
把几个窗口作为一个逻辑优化批次，32 条只作为内存微块。微块逐个反向以控制
内存，同时累积与原损失相同权重的 KL：窗口内按决策均值，窗口间均权。
在逻辑批次结束、optimizer.step 之前按聚合 KL 决定是否丢弃本步梯度和停止，
保持既有 clip、门槛与梯度限制；不把 .02 改成上游的其它默认值。
序列有放回采样改为无放回是明确的训练行为变化，必须单独验收，不能藏在文件搬动中。

所有退出路径统一返回实际步数、已应用梯度的决策暴露数、已检查但未更新的
决策数、唯一窗口数、每项损失、KL 与 stop_reason。改变 micro 大小应只
影响内存/舍入误差，不应让同一逻辑批次的停止结论随切块改变。
这一改法仍可能在少数步后合理停止；是否改善强度需后续训练证据，不能先承诺。

### 检查点：恢复点与评估冠军是不同用途

SB3 用 CheckpointCallback 周期性保存恢复点，EvalCallback 独立评估并
另存 best_model；两者保存触发和用途不同。
[周期保存](https://github.com/DLR-RM/stable-baselines3/blob/b2878f4b83e21f16a53c54a62def628e05fd2e96/stable_baselines3/common/callbacks.py#L245-L334)，
[评估选择](https://github.com/DLR-RM/stable-baselines3/blob/b2878f4b83e21f16a53c54a62def628e05fd2e96/stable_baselines3/common/callbacks.py#L510-L528)。

**本项目推论：** `latest` 继续原实验，`best` 用于冠军/交付；从 best 改
采样计划是明确的新分支。原样恢复 RNG 是正确的可复现行为，重复旧路径是
从旧状态回滚且后续计划相同的结果，不该“修复”为默认打乱恢复随机状态。
现有 latest.pt 和 best.pt 已经分开；缺的是清晰的入口用途和恢复契约，
不是再发明一层模型仓库。已有三个独立阶段入口也应复用。
若重构恢复模块，还必须保存 epoch 的窗口排列和下一个未应用逻辑批次位置，
否则改成无放回遍历后，仅恢复 epoch/step 加 RNG 不足以可靠复现中途计划。

选拔不能照抄上游“均分更高即替换”。继续保留我们的块轮换、置信区间和
独立 holdout；在训练截止前预留一次候选提名机会，按同一验证计划比较
冠军与最近合法候选，再冻结唯一入选模型做最终 holdout。
这样可避免 FFA4 v143 因不到 v200 而没有晋级机会，但不保证它一定替代 v100。
不能在最终 holdout 上反复挑赢家，不能为省时降低已定验收门槛。

## 3. 建议的模块形状和实施顺序

```text
FormatExperiment（沿用阶段、预算、门槛及采集调度）
  ├─ sequence dataset：窗口计划 → 有界加载 → 批次及读取统计
  ├─ BC learner：教师分层采样 → 累积更新 → 模仿验证
  ├─ PPO learner：无放回 epoch 计划 → 微块 → 逻辑批次 KL/更新
  └─ checkpoints：原实验恢复 / 显式新分支 / 验证冠军 / 最终冻结
```

这是责任划分，不要求把每个箭头都变成一个类。改动放在 `learning/` 的
现有职责模块，必要时新增 `bc.py`、`ppo.py` 等模块；不新建通用框架。

| 阶段 | 单一目标 | 最小验证（建议，未执行） |
| --- | --- | --- |
| A | 先拆 BC/PPO，统一结果对象，保持现行为 | 固定真实记录、相同 RNG/权重，对比拆分前后更新结果及截止/KL 返回字段；复用其余已通过证据 |
| B | 修 BC 欠填与读取统计 | 一个已有 2v2 长局输入，固定种子；有余量时补足，预算不足时明确欠填，保留原前缀和来源配额；只测这个新行为 |
| C | 无放回计划及逻辑批次 KL | 一个冻结 PPO batch，比较 micro=8/32 的加权损失、KL 和停止决定；检查每窗口每轮一次及恢复游标；随后才申请小规模训练效果验证 |
| D | 明确恢复/分支和最终候选提名 | 用两个人工检查点验证恢复选 latest、最终选入选者；中断后恢复同一计划；复用已验收的 BC→PPO→最终链，仅补受影响节点 |

每阶段独立 PR，纯搬动和训练行为变更分开；A 也须给出能在撤销拆分新增契约时
失败的断言。新实现后才进入 TEST.md，本研究不能充当执行授权。

直接换 SB3/TorchRL 的代价目前高于收益：现有网络同时使用动态候选特征、
空间实体、公开历史重放和纯 Lua 同构推理，采集还按游戏全局共享 8 workers。
整库替换会把环境适配、序列语义、并发与导出一起改变，难以归因改进。
先改训练内核，网络架构、引擎与奖励不同时调整。

## 4. 许可与结论边界

主研究四个项目在固定 commit 的 LICENSE 均为 MIT，许可文件哈希已记录；
循环 PPO 两项许可见专题记录。本文没有复制运行实现，不增加依赖。
以后若拷贝代码，须保留对应许可证并更新 THIRD_PARTY；研究链接不代替许可。
上游实现证明这些组织方式可用，不证明本项目会收敛或超过 Astra。
本轮没有运行测试、原版对局或训练，也没有重新采样已有验收。
