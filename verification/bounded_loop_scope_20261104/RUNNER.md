# Bounded driver handoffs

Ubuntu tested source `9386c58cacf45f2b02a1e48fe391f86441492290` in `/home/tongshu/acceptance/bounded_loop_runner_9386c58_20261104`. Its source archive SHA256 was `4336888c99b1042b9375acf657cb02bfc72fb557d513b1894291224f875fe0d4`.

```sh
/home/tongshu/venv/bin/python -m unittest tests.v5.test_bounded_loop_progress tests.v5.test_bounded_loop_final -v
```

Eight affected tests passed. With the same tests and the driver from `613cc97`, the simulated inherited effective flag let the old driver enter PPO with zero new BC updates. The old driver also issued both requests without a committed PPO batch target. Both regression assertions failed. [Baseline](red.log) · [Updated driver](runner.log)

These deterministic tests cover the handoff decisions. Actual checkpoint files, optimizer progress, elapsed time and full-panel results belong to the integrated run.
