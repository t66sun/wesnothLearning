# Astra 教师派生源

`gpt6astra/` 是冻结包 `data/opponents/gpt6astra.zip` 的源码副本（父包哈希由
`learning.teachers.parent_digest` 记录）。冻结压缩包本身从不修改。

副本只适配 lite 规则改变的部分：攻击评分使用确定性的 `expected_damage_v1`
结果，减速价值为 25% 伤害加上移动限制，中毒每回合价值 6 点。招募、移动、
队伍与目标选择结构保持上游实现。这些数值集中在 `lua/value.lua`，
`duel.lua`、`four.lua` 和 `eight.lua` 调用它。

lite 宿主始终加载此源码，因此引用冻结包的任务同样运行适配后的教师。
`learning.teachers.build(path)` 从源码生成可用于原生或外部部署的压缩包；
派生产物属于构建产物，不提交。

源码哈希以 `teacher_profile` 和 `teacher_source_sha256` 写入 lite 行、
检查点、任务元数据与导出；同一运行不能混用不同教师配置的数据。
