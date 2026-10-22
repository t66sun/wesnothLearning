# Wesnoth Native Arena v2

选手交付原生 **WML＋Lua AI 附加组件 zip**。Arena、Tournament 和实际游玩都使用 **Battle for Wesnoth 1.18.8 x86_64 官方运行时**；无需外部 bot 服务，不接收旧版 exe。本包不含游戏本体，也不再包含独立规则引擎。

需要 Python 3.10+、已安装的 Wesnoth 1.18.8；图形启动器另需 Tkinter。Python 部分仅使用标准库。

## 开始

以下命令在本目录运行；Linux 将 `python` 换为 `python3`，Wesnoth 路径换为本机程序。

```powershell
$env:WESNOTH_EXE='D:\SteamLibrary\steamapps\common\wesnoth\wesnoth.exe'
python arena.py doctor
python arena.py new MyTeam
# 编辑 submissions/MyTeam/lua/bot.lua
python arena.py match submissions/MyTeam baseline -n 6 -j 4
python arena.py pack submissions/MyTeam --output MyTeam.zip
```

`new` 复制一个能够招募、移动、攻击的简易模板。`sdk/sample_bot` 仅结束回合，用于验证接线；两者均不是官方 baseline。合格线为六局对官方 `baseline` 获胜多于失败，之后应继续改进。

```powershell
python arena.py ffa submissions/MyTeam baseline baseline baseline -n 4 -j 4
python arena.py ffa submissions/MyTeam baseline baseline baseline baseline baseline baseline baseline -n 8 -j 4
python arena.py validate MyTeam.zip
python -m unittest discover -s tests
python tests/smoke_native.py --output smoke_results
```

每局生成结果 `.json`、裁判事件 `.events.jsonl`、完整运行日志 `.log`，正常结束时另有原版 `.replay.gz`。输出默认放在独立的 `replays/series_<编号>/`；可用 `--replays` 指定一个不存在的目录。`--json` 可另存系列赛汇总。`match`、`ffa` 均无窗口；`-j` 最大为 4。

## 直接安装进原版，与人类对战

```powershell
python arena.py install MyTeam.zip
```

程序通过官方 `--userdata-path` 定位用户目录，安装到 `data/add-ons/MyTeam`；遇到同名组件拒绝覆盖。也可加 `--userdata "用户目录"`。手动安装时，把 zip 内的整个 `MyTeam/` 放进用户目录的 `data/add-ons/`。

重启原版 → **多人游戏 → 本地游戏 → 创建游戏 → 模组/修改**，勾选 **Arena AI: MyTeam**。在阵营设置中将自己设为人类，把对手设为电脑，并在 AI 列表选择 **Arena AI: MyTeam**。不需要 Arena 常驻，不需要特殊启动器。具体菜单译名随游戏语言略有不同。

快速打开同一比赛地图的人机对局：

```powershell
python arena.py play MyTeam.zip --players 4 --side 2
```

你控制第 1 方，选手控制第 2 方，其余为官方 AI。`--side 1` 时人类改为第 2 方。无参数运行 `python arena.py` 或双击 `run_arena.bat` 打开图形启动器。

## 原版回放

```powershell
python arena.py replay replays/series_编号/game_0001.replay.gz
```

这会在隔离用户目录中打开原版回放界面，使用原版播放、暂停、视角和速度控制。保留包内 `runtime/` 即可加载裁判场景，无需重新运行选手代码。因进程被强制终止而结束的超时局可能没有完整原版回放，结果和日志仍会保存。

## 冻结规则

2／4／8 方各自为战，默认时代六阵营，固定三张地图；初始金币 100，基础收入 2，村庄收入 2、支援 1；经验修正 70%，迷雾开、黑幕关，最多 30 个完整回合。战斗、特质、晋升选择、视野和路径均由原版处理。失去全部领袖时淘汰该方剩余单位。

选手一次候选动作评估及其对应执行合计限 **1 秒，首次 10 秒**，包含入口模块加载；原版进程冷启动单独限 120 秒。官方 baseline 每方整回合限 60 秒。具体边界、故障和混战名次见 [sdk/RULES.md](sdk/RULES.md)。

`--seed` 传给官方 `--rng-seed`，控制启动随机源；原版默认多人战斗还生成独立的逐动作随机种子，因此**同一个启动 seed 不保证整局重跑相同**。完整随机选择保存在原版回放里。公平性通过阵营和座位轮换及足够局数实现。

## 目录

|目录／文件|用途|
|---|---|
|`arena.py`、`match.py`、`native.py`|CLI、独立原版进程、官方场景生成|
|`addons.py`|创建、验证、打包和安装原生提交物|
|`runtime/`|裁判候选动作计时、事件记录和终局，不实现游戏规则|
|`maps/`、`params.py`|固定地图与赛制参数|
|`sdk/`|中文规则、官方接口说明、交付要求和两个原生示例|
|`bots/baseline/`|本机官方 RCA baseline 的版本说明|
|`tests/`|单元测试和真实运行时集成测试|

比赛进程使用临时用户目录，不修改已有存档与附加组件。只有显式的 `install` 命令写入原版用户附加组件目录。

Windows PowerShell 静默后台测试示例：

```powershell
Start-Process -WindowStyle Hidden -FilePath python -ArgumentList @('arena.py','match','submissions/MyTeam','baseline','-n','6','-j','4') -RedirectStandardOutput test.out.log -RedirectStandardError test.err.log
```

Linux：`nohup python3 arena.py match submissions/MyTeam baseline -n 6 -j 4 >test.log 2>&1 &`。检查进程是否结束、退出码、结果和故障；启动成功不表示测试通过。

版本变化及运行边界见 [sdk/COMPATIBILITY.md](sdk/COMPATIBILITY.md)。
