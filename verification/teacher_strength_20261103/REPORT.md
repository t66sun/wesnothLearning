# Native teacher strength panel — 2026-11-03

The full predeclared R3 panel ran on Ubuntu `cpuServer`. All 168 jobs returned `complete`, but one FFA game contains faults from both teachers. The unchanged comparison is inconclusive in all three formats. Item 5 remains OPEN; this is not a strength or transfer acceptance.

## Frozen scope and identity

- Source: `a5f8be0bd4a894385d9a86c9f26c5424c3a87a18`, shipped as `git archive --format=tar`, SHA256 `4daf890b0b9218aacd9157d453fe0e373c30889c0d4f00197c1c96ba3fa068d0`.
- Fresh source directory: `/home/tongshu/acceptance/teacher_strength_20261103`; output: its `panel/` directory. Python: `/home/tongshu/venv/bin/python`.
- Teacher: `probabilistic_combat_v6`, source `d0eb8d922b0c5b8092863ff712b9f2b4df097ac3653d90432c5d2d906aa87a38`; frozen parent `2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933`.
- Native Wesnoth 1.18.8 executable: `33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf`; freshly built entropy shim: `f12d763303445aa437de06d0dba129dc923e3d81fd1fc82d72b8e331916480cf`.
- Default captured rules file: `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`. These games execute native rules, not the Lite rules file. Full artifact hashes are in `panel/identities.json`.
- Seed `20261103`; 12 blocks and 12 distinct initial scenario families per format; 24 duel, 48 FFA, 96 team games. All seat rotations and both `baseline_partner`/`self_team` contexts retained.
- Existing validation maps: `hamlets` for duel and `loris_river` for four-player games. Final holdout untouched. 30-turn cap, 1-second ordinary/10-second first-call timeout, eight workers, six-hour deadline fixed before execution.
- Schedule SHA256 `c07c32a2abf902740b961d2a4cc522c2c299d405a440e89afc61e5ed81e82a8d`. No learning configuration or shard destination appears in any job. No collection, optimizer updates or training ran.

## Commands and results

After extracting the archive, link `data/rules/1.18.8-combat-filtered` to `/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered` and the historical map directory `data/rules/1.18.8` to `/home/tongshu/myDev/wesnothLearning/WesnothLearning/data/rules/1.18.8`. Both input trees remain read-only.

From the fresh source root:

```sh
cc -O2 -fPIC -shared -o .runtime/entropy.so vendor/arena/entropy.c -ldl
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
/home/tongshu/venv/bin/python tests/acceptance_teacher_strength.py prepare \
  --root /home/tongshu/acceptance/teacher_strength_20261103 \
  --output /home/tongshu/acceptance/teacher_strength_20261103/panel \
  --wesnoth /home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth \
  --source-commit a5f8be0bd4a894385d9a86c9f26c5424c3a87a18
/home/tongshu/venv/bin/python tests/acceptance_teacher_strength.py run \
  --output /home/tongshu/acceptance/teacher_strength_20261103/panel > panel/run.log 2>&1
```

Build, prepare and runner exit codes were zero. This means the runner completed, not that the comparison passed. `jobs.throughput.jsonl` records 414.488 seconds for the 168 games. No job was retried or replaced.

| Format | Complete jobs | Valid blocks/families | Fault games | Turn-limit games | Adapted minus frozen | 95% cluster interval | Status |
| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| duel | 24/24 | 12/12 | 0 | 2 | 0 | [-0.75, 0.75] | inconclusive |
| ffa4 | 48/48 | 11/12 | 1 | 22 | 0.011364 | [-0.098485, 0.151515] | inconclusive |
| team2v2 | 96/96 | 12/12 | 0 | 28 | -0.0625 | [-0.4375, 0.34375] | inconclusive |

Scores use the evaluator's existing 3/1/0 win/draw/loss scale for duel/team and existing FFA rank scale. `comparisons(..., min_blocks=12, min_distinct=12)` and its 5,000-resample clustered interval are unchanged. CI lower bound above zero is the existing superiority gate; crossing zero is not proof of non-inferiority.

`complete` is driver completion. The 52 `result.reason=turn_limit` games are reported separately from `truncated`, which counts candidate-generation truncations and is zero because these jobs contain no learning rows. The evaluator counts turn-limit outcomes under its existing scoring. TEST R3's stronger restriction on truncated strength evidence is not silently relaxed.

## Observed failure

`r3-panel-ffa4-b0001-solo-r0` records:

- Adapted side 1, turn 7: `~add-ons/astra_adapted/lua/four.lua:314: assertion failed!`.
- Frozen side 2, turn 21: `~add-ons/astra_frozen/lua/four.lua:311: assertion failed!`.

Both are the inherited assertion on `ai.move`/`ai.move_full(...).ok`. Replay inspection places each failed move next to a forest Wose: adapted at `(3,7)` beside `(2,6)`, frozen at `(17,10)` beside `(16,9)`. Native 1.18.8 represents ambush interruption as error status 2005 even when movement occurred. The original log does not record the move result status, so a fixed native fixture must confirm that exact code before accepting a repair. Neither a timeout nor a strength deficit is established by these assertions.

## Evidence and limits

`panel.tar.gz` preserves the entire original panel, including packages, plans, all replay/event/log files, results and summaries. SHA256: `e2e3b553ab232bc9852fc61afa7f28de76a4eff00820c6315d4291b581cea0d9`. The extracted JSON files beside this report are byte-identical copies for review. The full original directory remains on the Ubuntu host.

Earlier combat, weapon and fixed-board evidence is reused at its original paths; the old expected-damage R3 smoke is not mixed into this v6 panel. No Windows tests ran. No production scoring, rule, schedule or acceptance threshold changed. A later execution repair needs its own source identity and evidence; this failed panel remains unchanged.
