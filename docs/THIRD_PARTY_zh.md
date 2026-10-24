# 来源与许可

> 语言：[English](THIRD_PARTY.md) | 中文

`vendor/arena/` 来自上级只读的 WesnothArena 原生 v2 SDK，保留其 MIT LICENSE 与第三方说明。训练工程与团队扩展以同一 MIT 许可提供。

`data/opponents/` 下的 zip 是用户指定的参考选手原始包，按原样保存；每次实验再次复制并冻结哈希。选手源码和权重的许可由各提交方说明。

本工程不打包 Wesnoth 游戏本体或官方 RCA 实现。安装脚本从官方发布地址下载并校验 1.18.8 源码，在用户服务器本地构建；官方组件遵循其各自许可。

没有复制参考目录 `dev/upstream` 中第三方训练框架或模型。
