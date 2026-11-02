# Native teacher panel after ambush repair — 2026-11-03

The unchanged 168-game R3 design completes with zero faults after the teacher ambush repair. Each format has all 12 rotation blocks and 12 distinct initial scenario families. All three strength comparisons remain **inconclusive**, so blocker 5 and TEST R3 remain open. A complete operational panel is not proof of maintained or improved strength.

## Identity and procedure

- Production/runner source: `c4907460eb157d34acbadbb6b23d4b02b45e1ced`; git archive SHA256 `20ced4fbd896230a03f18bb51ee2224a7b58854256a4288d38310ffb9e4176ed`.
- The archive was extracted into the fresh Ubuntu directory `/home/tongshu/acceptance/teacher_ambush_fixed_20261103`. This panel reuses that exact source and entropy build after the fixed native ambush check. Output is a new `panel-r3/` directory; prior evidence is untouched.
- Teacher profile `probabilistic_combat_v6`, source SHA256 `24aa546bbcce6670b0baef8751730d64c229b37cfe608d6cc59fd3e4c211eb98`. The frozen opponent package remains `2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933`.
- Native Wesnoth 1.18.8 SHA256 `33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf`; entropy shim `f12d763303445aa437de06d0dba129dc923e3d81fd1fc82d72b8e331916480cf`; captured rules file `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`. Games execute native rules. Full hashes: `panel-r3/identities.json`.
- Seed `20261103`, 24 duel / 48 FFA / 96 team games, eight workers, 30-turn cap, 1/10-second ordinary/first-call limits and six-hour budget. Both team contexts remain. No shard or learning tasks; final holdout unused.
- Before execution, the old and new schedules were compared by job ID, seed, factions, teams, turn cap, entire map, scenario family, call timeouts, role sides, context, partition and bot package basename: `old_jobs 168 new_jobs 168 identical_frozen_design True`. Only source/package identities, output paths and the new execution deadline change. Schedule SHA256 `6b840f86957f616fef050daf7118f35b8ed9d47e4d550a9f41dd5929aa78e520`.

From the extracted source root, after linking the same read-only rule/map directories used by the initial panel:

```sh
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
/home/tongshu/venv/bin/python tests/acceptance_teacher_strength.py prepare \
  --root /home/tongshu/acceptance/teacher_ambush_fixed_20261103 \
  --output /home/tongshu/acceptance/teacher_ambush_fixed_20261103/panel-r3 \
  --wesnoth /home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth \
  --source-commit c4907460eb157d34acbadbb6b23d4b02b45e1ced
/home/tongshu/venv/bin/python tests/acceptance_teacher_strength.py run \
  --output /home/tongshu/acceptance/teacher_ambush_fixed_20261103/panel-r3 > panel-r3/run.log 2>&1
```

Prepare and run both exit 0. The game batch takes 418.005 seconds. This is one complete post-change panel, not retries of selected outcomes. Scoring, gates, source rules, seeds and opponent were not tuned to obtain this result.

## Results

| Format | Complete / planned | Valid blocks / families | Faults | Turn-limit outcomes | Adapted minus frozen | 95% cluster interval | Existing status |
| --- | ---: | --- | ---: | ---: | ---: | --- | --- |
| duel | 24/24 | 12 / 12 | 0 | 2 | 0 | [-0.75, 0.75] | inconclusive |
| ffa4 | 48/48 | 12 / 12 | 0 | 23 | -0.003472 | [-0.107639, 0.125] | inconclusive |
| team2v2 | 96/96 | 12 / 12 | 0 | 28 | -0.0625 | [-0.4375, 0.34375] | inconclusive |

The original failed game `r3-panel-ffa4-b0001-solo-r0` now completes without either teacher fault and ends at the turn limit. The whole FFA block is consequently eligible. The unchanged evaluator requires a CI lower bound above zero for `passed`; none passes. Intervals use its existing 5,000 resamples and scenario-family clustering. Raw duel/team scores use 3/1/0; FFA uses the existing rank scale.

The 53 turn-limit outcomes are explicit. Candidate `truncated` counters are zero and do not establish natural game termination. TEST R3's statement that truncated strength evidence stays inconclusive is preserved. No missing blocks or infrastructure errors occurred.

## Evidence and remaining boundary

- Full raw panel, including every replay/event/log and both staged packages: `panel.tar.gz`, SHA256 `1921dc3331765934c73ebb8cfb0d3ebb32b8ff3ee8057c3ab34cfcbe938c193e`. Local and remote hashes match. The adjacent JSON files are unchanged extracts for review.
- Initial failed panel: `verification/teacher_strength_20261103/REPORT.md`.
- Ambush root cause, failing regression and passing fixed native execution: `verification/teacher_ambush_20261103/REPORT.md`.
- Unchanged combat and 18 fixed legal-board checks reuse their original accepted evidence. No Windows checks, training, collection or parameter tuning ran.

The remaining problem is strength acceptance, not an unexecuted panel or the repaired ambush fault. The current comparison implements superiority, while the prose also names maintained strength without a non-inferiority margin. This report does not invent such a margin, relabel inconclusive as passing, change the turn cap or append seeds until a win. Any different statistical target or independent teacher-improvement experiment needs a predeclared design and must keep the final holdout reserve untouched.
