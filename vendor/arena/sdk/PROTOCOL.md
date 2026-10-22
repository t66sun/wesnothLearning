# 原生 AI 接口 v2

不再使用 stdin/stdout 行协议，不提交独立程序。比赛和原版均通过官方 Lua 候选动作（Candidate Action，CA）框架调用同一份代码。

```lua
local bot = {}
function bot:evaluation(cfg, data)
    -- 只评估。分数 0 表示本 CA 没有动作，原版结束该方回合。
    -- 选中动作可以写入 data.plan，执行时重新检查单位是否仍存在。
    return 0
end
function bot:execution(cfg, data)
    -- 使用 ai.move / ai.move_full / ai.attack / ai.recruit 等官方动作。
end
return bot
```

注意冒号方法的隐含 `self`。`data` 由官方框架提供；不要把不同阵营的持久状态放进共享全局。评估必须返回 0 到 1000000 之间的有限数字；执行必须有限结束并推进游戏状态。原版候选动作循环负责重复评估，直到没有可执行动作。

注册配置只包含选手的这一项 CA，**没有隐藏的默认 RCA 代走**。可以在自己的 Lua 模块内拆分策略或使用官方帮助库，最终仍由该入口调度。

## 常用官方接口

|需求|接口|
|---|---|
|当前阵营、回合、人数|`wesnoth.current.side`、`wesnoth.current.turn`、`#wesnoth.sides`|
|本方单位|`wesnoth.units.find_on_map {side=wesnoth.current.side}`|
|金币、可招募类型|`wesnoth.sides[side].gold`、`.recruit`|
|可见敌人|官方 `ai/lua/ai_helper.lua` 的 `get_attackable_enemies()`|
|路径、可达格|`wesnoth.paths.find_path`、`wesnoth.paths.find_reach`|
|战斗预测|`wesnoth.simulate_combat`，按本机 1.18 接口使用|
|地形、村庄|`wesnoth.current.map`、`wesnoth.map.find`、`wesnoth.map.get_owner`|
|动作检查|`ai.check_move`、`ai.check_attack`、`ai.check_recruit`|
|动作执行|`ai.move`、`ai.move_full`、`ai.attack`、`ai.recruit`|

坐标和武器下标均采用原版 Lua 的 **1 起始**语义；没有旧版动作编号列表。检查结果与执行结果都应检查 `.ok`。检查失败可以继续选择别的动作；执行非法动作会判故障。

允许同一次 `execution` 调用多个合法官方动作，但评估和全部执行共用本次 1 秒预算。推荐一次执行一个动作，使状态更新与决策边界清楚。首次入口模块加载也在首次 10 秒内；原版进程加载时间单独计，不扣选手预算。Lua 回调预算和外部 watchdog 都是实际墙钟时间。

## 信息与公平性

原版 Lua 可以访问比当前阵营视野更多的信息。比赛规则只允许读取本方单位和资源、已公开规则地图、当前可见敌人，以及此前合法观察到的信息；不得读取敌方金币、隐藏单位、未观察到的村庄归属、未来 RNG、裁判内部状态，或修改游戏状态绕过 `ai` 动作。普通 `find_on_map {}` 不会自动替你限制视野。

正式赛要求源代码审查；包验证只检查格式、路径、大小和固定 WML 配置，**不证明 Lua 策略合规，也不是每方独立的安全沙箱**。官方帮助库的使用也必须遵守相同信息边界。禁止打印伪造裁判事件或修改全局 API。

官方资料（以安装的 1.18.8 行为为准）：

- https://wiki.wesnoth.org/Creating_Custom_AIs
- https://wiki.wesnoth.org/LuaAPI/ai
- https://wiki.wesnoth.org/LuaAPI
- https://wiki.wesnoth.org/Wesnoth_AI_Framework
