# Isolated BC window sampling acceptance

2026-11-01, cpuServer. Source `99e23cc06440f5dd128905f2610e77f6609ee1be`, shipped using git archive into `/home/tongshu/acceptance/window_sampling_20261101`. Existing read-only rules link; Python `/home/tongshu/venv/bin/python`.

Command: `PYTHONPATH=.:vendor/arena /home/tongshu/venv/bin/python -m unittest tests.v5.test_bc_window_sampling -v`.

One test passed in 0.604 seconds; see sampling.log. This isolates PR #126 from the subsequent memory optimization. Combined behavior/gradient and baseline failure evidence is preserved in `../window_memory_20261101/REPORT.md`. No formal training or collection; no convergence claim.
