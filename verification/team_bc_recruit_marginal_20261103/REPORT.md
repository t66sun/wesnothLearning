# Recruit-type auxiliary supervision on the frozen team v10 checkpoint

**Both arms failed the complete BC gate.** The original objective produced 41/85 exact held-out recruits. Replacing the auxiliary actor group with recruit type produced 37/85. Both needed 51. The experiment also reduced held-out type matches from 47 to 44 and slot matches from 73 to 71. The result does not support adopting this objective. [Frozen plan](PLAN.md) · [Paired comparison](observed/comparison.json)

## Matched experiment

The starting checkpoint was team2v2 v10, SHA-256 `b74350699b445e63cdd11fd07f317e0d818fe3d3166d49705b1342b00336035e`, from the historical expected-damage v2 branch at `bdecbbd4f9f18fc6c1b7a01bc6ff4bce5b3e5e30`. The helper verified the branch's 48 teacher shards, manifest and checkpoint files against its recorded hash inventory. All 126 training and 85 validation recruit labels grouped exactly the same candidates under action kind and virtual actor ID. The diagnostic changes only that actor group for recruit-labelled rows. [Original branch and frozen configuration](../team_bc_branch_20261102/REPORT.md) · [Input inventory](../team_bc_branch_20261102/input_model_hashes.json) · [Diagnostic source](probe.py)

The commit shipped before fitting was `e4e54d0e5fe435c8b21360c82cc07d83964ce4f0`. The local and Ubuntu git archives matched at SHA-256 `521489ee8bcc1fa4e65e3e56c3b36dca211a1171204e818d30dde0ccaf2ec2ff`. The fresh Ubuntu directory was `/home/tongshu/acceptance/team_bc_recruit_marginal_20261103`. The command ran with one trainer thread against the recorded v2 learning package, v2 extension path and unchanged teacher-only inputs. [Launch script](run.sh)

```sh
bash verification/team_bc_recruit_marginal_20261103/run.sh
```

The two arms shared the 2,048-row training batch (seed 20261110) and 1,024-row validation batch (seed 20261101). Content hashes include legal recurrent prefixes. The original train/validation class counts were reproduced before fitting. Both arms restored identical model parameters, Adam moments and Python/Torch RNG. The swap fixture checked that the experimental grouping rewards a higher-scored alternative slot of the correct type while the original auxiliary loss stays equal. [Input and start metrics](observed/entry.json)

Each arm completed 16 epochs and 224 updates within its predeclared 600-second limit. Control took 174.07 seconds and recruit type took 172.88 seconds, including endpoint measurement. Both traversed the same ordered 896 window visits (54 unique windows) and 37,597 decisions. The ordered visit sequence SHA-256 was `6acc1a8181096dfdb13de615a1bd317a452222fdaee7cce8a3ab4239f3e6a05c`. Input file hashes matched again after fitting. The wrapper ran from 12:55:40 to 13:02:34 UTC on 2026-11-03 and exited 0. [Output log](console.log) · [Exit code](exit_code)

## Original gate and ranking counts

| Measure | Frozen v10 | Original loss, 224 updates | Recruit type, 224 updates |
| --- | ---: | ---: | ---: |
| Validation recruits exact / 85 | 34 | 41 | 37 |
| Validation recruits, correct type / 85 | 48 | 47 | 44 |
| Validation recruits, correct slot / 85 | 60 | 73 | 71 |
| Validation moves exact / 667 | 426 | 408 | 413 |
| Validation attacks exact / 141 | 56 | 68 | 64 |
| Validation end turns exact / 121 | 102 | 92 | 95 |
| All validation actions exact / 1,014 | 618 | 609 | 609 |
| Validation CE (uniform 3.57875) | 1.34341 | 1.41873 | 1.34208 |
| Training recruits exact / 126 | 54 | 73 | 76 |
| Training recruits, correct type / 126 | 75 | 85 | 86 |
| Training recruits, correct slot / 126 | 85 | 103 | 109 |
| Training moves exact / 1,285 | 872 | 972 | 997 |
| Training attacks exact / 361 | 162 | 206 | 192 |
| Complete gate | FAIL | FAIL | FAIL |

The frozen manifest sets thresholds of 40% overall, 60% recruit, 35% move and 35% attack. At v10 and both endpoints, all three classes exceed the 32-sample minimum, CE is below 85% of uniform and overall, move and attack pass. In particular, the original v10 attack count of 56/141 already passed its 35% floor. Only recruit exact fails. The shared corpus is 48/48, coverage is 11,284/11,978 (94.21%) with all class floors met, and design is 47 distinct scenarios with no missing scenario rows against a floor of 12. The four-game opening probe is nonblocking. The experiment changes no recorded game evidence. [Control endpoint](observed/control.json) · [Recruit-type endpoint](observed/recruit_type.json) · [Frozen gate](observed/entry.json)

This was one historical v2 team checkpoint and one held-out partition. Each endpoint was measured once on its in-memory model copy. No new games or ordinary BC checkpoint were produced. Current all-format readiness remains open.
