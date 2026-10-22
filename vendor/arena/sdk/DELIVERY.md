# 交付与安装

最终只交一个 `<team>.zip`，由 SDK 生成。它本身就是原版附加组件，不包含 exe、Python、外部运行服务或编译依赖。

```text
MyTeam.zip
└── MyTeam/
    ├── _main.cfg       # 原版模组注册
    ├── ai.cfg          # 官方 AI 配置
    ├── arena.json      # 比赛发现元数据，原版忽略
    └── lua/
        ├── bot.lua    # CA 入口
        └── ...        # 可选的其他 Lua 模块
```

队名 1–40 个 ASCII 字母、数字、下划线，以字母开头，不得用保留名。目录名、`arena.json` 的 id 和 SDK 生成的 WML 引用必须一致。使用 `arena.py new` 创建，改名请重新创建组件并迁移 Lua，避免引用错误。

只允许固定生成的三份配置、`lua/` 下 `.lua` 文件，以及可选 `README.md`、`LICENSE`。最大解压后体积 16 MiB，zip 最多 512 个条目，不允许符号链接、重复路径或目录穿越。注册配置固定是为了禁止把比赛规则事件夹带进提交物；策略可在 Lua 中自行组织。

```powershell
python arena.py new MyTeam
python arena.py validate submissions/MyTeam
python arena.py match submissions/MyTeam baseline -n 6 -j 4
python arena.py ffa submissions/MyTeam baseline baseline baseline -n 4 -j 4
python arena.py pack submissions/MyTeam --output MyTeam.zip
python arena.py validate MyTeam.zip
```

打包命令拒绝覆盖已有 zip，保留最佳版本后再选择新输出名。正式比赛直接接受目录或 zip，不需要先全局安装。

安装进原版：`python arena.py install MyTeam.zip`。或手动将 zip 顶层 `MyTeam/` 解压到原版用户目录 `data/add-ons/`。重启游戏，在本地多人游戏创建界面启用 **Arena AI: MyTeam** 模组，再为电脑阵营选择同名 AI。它不依赖本 SDK 的 `runtime/`，不需要外部启动器。

普通游戏中的地图、时代和回合设置由房主决定；比赛只保证冻结场景。附加组件格式可安装不代表你的策略能适应所有时代与地图。
