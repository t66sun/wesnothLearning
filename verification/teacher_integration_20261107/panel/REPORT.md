# Bounded mixed-teacher integration panel

The default activation gate did not pass. The default remains `astra`; `mixed-20261107` is available only by explicit selection. No formal corpus collection, optimizer, BC qualification or strength experiment ran.

The fixed 48-task plan ran once on Ubuntu with eight workers and a one-hour deadline. All 48 tasks returned in **485.556 seconds (8m05.6s)**: **36 complete, 12 infrastructure errors, zero hard timeouts**. All 24 PPO/DAgger jobs and 12 Lite BC jobs completed. There were **333 teacher queries, 312 valid stored DAgger labels**, no query failures and no row-identity/history audit errors in the completed jobs. The combined original-teacher and DAgger audit counted **1,487 valid supervised labels**. Per-hour rates below divide by the full panel wall time; they are observed throughput, not an isolated engine benchmark.

## Frozen design and identities

- Game source: `1a87e9d883813a355b316edb0a53cb086b90622d`.
- Exact teacher ZIP: `6b461de4e99303321b0119a7b88babd575c2d786500b28da4cb45d3c2bdabdb3`.
- Duel: `clean_fortified_pruned`; FFA: maintained Astra; 2v2: `clean_fortified_pvs`.
- Four BC and four PPO/DAgger jobs per backend/format, full focal-seat coverage, existing train-map/scenario scheduling and 30-turn task. Six-faction scheduling is covered by the fixed role tests.
- Three fixed untrained sample-mode student models, seed 20261107 plus format index; the same weights serve both backends. No optimizer is constructed. Historical/current student slots use these fixture weights while retaining the production pool/teammate schedule.
- [Manifest](manifest.json) pins executable/backend identities and student files; [schedule](jobs.json) pins all tasks, seeds, roles and deadlines.

## Results

BC coverage uses the existing exact-match gate, including its current overall denominator. PPO student actions never inflate teacher coverage. Required: >=90% overall; recruit/move/attack each >=80% and nonempty. Native BC coverage is unavailable because those jobs failed.

| Backend/format | Complete | Overall | Recruit | Move | Attack | Valid/query | Query p95 ms | Valid supervision | Labels/hour | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| native/duel | 4/8 | unavailable | unavailable | unavailable | unavailable | 39/42 | 486.0 | 39 | 289.2 | not passed |
| native/ffa4 | 4/8 | unavailable | unavailable | unavailable | unavailable | 53/54 | 32.0 | 53 | 393.0 | not passed |
| native/team2v2 | 4/8 | unavailable | unavailable | unavailable | unavailable | 42/50 | 705.0 | 42 | 311.4 | not passed |
| lite/duel | 8/8 | 77.41% | 59.52% | 70.35% | 87.74% | 41/45 | 550.5 | 346 | 2565.3 | not passed |
| lite/ffa4 | 8/8 | 91.84% | 80.65% | 93.51% | 89.45% | 98/102 | 19.9 | 728 | 5397.5 | passed |
| lite/team2v2 | 8/8 | 68.77% | 90.24% | 42.53% | 93.90% | 39/40 | 701.8 | 279 | 2068.6 | not passed |

Only Lite FFA passes its cell gate. Lite duel misses recruitment and movement coverage; Lite 2v2 misses movement coverage. The largest miss counts are movement destinations absent from the unchanged student candidates: 59 duel and 100 team actions. Exact raw actions, unmatched history and reason codes remain recorded. These results do not establish student quality or Lite strength.

## Native BC failure and bounded correction

The panel harness incorrectly supplied a `TestStudent<format>` add-on as collector support. Native installs support at `LearningSupport`, so BC games without the student add-on could not resolve the embedded `TestStudent...` module paths. All 12 Native BC tasks were classified `infrastructure_error`, never ordinary losses/draws. [Representative original log](native-support-error.log).

Production `FormatExperiment` already exports a separately named `LearningSupport` package. Commit `a8bcf1d1b92625b17b91be40a1d23eeb60ea0d7c` corrects the panel harness to use that same namespace and pins support files. The Ubuntu design regression asserts the name and rejects student-module references in support. It passed without games or optimization. **No failed task was rerun, and no additional game was added.** Corrected Native panel acceptance remains unobserved. The independent Lite coverage failures also prevent default activation. Frozen strategies, candidates and thresholds were not changed.

## Evidence and reviews

- [Results](results.json), [full summary/audits](summary.json), [append-only task log](jobs.jsonl), [throughput](jobs.throughput.jsonl), [resource preflight](preflight.txt).
- [Execution command/source/build output](checks/20261107T080150_panel48_1a87e9d88381/output.txt). Wesnoth 1.18.8, isolated `teacher-host-v1`; about 14 GB available at launch. The support-fixture check briefly overlapped the remaining games.
- Fixed design/audit checks passed at `14d3d15`, `fbd9fff`, `1a87e9d` and corrected support `a8bcf1d`; commands and outputs are preserved under `checks/`. They do not promote this failed panel to passed.
- Pre-execution standards/specification reviews found missing audit closure for empty/misclassified DAgger labels. The corrected auditor binds source/task/seat, compares public histories and reconciles stored labels with query statistics. Both reviewers closed the findings before the 48-task execution.
- [Closure](closure.json) confirms task/status totals and zero timeouts. Its optional timing attempt could not decode packed-row metadata; those zero counts/nulls are unavailable, not zero-query evidence. The separate immutable [rowpack timing audit](panel_audit_20261107T0812/query_timing.json) decodes all 333 queries with the archived reader and supplies the table above. Original files were not rewritten.
- All 240 original raw files (including shards, events, model files and failed logs) remain at `cpuServer:/home/tongshu/myDev/wesnothLearning/verification/teacher_integration_20261107/panel_20261107T0802`. [SHA256SUMS](SHA256SUMS) binds their bytes. The local mirror contains reports/schedule and a representative error log; the full raw corpus stays on the acceptance host.

Remaining gate: a separately authorized new acceptance panel after addressing supervision compatibility within agreed scope. This report grants no new collection/training budget, does not modify the student candidate set and does not justify changing the FFA teacher.
