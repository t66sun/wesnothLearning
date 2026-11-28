# 验收计划

> 语言：[English](TEST.md) | 中文

## F2. FFA/team 有限任务就绪和最终检查点 critic 校准

- **状态/原因：** FFA/team 有限任务 BC 就绪与对应最终检查点的 critic 校准仍待验收。单挑 BC 资格已验收，合格 v38 和三个归档 PPO 检查点的校准已经实测，critic 表现因训练种子而异。单挑棋力对照结果仍不确定。
- **最小 Ubuntu 输入/流程：** 后续采集或训练需另行授权并使用新日期证据。FFA/team 使用新有限任务数据、原有门禁，以及已审计初始化谱系和独立物理验证/留出布局。复用已验收任务边界夹具。最终检查点校准必须使用被评估的冻结检查点自身产生的完整轨迹；更新前已记录行为不能替代。FFA/team 的对应最终检查点数据集尚待构建。
- **通过标准：** FFA/team 原有语料、覆盖、模仿和场景设计门禁全部通过，行与检查点任务身份兼容。按明确采样设计报告对应检查点的计分终局 MC 校准，与外部截断 bootstrap 自洽性分开。GAE 自洽性或已完成单挑对照均不证明 PPO 收益或收敛。
- **证据：** [单挑 BC 资格](https://github.com/t66sun/wesnothLearning/blob/83266766dc5fbcc3121ccc58262d910a52dfe01a/verification/duel_ppo_acceptance_20261107/REPORT.md) · [单挑最终检查点校准](../verification/ppo_diag_capture_20261115/REPORT.md) · [有界单挑棋力对照](../verification/ppo_vs_bc_acceptance_20261115/REPORT.md)。[历史正式运行](https://github.com/t66sun/wesnothLearning/blob/83266766dc5fbcc3121ccc58262d910a52dfe01a/verification/formal_30h_scratch_20261106/REPORT.md)和[目标诊断](https://github.com/t66sun/wesnothLearning/blob/83266766dc5fbcc3121ccc58262d910a52dfe01a/verification/team_critic_horizon_20261106/REPORT.md)保持原范围。
- **训练阻塞：** 阻塞全赛制有限任务就绪、最终策略校准、PPO 收益与收敛声明，不授权后续执行。

以上不授权采集或训练。
