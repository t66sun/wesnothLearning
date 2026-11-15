# PPO score gain over qualified v38 BC

On cpuServer, all **720 Lite duels** reached the official terminal state with zero faults. Greedy PPO averaged **41.73%** against frozen Astra, and shared v38 BC scored **41.48%**. The difference was **+0.25 percentage points** (crossed paired 95% interval **[−7.84, +8.40] pp**). The useful-gain result is inconclusive. [Execution issue](https://github.com/t66sun/wesnothLearning/issues/349) · [Frozen protocol and command](../ppo_vs_bc_20261115/REPORT.md)

## Paired scores

| Board | v38 BC | PPO 202611081 | PPO 202611082 | PPO 202611083 | Mean PPO − BC (pp) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fallenstar Lake | 33.89% | 38.89% | 41.11% | 41.67% | +6.67 |
| Sulla's Ruins | 42.78% | 31.11% | 36.67% | 47.22% | −4.44 |
| Ur-Thorodor | 47.78% | 37.78% | 48.33% | 52.78% | −1.48 |
| Equal-weight total | 41.48% | 35.93% | 42.04% | 47.22% | +0.25 |
| PPO − BC (pp) | | −5.56 | +0.56 | +5.74 | +0.25 |

Each map and role had 60 games. The last column in the next table counts the official round-30 draws.

| Board | Role | Wins | Draws | Losses | Round cap |
| --- | --- | ---: | ---: | ---: | ---: |
| Fallenstar Lake | v38 BC | 9 | 34 | 17 | 34 |
| Fallenstar Lake | 202611081 | 14 | 28 | 18 | 28 |
| Fallenstar Lake | 202611082 | 15 | 29 | 16 | 29 |
| Fallenstar Lake | 202611083 | 12 | 39 | 9 | 39 |
| Sulla's Ruins | v38 BC | 21 | 14 | 25 | 14 |
| Sulla's Ruins | 202611081 | 14 | 14 | 32 | 14 |
| Sulla's Ruins | 202611082 | 17 | 15 | 28 | 15 |
| Sulla's Ruins | 202611083 | 24 | 13 | 23 | 13 |
| Ur-Thorodor | v38 BC | 26 | 8 | 26 | 8 |
| Ur-Thorodor | 202611081 | 21 | 5 | 34 | 5 |
| Ur-Thorodor | 202611082 | 26 | 9 | 25 | 9 |
| Ur-Thorodor | 202611083 | 29 | 8 | 23 | 8 |

The independent integer recount joined all 720 job and reply IDs exactly once across 90 scenario blocks and 180 shared BC slots. It used 3/1/0 game points, paired the learner seats, and gave each fixed map and PPO training history equal weight. The raw paired gain and 95% limits were 4/1620 and [-127, 136]/1620. The 10,000-draw crossed bootstrap reused the sampled scenario blocks across all roles with seed 2026111699. The frozen gate requires a gain of at least +5 pp and a 95% lower bound above zero. A 95% upper bound below +5 pp excludes the useful gain.

These estimates cover Lite score against frozen Astra on these three layouts for the three archived PPO histories of the same v38 initializer. The run started zero training updates.

## Execution and evidence

The run started at 2026-11-15 16:36:28.327 and finished at 2026-11-15 17:01:00.347 (Asia/Shanghai). The total was **1472.020 seconds** of the 7,200-second allocation. The panel used 1469.795 seconds of its 5,400-second cap. The recount and archiving used 1.325 seconds of the final 900-second allocation. Both stages exited with code 0. Eight Ubuntu workers used the exact frozen schedule with one runtime deadline bound into each job.

- Launch SHA-256 `3ff17a173aa6af898aead3564d8d466e5ffa7dcdec9481125c01e47130c7da50`. [Launch and role fingerprints](../ppo_vs_bc_20261115/launch.json)
- Schedule decompressed SHA-256 `ebd3b3c16273f98919a1688e5e38168eb2c123821ebc1e2456625612d7549fe0`. [Frozen schedule](../ppo_vs_bc_20261115/schedule.json.gz)
- The archive contains the executed schedule, all raw replies, launch and panel timing, and the original score audit. The archive SHA-256 is `e79feb67e29ffea3b9f96846991ed6ae56eae8c2b127a9215bc84a711e2f56b1`. The reply stream SHA-256 is `c2305a8a30c48f4be85680454098aca99755e2b2bf91e2bc414d55bc12044cdd`. [Original metadata and raw replies](raw-metadata.tar.gz)
- Score audit SHA-256 `69f5834dee3773a509f15903c53ff752e334cbb94156bbf5c53983bd77d5681d`. [Machine-readable score and verdict](audit-result.json)
- The review checked archive members against the live output, recomputed the frozen estimate and interval from the archived replies, and checked role point totals directly from winners and learner seats. [Read-only archive review](review.json) · [Audit timing](audit-exit.json) · [Final run timing](run-exit.json)

Reproduce the recount from the recorded Python environment and historical source in the frozen protocol. Use the shipped Git adapter commit d935d5c5e2a50b49e3b2e9a7e3f6a35ea7a0275a and the archived executed schedule.

```bash
work=$(mktemp -d)
tar -xzf /path/to/raw-metadata.tar.gz -C "$work" runtime-schedule.json results.jsonl
"$python" - "$scripts" "$work" <<'PY'
import json
from pathlib import Path
import sys
sys.path.insert(0, sys.argv[1])
from panel import recount
p = Path(sys.argv[2])
jobs = json.loads((p/'runtime-schedule.json').read_bytes())
with (p/'results.jsonl').open(encoding='utf-8') as raw:
    print(json.dumps(recount(jobs, [json.loads(line) for line in raw]), indent=2))
PY
```
