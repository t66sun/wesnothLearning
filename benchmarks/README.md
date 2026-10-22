# V5 引擎基准合同

本目录保存固定基准合同和 Linux 真实资源 runner。性能结果以实际输出目录为准。
`learning.benchmark.build_manifest()` 生成确定性的原版/lite 成对清单。
每个赛制分别覆盖冷启动/常驻热运行、同工作量/端到端、常规/密集场景，
每组 30 个完整座位轮换块；单游戏 worker、CPU 推理、单线程是主验收。
4/8 worker 吞吐是后续独立结果，不能替代单 worker 门槛。

## 冻结与执行

`freeze_artifacts(paths)` 输入名称到真实文件路径的映射，逐个计算 SHA256。
主验收要求 `native_executable`、`lite_rules`、`astra`、`v4_duel`、`v4_ffa4`、
`v4_team2v2` 六个工件。把返回值交给 `build_manifest(artifacts)` 后写入
manifest.json；缺工件时报告保持 `inconclusive`。历史 V4 工件只读取。

清单中的地图、规则、种子、阵营轮换、座位、回合上限必须由实际 runner 消费。
等工作量 runner 使用固定局面/脚本/命中序列，并把其哈希与实际
动作数、回合数记录为 `work_signature`、`actions`、`turns`。
完整对战 RNG 不同导致较早结束时，端到端的节省不会被当作规则核加速。

`run_benchmarks({'native': native_runner, 'lite': lite_runner}, manifest, directory)`
是显式执行的入口。每个 runner 接收一条 workload，返回以下真实 raw 字段；
入口交替执行两种引擎，追加写 raw.jsonl，最终写 report.json。
仅有后端适配器而没有真实测量器时，不能调用该入口伪造资源数字。

## raw.jsonl 字段

每行由入口追加 `engine`、`manifest_id`、`workload_id`，runner 提供：

- `host_id`、`cpu_quota`、`workers=1`、`threads=1`、`inference="cpu"`。
- `cache_aligned=true`：真实证明两边缓存状态符合 cold/hot 合同。
- `wall_seconds`、`cpu_core_seconds`、`startup_seconds`，单位秒。
- `cpu_scope="process_tree_including_coordinator"`：CPU 累计覆盖游戏、宿主、
  推理与协调进程；短命子进程退出前后的 CPU 也必须捕获。
- `peak_rss_bytes`、`peak_pss_bytes`、`disk_bytes`，单位字节。
  PSS 是共享内存分摊后的实际测量；平台不能测量时写 null，不能拿 RSS 替代。
- `actions`、`turns`、`terminal_reason`、`faults`、`work_signature`。
- `components_seconds` 包含 `rules`、`visibility_pathfinding`、`candidates`、
  `teacher`、`inference`、`serialization`、`logging` 七项真实分项时间。
  无法拆分的项写 null，报告单独列出诊断缺口；不据此抹掉已实测的资源倍率。

`benchmark_report(raw_samples, manifest)` 不启动引擎，按赛制/缓存/工作量/
密度分组报告双方各资源 p50/p95/总量，及完整轮换块的 wall/CPU 倍率和
按块 bootstrap 95% 区间。缺座位、故障、不同主机/配额、工作量不等、缺资源
都排除并保留原因。原版/lite wall 和 CPU 分别至少 5 倍；PSS 5 倍目标独立报告。

`pipeline_report(native_equivalent, measured_pipeline)` 单独比较包含原版审计
及协调成本的实测总 wall/CPU；需要相同 `work_signature`。
仅纯 lite 达标时，含审计流水线仍为 `inconclusive`，不能用理论公式替代实测。

## Ubuntu 真实 runner

依赖现有 Python 环境、release `_engine_lite`、原版 Wesnoth 1.18.8 和可读取的
`/proc/*/smaps_rollup`，不新增第三方依赖。先在项目根目录跑最小成对实例：

```bash
python -m learning.benchmark_runner --executable "$WESNOTH_EXE" \
  --output verification/perf-smoke --formats duel --caches cold \
  --modes equal_work --densities regular --blocks 1 --seats 1 \
  --script-turns 1 --max-decisions 4
```

需要完整样本时移除格式/缓存/模式/密度/座位限制，指定 `--blocks 30`。
每个输出目录只能写一次；`raw.jsonl` 逐样本落盘，故障不会被转成成功的 0。
`manifest.json` 绑定原版、规则和 Astra 哈希。此 runner 比较纯 Astra，故不要求
无关的 V4 学生权重；学生推理性能须在真实小闭环另测。

- 每种引擎启动独立单 worker，限制 BLAS/OpenMP 单线程和 CPU 推理。原版子进程
  跟随计费。cold 含导入、建宿主和关闭；hot 先在同一个常驻宿主完成一次
  observe/legal/decision，再开始计时。两者均不清理操作系统页缓存，报告明确记录。
- `equal_work` 对同一 GameSpec 执行 observe/legal/decision/end_turn 固定脚本，
  不发生战斗，命中序列为空；签名包括完整初态和实际动作/回合。普通局面为
  arena2/arena4，密集局面在每方出生点附近额外放置 8 个 Elvish Fighter。
  这项结果限于该脚本，不能冒称战斗性能。
- `end_to_end` 调用共同 Lua 的真实 Astra 决策并执行。记录实际动作数、回合和
  终止原因；`decision_limit` 表示人为预算截断，不能作为完整对局结论。
- Linux `getrusage` 归集退出子进程，常驻子进程的热区间 CPU 由 `/proc/stat`
  计数补齐；协调器自身 CPU 同时计入。每 20 ms 采样实际进程树和协调器 RSS/PSS，
  峰值属于采样峰值。`disk_bytes` 仅表示留存的基准文件字节，明确不包含已删临时文件。
- `operation_seconds` 提供 observe/legal/decision/execute/serialization 边界的
  实测耗时；共同 decision 尚未拆开的分项保持 null。纯 Astra 的学生 inference
  为 0，因为本运行没有学生模型前向。
- `observed.json` 展示完整轮换块的实测倍率及可用的 bootstrap 区间；不足 30 块
  仍可查看数字。`acceptance.json` 保留至少 30 完整块、相同主机/配额/工作量、
  wall 和 CPU 各 5 倍的验收标准。两者用途不同，不能把最小实例当作通过验收。
