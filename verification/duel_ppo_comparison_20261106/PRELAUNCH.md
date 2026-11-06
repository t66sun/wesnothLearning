# Prelaunch acceptance

No experiment, collection or new evaluation game has been launched. Protocol commit: `0c5cfa2a69f160610ab92032c0a6e72deccfca22`. Driver/fixture source: `f06de2556556b7fd0044a54a7b7c43fe79e01021`, archived with SHA-256 `969230f9c1762f5c52721e464f43b988d583c48d3bd20550e75fce5162b9b376` at `/home/tongshu/acceptance/duel_comparison_20261106_f06de25/source`.

On Ubuntu, `/home/tongshu/venv/bin/python -m unittest -v verification.duel_ppo_comparison_20261106.test_contract` passed **9 tests in 0.024 s**. The fixtures cover zero-step fresh accounting, hard-deadline settlement, the real learn-loop boundary with two whole 6001-target batches, fixed Astra parameters, equal-weight result aliases, matched and complete panels, crossed bootstrap draws, separate superiority/retention predicates and recorded-policy MC deduplication. [Raw output](fixture-tests-f06de25.log)

Restoring the wrong rule that counts only batches with `updates>0` makes the numeric accounting assertion fail: `5000 != 11001`. [Controlled restoration](reverted-budget-test.log). It was a separate process and did not change source or production behavior.

The read-only input audit succeeded against the actual old BC checkpoint, all 304 retained teacher/DAgger schedules, rules, opponent, extension and holdout boards. [Observed identities](preflight-inputs-f06de25.json). The nine fixtures launch no games and make no optimizer updates. No Windows test was run.

## Persistent host dependency

The host had no installed tmux. Two packages were downloaded from its configured Ubuntu Noble repositories and extracted without installation scripts or system package changes into `/home/tongshu/acceptance/duel_comparison_tools_20261106/root`:

| Package | Version | SHA-256 |
| --- | --- | --- |
| tmux | `3.4-1ubuntu0.2` | `fd14ca543ca0c00c7314c7bb524be40f3d058d9e587a5f47d9b35e851d9bd67d` |
| libutempter0 | `1.2.1-3build1` | `46c0dfbfeca19ba0773398d654b7e7225b178f26b414f0e2f8250519551bfb32` |

The apt mirror was `http://mirrors.tuna.tsinghua.edu.cn/ubuntu`, Noble/main and Noble-updates/main. The extracted executable reports `tmux 3.4`. It uses the task directory's PATH and LD_LIBRARY_PATH; libevent and libtinfo were already installed. Packages remain under the sibling `packages/` directory.

## Reviewed launch shape

Archive the final source into a fresh acceptance directory, retain `SOURCE_COMMIT`, provision the unchanged maps link, and run the following only after root reviews the final source and command:

```bash
export PATH=/home/tongshu/acceptance/duel_comparison_tools_20261106/root/usr/bin:$PATH
export LD_LIBRARY_PATH=/home/tongshu/acceptance/duel_comparison_tools_20261106/root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
tmux new-session -d -s duel227-20261106 \
  'bash /home/tongshu/acceptance/FINAL_DIRECTORY/source/verification/duel_ppo_comparison_20261106/launch.sh'
```

`launch.sh` pins the tested Python/extension/rules/thread environment and provides an outer eight-hour timeout. The driver records the exact command, source/protocol/input identities, its PID, every child PID/process group and each stage deadline/exit. The acceptance directory receives `driver.log`, `driver.exit` and `launcher.txt`; detailed fresh run data go under `source/runs/duel_ppo_comparison_20261106/`. No source or frozen historical input is rewritten. Root must replace `FINAL_DIRECTORY` with the fresh archive directory and verify its SHA before launch.
