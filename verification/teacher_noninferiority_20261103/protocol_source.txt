# R3 maintained-strength acceptance protocol

Date: 2026-11-03 (Asia/Shanghai).

Status: predeclared, execution NOT RUN. The user approved a five-percentage-point margin on normalized official score after the two completed repair rounds failed to establish superiority. Commit this protocol and freeze the completed runner/control implementation and all package hashes before any game starts. This document contains no new acceptance result.

## Scope and fixed candidate

The two completed scoring repairs count toward the user's two-round limit: attribute slow benefit to the attacked target, then exclude fatal outcomes from that benefit. No further teacher tuning is part of this experiment. The original superiority results remain inconclusive at their original evidence paths; they are not reinterpreted as non-inferiority results.

The candidate production source is `9118fac3628542b585a35f27d2115560057d4ddc`, also present unchanged in master `693fc42`. Its teacher source SHA256 is `ad75d870ce68fa6b489ad922fd8bb3059e29bbe7626f296e74d2b6fad828c7d4`. See [the surviving-slow repair](../verification/teacher_surviving_slow_20261103/REPORT.md) and [its native panel](../verification/teacher_strength_surviving_slow_20261103/REPORT.md).

The new experiment compares this fixed candidate with the frozen Astra lineage on native Wesnoth 1.18.8. It does not train a policy, collect learning shards, alter rule data or claim complete native semantics. Final holdout maps remain untouched.

## Control identity and symmetric native compatibility

The historical parent is `data/opponents/gpt6astra.zip`, SHA256 `2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933`. It remains read-only. The [first native panel](../verification/teacher_strength_20261103/REPORT.md) records its concrete `four.lua:311` movement assertion fault, alongside the same adapted-teacher failure. The [native ambush fixture](../verification/teacher_ambush_20261103/REPORT.md) proves that status 2005 can mean a move changed the board and revealed a Wose; the old plan must stop rather than continue or disqualify the side.

For this NI panel only, derive the control from the original archive by adding only the matching `status == 2005` / `return false` handling to its three original strategy move helpers (`duel.lua`, `four.lua`, `eight.lua`). This is the same native execution compatibility behavior already present in the candidate. Preserve every other original strategy and scoring byte; do not copy the maintained teacher's value function or other adaptations into the control. Normal package staging may rename add-on references so both bots can coexist.

The comparison therefore estimates current teacher versus original strategy/scoring with the same ambush compatibility, not current teacher versus the byte-identical historical archive. This compatibility correction is not a third teacher-improvement round. Before launch, record the immutable parent digest, compatibility patch/helper source digest, actual derived source and staged-package digests, and the focused compatibility check result. The candidate production teacher digest above must remain unchanged. Freeze the eventual runner/helper Git commit and archive digest in the prepared plan; their values do not exist at this document's planning commit and must not be guessed. Any gameplay fault still prevents acceptance; the control correction does not relax that gate.

## Estimand and decision

[The existing scorer](../learning/evaluate.py) assigns duel/team win, draw and loss scores of 3, 1 and 0, and FFA rank points divided by three. Normalize duel/team scores, differences and confidence endpoints by three; FFA is already on the 0-to-1 scale. The effect is candidate minus control, averaged within a complete rotation block, then within scenario family, then equally across the 15 scenario families.

The approved margin is `delta = 0.05` on this normalized scale. It means excluding a loss of five percentage points of average official score. It is not a five-percent relative change or necessarily a five-point change in win rate: draws and FFA ranks contribute to the score.

For each format:

```text
H0: normalized candidate-minus-control effect <= -0.05
NI pass: normalized lower endpoint of the existing 95% interval > -0.05
```

Use the existing scenario-cluster percentile bootstrap unchanged: 5,000 resamples, bootstrap seed 19, 2.5th and 97.5th percentiles. In raw score units the lower-bound thresholds are `-0.15` for duel/team and `-0.05` for FFA. Report the point estimate and both normalized interval endpoints. Do not replace the production superiority rule `CI lower > 0`, use a different confidence level, or substitute a non-significant superiority test for non-inferiority.

All three format-level NI checks must pass for the overall maintained-strength claim. Team retains the original equally weighted `baseline_partner` and `self_team` comparison. Report both contexts separately as descriptive results; they neither replace the combined result nor become post-hoc alternative pass criteria. An incomplete or faulted format cannot pass even if an available subset has a favorable interval.

## Frozen schedule and execution budget

Use [the existing evaluation schedule](../learning/schedule.py) and all 15 entries in each format's existing validation faction roster. Keep the original physical faction/seat design, complete rotations, native RCA field seats, both team contexts, fog/sharing settings and frozen validation maps (`hamlets` for duel, `loris_river` for FFA/team).

| Format | Distinct scenario families | Complete blocks | Repeats per family | Games per block | Games |
| --- | ---: | ---: | ---: | ---: | ---: |
| duel | 15 | 960 | 64 | 2 | 1920 |
| ffa4 | 15 | 300 | 20 | 4 | 1200 |
| team2v2 | 15 | 180 | 12 | 8 | 1440 |
| Total | 15 per format | 1440 | — | — | 4560 |

- Master schedule seed: `20261104`. Call the existing scheduler separately for each format with seed `20261104 + 100003 * i`, where `i` is 0/1/2 for duel/ffa4/team2v2: `20261104`, `20361107`, `20461110`. Save every actual per-block game seed in the frozen schedules. No old game result is part of this acceptance panel.
- Global concurrency: eight workers. Numerical libraries retain one thread per worker.
- Native match limit: 30 turns; action timeout one second and first-action timeout ten seconds.
- Wall-clock budget: six hours from the recorded preparation time. Freeze the absolute deadline before execution; preparation-to-launch time consumes that budget.
- Freeze all three schedules, execution source/archive identity, candidate/control packages, executable, entropy shim, rule/map identities, plan and hashes before the first game.
- Interleave formats, blocks and rotations using the existing scheduling convention. Never choose or replace a scenario/seed based on its result.

The endpoint is performance under this official 30-turn match contract. A normally returned `turn_limit` result is valid official adjudication and remains in the analysis; it is not described as natural termination. Report completion reasons, faults, missing jobs and candidate truncation separately. A process deadline, missing result or infrastructure/gameplay fault is not a draw and cannot be imputed as one. The acceptance claim does not extend to uncapped games.

## Sample-size and cost rationale

The completed 168-game panel is used only for variance and cost planning. The margin came from the user's explicit decision, not from that panel's confidence limits. From its [recorded block differences](../verification/teacher_strength_surviving_slow_20261103/panel-r3/summary.json), the normalized sample standard deviations across 12 blocks are:

| Format | Pilot SD | IID-equivalent required blocks | Rounded upward to 15 | Fixed planned blocks |
| --- | ---: | ---: | ---: | ---: |
| duel | 0.4264014327 | 945.088899 | 960 | 960 |
| ffa4 | 0.2360089648 | 289.529187 | 300 | 300 |
| team2v2 | 0.1777782710 | 164.283031 | 165 | 180 |

The planning calculation is `n = (1.96 + 1.644854)^2 * SD^2 / 0.05^2`, assuming zero true effect and independent blocks. It is a normal-approximation, 95%-power calculation for each endpoint under those assumptions, not a guarantee for the actual clustered bootstrap or for all three endpoints jointly. The pilot mean is not used to select a more favorable margin. A negative true effect would reduce power.

Repeated seeds do not create new scenario families. The actual analysis has 15 scenario clusters per format; repetitions reduce within-scenario random-outcome noise but do not remove genuine between-scenario heterogeneity. The pilot SD includes both components, which the small pilot does not estimate separately. The calculation therefore cannot certify that this panel has 95% power or will pass. Its purpose is a fixed, finite allocation that gives the highest-variance duel comparison more work while retaining every format and context.

The [measured pilot cost](../verification/teacher_strength_surviving_slow_20261103/REPORT.md), 419.681 seconds for 168 games, gives a linear estimate of `419.681 / 168 * 4560 = 11391.34` seconds, approximately 3 hours 10 minutes. Different roster entries, match lengths and host load can change that cost; the six-hour ceiling remains binding.

## Observation, stopping and reporting

During execution, inspect progress counts, elapsed time and operational faults only. Do not inspect interim win/rank/score differences or confidence intervals. Analyze once at the fixed endpoint. Do not stop early for a favorable score, extend the deadline or game count, retry failed games, replace cases, tune the teacher, or combine selected results from old panels.

If the budget expires, report the actual completed, faulted and missing counts and retain an incomplete/inconclusive acceptance result. If a required NI check does not pass, report it without changing the margin or starting another panel. A successful operational exit is not a statistical pass.

Archive commands, exact source/package identities, frozen schedules, raw results, completion reasons, counts, normalized and original superiority summaries, and elapsed cost in a new dated `verification/` directory. Preserve the earlier failed/inconclusive panels unchanged. Remove this temporary protocol document when its task is finished, after archiving the committed protocol with the resulting evidence.

## Statistical references and limits

- The [FDA's primary non-inferiority guidance, sections III.E and IV.G](https://www.fda.gov/media/78504/download), describes choosing a margin before the confirmatory results, planning from the margin and variability, and why a failed superiority experiment cannot be salvaged by choosing a margin afterward. This protocol uses those statistical principles only; clinical efficacy, placebo, assay-sensitivity and regulatory requirements are not being applied to a game.
- The [FDA's primary multiple-endpoint guidance, section III.C.1](https://www.fda.gov/media/162416/download), explains that a claim requiring success on every co-primary endpoint has no opportunity to select the favorable endpoint. The same intersection-of-tests logic applies to requiring all three formats here. It does not justify separate unadjusted claims selected after looking at the context results, nor promise joint power.
- The confidence construction and scenario grouping are the repository's existing method in [learning/evaluate.py](../learning/evaluate.py); this protocol adds no statistical framework or revised production gate. Acceptance remains limited to the frozen comparator, validation design and declared 30-turn native match rules.
