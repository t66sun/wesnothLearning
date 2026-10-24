# 循环 PPO：GitHub 实现对照与重构边界

日期：2026-10-24。范围：只读上游源代码、记录设计建议；未修改生产代码，未连接服务器，未采样、训练或运行测试。

## 固定来源

通过 GitHub commits API 查询 master，并读取下列文件；链接固定到提交，避免分支后续变化：

- SB3-Contrib：`f09418152160fce6c05c02afeaf7d10aa9c3612e`（提交时间 2026-10-16）。[提交](https://github.com/Stable-Baselines-Team/stable-baselines3-contrib/commit/f09418152160fce6c05c02afeaf7d10aa9c3612e)
- CleanRL：`fe8d8a03c41a7ef5b523e2e354bd01c363e786bb`（提交时间 2026-04-20）。[提交](https://github.com/vwxyzjn/cleanrl/commit/fe8d8a03c41a7ef5b523e2e354bd01c363e786bb)

## 上游事实

| 主题 | SB3-Contrib RecurrentPPO | CleanRL Atari LSTM |
| --- | --- | --- |
| 每轮覆盖 | 保持序列次序，将全体索引随机旋转后逐批切片；未早停的一轮覆盖全部索引一次，而非反复有放回抽窗。[缓冲区 L149–199](https://github.com/Stable-Baselines-Team/stable-baselines3-contrib/blob/f09418152160fce6c05c02afeaf7d10aa9c3612e/sb3_contrib/common/recurrent/buffers.py#L149-L199) | 每轮打乱环境索引，按环境分批，保留各环境的整段时间顺序；未早停的一轮每个环境出现一次。[训练 L295–313](https://github.com/vwxyzjn/cleanrl/blob/fe8d8a03c41a7ef5b523e2e354bd01c363e786bb/cleanrl/ppo_atari_lstm.py#L295-L313) |
| 隐状态 | 收集时存 actor/critic 的 LSTM 状态；训练切段时取段首已存状态初始化。[存储 L138–145](https://github.com/Stable-Baselines-Team/stable-baselines3-contrib/blob/f09418152160fce6c05c02afeaf7d10aa9c3612e/sb3_contrib/common/recurrent/buffers.py#L138-L145)、[取样 L207–243](https://github.com/Stable-Baselines-Team/stable-baselines3-contrib/blob/f09418152160fce6c05c02afeaf7d10aa9c3612e/sb3_contrib/common/recurrent/buffers.py#L207-L243) | 保存本轮 rollout 起点的状态副本，采集不建计算图；每次训练取对应环境的段首副本。[采集 L233–248](https://github.com/vwxyzjn/cleanrl/blob/fe8d8a03c41a7ef5b523e2e354bd01c363e786bb/cleanrl/ppo_atari_lstm.py#L233-L248)、[训练 L308–313](https://github.com/vwxyzjn/cleanrl/blob/fe8d8a03c41a7ef5b523e2e354bd01c363e786bb/cleanrl/ppo_atari_lstm.py#L308-L313) |
| 边界与补齐 | episode/env 切换产生序列边界；pad 后提供有效位 mask；归一化、policy/value/entropy loss 和 KL 排除补齐位。[边界 L83–95](https://github.com/Stable-Baselines-Team/stable-baselines3-contrib/blob/f09418152160fce6c05c02afeaf7d10aa9c3612e/sb3_contrib/common/recurrent/buffers.py#L83-L95)、[mask L342–403](https://github.com/Stable-Baselines-Team/stable-baselines3-contrib/blob/f09418152160fce6c05c02afeaf7d10aa9c3612e/sb3_contrib/ppo_recurrent/ppo_recurrent.py#L342-L403) | 使用等长环境时间片，不做该类变长 padding；done 在 LSTM 每步重置状态。[状态 L140–157](https://github.com/vwxyzjn/cleanrl/blob/fe8d8a03c41a7ef5b523e2e354bd01c363e786bb/cleanrl/ppo_atari_lstm.py#L140-L157)、[索引 L295–313](https://github.com/vwxyzjn/cleanrl/blob/fe8d8a03c41a7ef5b523e2e354bd01c363e786bb/cleanrl/ppo_atari_lstm.py#L295-L313) |
| KL 早停 | 每个 optimizer minibatch 计算近似 KL；超过 `1.5 * target_kl` 时在本批 optimizer.step 前退出整个 update。不是整轮平均 KL。[L397–421](https://github.com/Stable-Baselines-Team/stable-baselines3-contrib/blob/f09418152160fce6c05c02afeaf7d10aa9c3612e/sb3_contrib/ppo_recurrent/ppo_recurrent.py#L397-L421) | 每批先 step，epoch 结束才判断 target_kl；判断值是最后一批的 KL，不是全轮平均。[L314–356](https://github.com/vwxyzjn/cleanrl/blob/fe8d8a03c41a7ef5b523e2e354bd01c363e786bb/cleanrl/ppo_atari_lstm.py#L314-L356) |
| 早停后记录 | break 后仍到统一记录段；`_n_updates` 按进入过的 epoch 增加，不等于 optimizer step；KL 日志平均的是最后进入的 epoch 中已检查的批次。[L419–438](https://github.com/Stable-Baselines-Team/stable-baselines3-contrib/blob/f09418152160fce6c05c02afeaf7d10aa9c3612e/sb3_contrib/ppo_recurrent/ppo_recurrent.py#L419-L438) | break 后仍记录 loss/KL/clipfrac/SPS；多项是最后批次值，clipfrac 是已访问批次的均值，并不提供独立样本覆盖率。[L355–372](https://github.com/vwxyzjn/cleanrl/blob/fe8d8a03c41a7ef5b523e2e354bd01c363e786bb/cleanrl/ppo_atari_lstm.py#L355-L372) |

## 对本项目的判断（推论，不是上游结论）

现状依据上一轮[实力复盘](../model_strength_20261024_2120/REPORT.md)及本次研究任务的约束：当前权重重放原始历史前缀、动态合法候选最多 128、CPU 上有限窗口和 32-decision 微块、微块 KL 可结束整个 update，有放回抽窗。

1. **“微批次 KL 早停”不能单独判成 bug。** SB3 也会这样做。需要区分“为省内存拆开的计算微块”和“真正进行一次 optimizer.step 的统计批次”；若两者原本相同，仅改名字或加大 target_kl 不解决更新稀少的原因。
2. **优先重构样本计划，而非换算法。** 在一个 update 内先固定合法训练窗口清单，每个 epoch 打乱后无放回遍历。窗口的训练目标区间应不重叠；若保留重叠，必须明确计数的是窗口覆盖还是唯一 decision 覆盖。早停时允许未覆盖，报告缺口，不伪称完成整轮。
3. **将统计批次和计算微块分离是可选方案。** 若一个 optimizer batch 分成多个微块，保持同一组参数计算这些微块，按现有目标的权重汇总 loss/KL（本项目保持窗口等权、窗口内 decision 等权）；过阈值不 step，否则累计梯度后仅 step 一次。SB3 的有效位平铺均值只在选择同一目标时适用。不得把不同 optimizer step 后的 KL 混合成“同批平均”，不得把 padding 当样本。
4. **先记录有效更新，再判断调整方向。** 正常结束、KL 停止和截止时间返回都走同一统计出口：计划/已访问/实际优化 decision 数、唯一覆盖率、optimizer steps、早停 epoch/batch、与目标权重一致的有效位 KL 和 clip fraction、stop_reason。监测值必须注明来自 step 前还是 step 后。步骤计数与样本覆盖分开，不能用 epoch 冒充更新量。
5. **保留当前权重的历史前缀重放契约。** 上游的已存隐状态方案减少重算，但它不是当前权重完整历史重放的等价替代；不得在本次结构整理中悄悄换成旧策略 detached 状态。缓存只在参数版本及合法可见前缀一致时复用；跨 optimizer step 的缓存必须作废或明确另立实验。

## 建议落地顺序与最小验证（尚未实施）

- 第一项 PR：独立出 update 的窗口计划与统计结果；保留现有网络、奖励、KL 阈值及状态重放，先消除“采样次数充足但唯一覆盖很少”和早退出漏指标。不要把 BC 读取欠填修复混进此 PR。
- 第一项最小验证：已有短序列 fixture，固定 seed 验证每轮索引无重复无缺漏、断局不串状态；分别触发正常/KL/截止退出，核对实际 optimizer.step 与报告一致。微块未改则不新增大规模对局。
- 第二项 PR（只有测得必要才做）：优化器批次的梯度累计与加权 KL；构造一组变长序列，保持窗口等权，验证不含 padding 的 loss、KL、梯度与未切分同批参考一致，并检查阈值分支未 step。由于浮点顺序不同使用既有合理数值容差。
- 之后才比较小规模已授权训练中的覆盖、KL、optimizer steps 和固定对手评分；指标改善不代表实力通过，不承诺给定收益。不因研究笔记而启动训练。

## 不直接适用与复用许可

- CleanRL 此文件是 Atari 固定离散动作模型，不包含本项目动态候选编码和 Lua 推理部署；其网络与环境构建不是替换目标。[固定动作头 L137–138](https://github.com/vwxyzjn/cleanrl/blob/fe8d8a03c41a7ef5b523e2e354bd01c363e786bb/cleanrl/ppo_atari_lstm.py#L137-L138)、[环境 L205–209](https://github.com/vwxyzjn/cleanrl/blob/fe8d8a03c41a7ef5b523e2e354bd01c363e786bb/cleanrl/ppo_atari_lstm.py#L205-L209)
- 两个项目均为 MIT；真正复制代码时保留原版权与许可。此笔记只引用链接并概括设计，没有引入上游代码。[SB3-Contrib LICENSE](https://github.com/Stable-Baselines-Team/stable-baselines3-contrib/blob/f09418152160fce6c05c02afeaf7d10aa9c3612e/LICENSE)、[CleanRL LICENSE](https://github.com/vwxyzjn/cleanrl/blob/fe8d8a03c41a7ef5b523e2e354bd01c363e786bb/LICENSE)
