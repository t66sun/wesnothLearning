# Independent search teacher

`selected_teacher.zip` is the frozen Wesnoth 1.18.8 native Lua AI package. Its public entry remains `evaluation(cfg,data)`, `execution(cfg,data)` and `data.plan`.

The package dispatches to the original selected strategy for duel, FFA4 and 2v2. Version identities, complete parameters and budgets are in [manifest.json](manifest.json). SHA256: `6b461de4e99303321b0119a7b88babd575c2d786500b28da4cb45d3c2bdabdb3`.

All 524 holdout games completed without faults. Duel and 2v2 pass both strength gates; FFA does not, so the overall six-cell requirement is not met. [Scores, intervals, costs and scope](../../verification/teacher_search_20261107/REPORT.md).

This delivery is independent. It does not install itself, replace the active Astra teacher or connect to student training. The measured action budgets are 2 seconds ordinary / 20 seconds first, versus Astra 1 / 10 seconds. Evaluation soft deadlines are 700 ms tactical and 1000 ms total from the same start.
