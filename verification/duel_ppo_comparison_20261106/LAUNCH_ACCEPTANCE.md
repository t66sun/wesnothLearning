# Final launch acceptance

Execution source: `43325b33696de4db8ee546e1c6bedb7230a73b37`. Protocol commit remains `0c5cfa2a69f160610ab92032c0a6e72deccfca22`.

Archive SHA-256: `62f97a406854c27241d0a558067c6858b1133ad9ab092ea29d08bdd7e395aef5`.

Fresh Ubuntu source: `/home/tongshu/acceptance/duel_comparison_20261106_43325b3/source`; sibling `SOURCE_COMMIT` identifies the extraction. The source adds the root-reviewed completeness requirement: both shared validation and final holdout must be complete before an experiment can report `observed`.

`/home/tongshu/venv/bin/python -m unittest -v verification.duel_ppo_comparison_20261106.test_contract` passed **10 tests in 0.030 s**. The original nine responsibilities and the validation-incomplete/holdout-complete counterexample passed. [Raw output](fixture-tests-43325b3.log)

`bash -n verification/duel_ppo_comparison_20261106/launch.sh` and `python verification/duel_ppo_comparison_20261106/driver.py --help` passed. [Checks](launch-checks-43325b3.log). The input audit and controlled accounting restoration retain their original source identities in `PRELAUNCH.md`. No experiments or new games were started during these checks.

After root approves this source and command:

```bash
export PATH=/home/tongshu/acceptance/duel_comparison_tools_20261106/root/usr/bin:$PATH
export LD_LIBRARY_PATH=/home/tongshu/acceptance/duel_comparison_tools_20261106/root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
tmux new-session -d -s duel227-20261106 \
  'bash /home/tongshu/acceptance/duel_comparison_20261106_43325b3/source/verification/duel_ppo_comparison_20261106/launch.sh'
```

The immutable runtime source is the extraction above; subsequent evidence-only commits are not a change to the execution source. Track `driver.log`, `launcher.txt`, `driver.exit` and the new run's stage process/exit records until termination. User authorization for this bounded experiment is already recorded; no repeated user approval is required.
