# 选手 SDK

从根 README 的 `arena.py new MyTeam` 开始。只修改新组件的 `lua/` 下 Lua 文件；`_main.cfg`、`ai.cfg` 和 `arena.json` 保持生成格式。最终交付 `arena.py pack` 生成的单个原生组件 zip。

推荐阅读顺序：

1. [RULES.md](RULES.md)：赛制、计时和故障。
2. [PROTOCOL.md](PROTOCOL.md)：官方 CA 接口和状态访问。
3. [DELIVERY.md](DELIVERY.md)：验证、打包、安装。
4. [CONTEST.md](CONTEST.md)：竞赛约束。

模板返回一个实现 `evaluation(cfg,data)` 和 `execution(cfg,data)` 的 Lua 表，使用原版提供的 `wesnoth`、`ai`、`wml` 和官方帮助库。参战人数通过 `#wesnoth.sides` 获取，不能写死为 2。

`sample_bot` 仅结束回合；`template_bot` 提供简单策略，都不是官方 RCA。
