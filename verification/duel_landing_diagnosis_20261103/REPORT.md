# Native duel attack landing at b0025

The frozen adapted teacher selects a grass hex for the Elvish Shaman's entangle attack where the control selects its village. Both native evaluations enumerate 18 attack candidates, include both legal landings, and finish below the evaluation cutoff. The adapted teacher values slow more on the hex where the shaman is easier for the target to hit. On this board that difference reverses the complete candidate ranking.

## Board and method

The two original records are `panel/replays/r3-ni-panel-duel-b0025-solo-r{0,1}.replay.gz` in the Ubuntu run documented by `verification/teacher_noninferiority_20261103/REPORT.md`. Both have seed 272584090 and scenario family `5d8e9b4ca2b3f0842de5bf58981ebd5b0e784e56aa63e59158b40c3999a711ed`. The test runs the original matched opening, map and bots in native Wesnoth. At turn 4, side 2, the wrapper identifies the decision using its shaman and a legally visible cavalryman. The old teacher's own evaluation receives the live board and its accumulated decision memory. The frozen source's inner scoring loop records the candidates in enumeration order after the final score is calculated. The original simulation, ordering, move check and selection run normally. The diagnostic finishes immediately after the measured move and attack.

Command numbers are one-based `[command]` entries within `[replay]`. Command 190 is the preceding archer attack and 191 its dependent random-seed record. At the next decision the shaman is at (20,20), HP 26, with five moves and one attack. The cavalryman is at (21,18), 14/37 HP. Command 192 moves the shaman to (20,19). The original and measured traces for each role match byte for byte through command 194, including all random-seed records and checkups. The shared SHA256 of the concatenated first 191 command entries is `b74ea71ba2adda873b0b7f6763ad2dc62ad3b446ac1202e89dd3469b05d4eb5f`.

## Native scores and choices

| Frozen teacher, side 2 | Own village (21,19) | Grass (20,18) | Grass minus village | Chosen landing |
| --- | ---: | ---: | ---: | --- |
| Control, rotation 0 | 6.1914036617262 | 5.8914036617262 | −0.3000000000000 | (21,19) |
| Adapted, rotation 1 | 5.5164523103749 | 6.1389766346992 | +0.6225243243243 | (20,18) |

Grass (20,17) ties (20,18) in both traces. The adapted teacher retains the first of the tied choices under its strict improvement rule. The village is uniquely first in the control and third in adapted enumeration-stable rank. Both selected plans use Lua weapon 2, replay weapon 1, against Cavalryman-8. Both runs finish with zero faults. Native game durations are 1.3517 and 1.3560 seconds respectively.

The two landings have the same expected damage dealt (3.6), damage taken (0), kill and death probabilities (0), expected attacker HP (26), slow probability (0.84) and aggregate danger from other enemies (0). Their common combat-value term is 1.6914036617262. The village has 60% shaman defense and a direct +0.3 terrain score. Grass has 40% defense and zero direct terrain score.

The control slow benefit is 0.84 × 5 = 4.2 for both landings. For the adapted teacher, the actual target-damage input is 4.392972972973 in the village and 6.5894594594595 on grass. The target is unslowed. Its sword is 6 × 3 and its next turn has a 0.75 lawful multiplier. The target estimate includes shaman hit chance on the candidate hex and the target's HP weight, 0.7 + 0.3 × 14/37. Surviving slow benefit is 0.84 × (2 + 0.5 × target damage), which gives 3.525048648649 in the village and 4.447572972973 on grass. The resulting +0.922524324324 benefit of grass exceeds the direct 0.3 defense benefit of the village. The evidence identifies the reason for this local score reversal. Its effect on the full game and on the population strength gap remains unmeasured.

## Reproduction and evidence

The diagnostic source is `0718b005b268d49622fafa0ab9f2cdecf07ebeff`. Its git archive SHA256 is `625194be631d842f022309fd7162da018233e79f92bf0b661460a90bc4f8fb24`, equal on Windows and Ubuntu. It was extracted into `/home/tongshu/acceptance/duel_landing_trace_20261103`. The frozen native executable and entropy shim identities are checked against the panel before each invocation, as are the two original package hashes. Each summary records those four hashes, the original replay hash, source and result.

From the extracted directory, with its `.runtime/entropy.so` linked to the original panel source root's shim:

```sh
export PYTHONPATH="$PWD:$PWD/vendor/arena" SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
for variant in control adapted; do
  /home/tongshu/venv/bin/python tests/diagnose_teacher_landing.py \
    --panel /home/tongshu/acceptance/teacher_noninferiority_20261103/panel \
    --source 0718b005b268d49622fafa0ab9f2cdecf07ebeff \
    --variant "$variant" --output "$variant"
done
```

Both commands exit 0. `control.json` and `adapted.json` are copies of the summaries. `native-records.tar.gz` contains both complete outputs, staged sources, raw event traces, native replays, logs, summaries and exit codes. Its SHA256 is `b905c0a46c6c46d5d7926fd5ffd38c773e3f6695a71a1ed341f5489a576a5d35`.

An initial control diagnostic on source `07efee5091e668184ffed4e51037898fce01e236` exited 1 before producing scores. It tried to observe an adapted-only local variable in the control's strict Lua environment. The corrected tracer records the field only for the adapted scorer. The failed log is preserved as `initial-control.log`.

For a later source, `--variant challenger --challenger <add-on-root>` runs the frozen adapted opening and switches the duel/value source only at the measured decision. The same 191-command boundary must match the frozen replay before its scores are interpreted. This report covers only the two frozen inputs.