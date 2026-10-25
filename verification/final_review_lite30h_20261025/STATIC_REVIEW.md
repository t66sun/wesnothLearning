# Final static review and launch preparation — 2026-10-25

Reviewed repair baseline `ab4fa33` through merged source `4e9e0dd1f93c71498be06d50f9b47af0ab846507`, plus the new final-budget reserve change. Standards and specification reviews found no actionable V1–V6 defect or scope expansion. Frozen inputs, rewards, gates and game quotas are unchanged.

The review identified architecture §10.12's launch prerequisite: predeclare nomination/holdout timing. The new opt-in reserve freezes a 25/1/4-hour schedule inside the requested 30-hour cap. Historical 420-game final evaluation took 36m53; this is a scheduling basis, not a new throughput claim. Default/legacy reserve stays zero.

Local command (Windows reference, one math thread):

```powershell
.venv/Scripts/python.exe -B -m unittest tests.v5.test_final_budget tests.v5.test_final_nomination
```

Before implementation, the two added tests failed (one parser error and one deadline assertion); see `reserve_before.log`. After implementation, all six affected tests passed in 7.097s; see `reserve_local.log`. They use synthetic inputs and recorded schedules, with zero real games. The boundary assertion fails when the new deadline subtraction is removed.

Ubuntu reserve acceptance and actual training startup are **NOT RUN** at preparation time. `launch.sh` checks a new destination, archive/rule/engine/teacher identities, runs only these six tests, then starts exactly one detached fresh run. It links only rules and opponents from existing provision; the new human/data namespace is empty. `launch.py status` is read-only and requires a live coordinator, valid teacher games, optimizer progress and checkpoints for all three formats before reporting startup ready.

Reuse the 12 Ubuntu repair checks and unchanged 273/17/13 evidence under their original identities and limits in `../refactor_repairs_20261025/REPORT.md`; no full-suite rerun. SDK package-size failure, broad real-game stage/forecast assertions, teacher strength and native semantics remain unpassed or unrun as already recorded. Training uses internal unbundled policies, with final packaging still explicit. No claim of convergence or strength follows from startup.
