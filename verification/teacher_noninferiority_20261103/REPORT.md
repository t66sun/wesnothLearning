# R3 native teacher maintained-strength panel, 2026-11-03

**The panel returned `not_passed`.** The adapted teacher passed the predeclared 5 percentage point non-inferiority margin in FFA and team. In duel the point estimate was 3.07 points below control and the 95% interval extended to 6.09 points below control. The interval lies below zero and spans the allowed loss. R3 requires all three formats. Blocker 5 remains open.

## Frozen comparison

Candidate `9118fac3628542b585a35f27d2115560057d4ddc` includes the two completed slow-value repairs. Native Wesnoth 1.18.8 compared it with original Astra strategy and scoring plus the same native ambush handling. The runner shipped at `97d7d9ddf87948bb59781f8f68a7d9b1e3a03fe3` (source tar SHA256 `20d1c2e2120375f3ddaa8a83c347f33e17cbb682c4a4220c8a4cea9f7243f8bc`). The startup record contains the Ubuntu paths, exact prepare/run commands, built shim and package hashes. The identity manifest includes the frozen parent, change to its three move helpers, actual staged packages, executable, native rules and evaluator. [Startup and commands](STARTUP.md) · [Identities](identities.json) · [Protocol as committed before launch](protocol_source.txt) · [Frozen plan](plan.json)

The margin applies to the difference in official score, candidate minus control, on a 0–1 scale. Duel and team divide the raw 3/1/0 win/draw/loss scale by three. FFA uses official rank points divided by three. The existing evaluator averaged complete rotations within each scenario family and weighted the 15 families equally. Its 95% interval used 5,000 scenario-cluster bootstrap resamples with seed 19. Each normalized lower endpoint had to exceed −0.05. The same official 30-turn contract applied throughout. Only validation maps were used.

## Endpoint

| Format | Games | Blocks × games | Families | Difference in percentage points | 95% interval in points | Maintained strength |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| Duel | 1,920 | 960 × 2 | 15 | −3.073 | [−6.094, −0.729] | Not passed |
| FFA | 1,200 | 300 × 4 | 15 | +1.056 | [−4.361, +6.792] | Passed |
| Team | 1,440 | 180 × 8 | 15 | 0.000 | [−3.403, +2.986] | Passed |

The two team contexts had 720 games each. Baseline partner had a normalized difference of +0.556 percentage points [−5.556, +6.250], self-team −0.556 [−1.944, +0.556]. The prespecified team result is their equal-weight combination.

| Original superiority comparison | Candidate mean | Control mean | Raw difference | Raw 95% interval | Status |
| --- | ---: | ---: | ---: | --- | --- |
| Duel | 1.404167 | 1.496354 | −0.092188 | [−0.182813, −0.021875] | not_passed |
| FFA | 0.568472 | 0.557917 | +0.010556 | [−0.043611, +0.067917] | inconclusive |
| Team | 1.304167 | 1.304167 | 0.000000 | [−0.102083, +0.089583] | inconclusive |

All 4,560 schedule IDs occurred exactly once in the job log and once in the results file. The two records matched for each ID. The planned seat rotations, paired seeds, 64/20/12 repeats per family and both team contexts were complete. There were zero missing blocks, fault games or candidate truncations. [Full-precision endpoint](summary.json)

| Format | Natural ending | Official 30-turn adjudication |
| --- | ---: | ---: |
| Duel | 1,729 last leader | 191 |
| FFA | 748 last leader | 452 |
| Team | 876 last team | 564 |
| All | 3,353 | 1,207 |

Eight workers ran from 07:26:48 to the endpoint summary at 09:57:54 Asia/Shanghai, within the 13:25:35 deadline. Start to summary took 9,066.60 seconds. The game broker recorded 9,065.25 seconds and 1,810.87 games per hour. The process exited 0. There was one panel execution and one endpoint analysis.

## Reading the duel result

The candidate won 835 games, lost 894 and drew 191. All 191 turn-limit outcomes were draws. Every family contributed 128 games. Five matchups containing Rebels account for the net 59 losses. Contributions below use the common 1,920-game denominator.

| Rebels opponent | Candidate wins minus losses | Contribution to duel difference (percentage points) |
| --- | ---: | ---: |
| Loyalists | −24 | −1.2500 |
| Undead | −15 | −0.7813 |
| Drakes | −10 | −0.5208 |
| Northerners | −6 | −0.3125 |
| Knalgan | −4 | −0.2083 |
| Other ten families combined (no Rebels) | 0 | 0.0000 |

This is a post-endpoint breakdown. In all 640 same-seed rotations without Rebels, both games in the pair produced the same physical winner or draw. In the 320 Rebels rotations, 122 pairs differed. The candidate played both factions across each rotation.

One inspectable pair on Hamlets is `r3-ni-panel-duel-b0025-solo-r{0,1}`, seed `272584090`, Loyalists/Rebels family `5d8e9b4ca2b3f0842de5bf58981ebd5b0e784e56aa63e59158b40c3999a711ed`. The first 192 WML replay commands match. At turn 4, both versions moved side 2's Elvish Shaman from (20,20) to (20,19). At command 193 the control finished on its village (21,19) and the candidate on grass (20,18). At command 194 both used the same weapon against the same Cavalryman at (21,18), with no retaliation. The adapted teacher lost both seat rotations, on turns 23 and 22 respectively. These two files preserve the shared board before the move. [Rotation 0](duel-b0025/r3-ni-panel-duel-b0025-solo-r0.replay.gz) · [Rotation 1](duel-b0025/r3-ni-panel-duel-b0025-solo-r1.replay.gz)

The frozen scoring terms explain why to inspect the landing hex. The Shaman's defense was 60% in the village and 40% on grass. The target had 14/37 HP, a 6×3 sword and a next-turn alignment factor of 0.75. With zero blade resistance, the adapted scorer estimated target damage as `6 × 3 × (1 − defense) × 0.75 × (0.7 + 0.3 × 14/37)`, using defense as a fraction. This gives 4.393 on the village and 6.589 on grass. Entangle dealt 3 per hit with two independent 60% chances. Its slow probability was 0.84 and its kill probability zero on both hexes. [Duel scoring source at the shipped commit](https://github.com/t66sun/wesnothLearning/blob/97d7d9ddf87948bb59781f8f68a7d9b1e3a03fe3/learning/teachers/gpt6astra/lua/duel.lua#L68-L85) · [Slow benefit](https://github.com/t66sun/wesnothLearning/blob/97d7d9ddf87948bb59781f8f68a7d9b1e3a03fe3/learning/teachers/gpt6astra/lua/value.lua#L16-L28)

| Reconstructed terms only | Village | Grass | Grass minus village |
| --- | ---: | ---: | ---: |
| Control slow benefit + landing defense | 4.5000 | 4.2000 | −0.3000 |
| Adapted slow benefit + landing defense | 3.8250 | 4.4476 | +0.6225 |

The direct landing bonus was +0.30 in the village and zero on grass. Control awarded `0.84 × 5` for slow on either hex. The adapted teacher used `0.84 × (0.5 × target_damage + 2)`, crediting the higher estimated damage on grass. Candidate enumeration, risk from other enemies and their effect on the final scores are still unknown. This partial score reversal supplies a testable explanation for the first move difference.

For a fixed-board diagnosis, use the legal side-2 position immediately after command 191, before the first movement step. Compare which landing hexes were considered, their defensive value, threat and slow benefit. The archived actions identify the first divergence. The saved games give no candidate scores or counterfactual outcome for choosing the other hex.

## Archived records

The Git evidence bundle contains the full schedule, every job and result, summary, throughput, run log, exit code, startup identities, plan and both staged packages. It is 2,429,935 bytes, SHA256 `c5a72748e25103d122b96dd4c8f5ddd406ee1c9f49e38ccd1fd9b72616b94df3`. [Panel records](panel-records.tar.gz)

| Uncompressed file | SHA256 |
| --- | --- |
| `schedule.json` | `1343852a01d6ea62152aae6f38ae4cb08fef15d422c286ee38a1e7d939cf8987` |
| `jobs.jsonl` | `dd219b062d2a5c1d55ba9d5183a6a5f659e345c4c770a071d01043d5c1c0d6f9` |
| `results.json` | `efa3dba1afb816b5becdb06026ddf936f6c9985f8884590d868925fa5715e050` |
| `summary.json` | `8d56d7df50d9b53d83e824ddcb8b5d155351818d4f7c1966cd6be129f0e7d44d` |

The complete panel, including all replays and arena event logs, is preserved in the Ubuntu directory named in the plan. The full tarball is 314,445,653 bytes, with the same SHA256 on Ubuntu and in the local workspace: `4a74682a458f42f0703da87a9d6ccbd88d668969abe0a5faefc858f76fb5cb4c`. It is available on `cpuServer` at `/home/tongshu/acceptance/teacher_noninferiority_20261103-panel.tar.gz` and locally beside this report under `completed/teacher_noninferiority_20261103-panel.tar.gz`. The archived 6,014,278,001-byte source directory is retained on Ubuntu.

```sh
cd /home/tongshu/acceptance
tar -czf teacher_noninferiority_20261103-panel.tar.gz -C teacher_noninferiority_20261103 panel
sha256sum teacher_noninferiority_20261103-panel.tar.gz
```

The fixed-board combat and teacher checks cited in blocker 5 remain accepted for their stated cases. The open condition is maintained duel strength. The two completed repairs have exhausted the agreed superiority attempts, and the prospective maintained-strength experiment has reached its endpoint. A further candidate decision needs its own scope and plan.
