# One-hour FF4 root-cause investigation

User authorization: 2026-10-23 23:18 Asia/Shanghai, one additional hour of investigation and bounded repair trials. Preserve formal runs and the original T5 failure. The old FF4 validation corpus is development data; the predeclared new holdout remains untouched until a concrete candidate is frozen.

1. Minutes 0–15: trace labels/indexes/candidate aliases, normalization and public-information inputs. Compare FF4/2v2 train/development distributions. Prefer read-only diagnostics on existing shards.
2. Minutes 15–30: freeze at most 64 existing FF4 training rows with complete prefixes and class coverage; test current/empty-history fitting. Measure loss, exact accuracy, parameter/gradient movement and actual sampling weights rather than guessing a new head.
3. Minutes 30–45: test batch/padding/permutation invariance and memory/context reconstruction. Follow any concrete failure to its owning layer. Timing allocations may overlap when a diagnostic runs.
4. Minutes 45–60: implement only evidence-supported fixes, run affected minimal regression tests, then evaluate a frozen candidate on fresh holdout only if justified and within budget. Otherwise record confirmed/excluded causes and the smallest remaining experiment without claiming a fix.

No new formal training, teacher replacement, threshold relaxation or broad benchmark matrix. Preserve rejected experiments separately; update docs/TEST.md and architecture status only from actual results. Do not alter the concurrent user edit to AGENTS.md.
