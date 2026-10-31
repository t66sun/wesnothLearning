# Native decision budget — 2026-10-31

Host: `server`, Ubuntu 24.04.5 LTS, x86_64.
Source: branch `native-candidate-cap`, commit `87205b5aedb2ac04753b4932fdb65d0734de3281`.
Wesnoth: `/home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth`, SHA-256 `33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf`, version 1.18.8.

Command, from the extracted source root:

```bash
source ~/venv/bin/activate
export WESNOTH_EXE=/home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth
PYTHONPATH=$PWD python tests/smoke_native.py --wesnoth "$WESNOTH_EXE" \
  --output runs/native_budget_87205b5 --players 2 --turns 5
```

The smoke exported `out/bot` with `mode=rule`, `package=False` and `candidate_cap=32`; the 16 MiB package validation is skipped because the three random-policy weight dumps exceed it, and native play uses the addon directory.

Result: job `smoke-2` status `complete`, `result.faults` `{}`, turns 4, winner 2, reason `last_leader`, actions 10, seconds 3.6819, coverage 10/10. `summary.json`, `game2.events.jsonl.gz`, `game2.jsonl.gz`, `config.lua` and `export.json` are the unchanged files from that run.

`RETURN` decisions in `game2.events.jsonl.gz`: 10, `elapsed_ms` values 661, 43, 386, 190, 52, 413, 378, 60, 285, 57; minimum 43, maximum 661. The first decision is the 661 ms execution; every later decision is under the frozen 1 s budget. The first `CALL` carried 10 s, all later calls 1 s.

Limits: the policy weights are randomly initialized (`torch.manual_seed(7)`) and `mode=rule`; this proves decision latency for the exported architecture, not playing strength. It is one game, not the 60-game L1 final-evaluation panel. The panel rerun is NOT RUN, and L1 remains FAIL.
