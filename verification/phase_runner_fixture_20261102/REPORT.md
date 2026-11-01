# Automatic phase-entry fixture

Source: `41703d6a7023d65593206a10d521f7d516b11153`, shipped by `git archive` into `/home/tongshu/acceptance/phase_runner_fixture_20261102` on Ubuntu `cpuServer`.

The synthetic runner for `test_auto_uses_next_sampling_method_after_bc_gate` omitted `policy_shards`, which the real runner initializes. Its qualified branch therefore raised before checking that a passed BC gate schedules PPO. Initialize that list in this fixture only; preserve both qualified/unqualified assertions and production behavior.

The pre-fix error is reproduced on baseline in `../team_teacher_factions_20261102/baseline/baseline_phase.log`. After the one-line fixture correction:

```bash
PYTHONPATH=.:vendor/arena OMP_NUM_THREADS=1 /home/tongshu/venv/bin/python \
  -m unittest tests.v5.test_training_failure_fixes.PhaseEntryTests -v
```

**5 tests pass**, 0.043 s, exit 0; raw output is `checks.log`. The other 42 prior passing checks outside this class are reused, not rerun. No training or collection was launched by these checks. They ran during the separate bounded BC experiment; this report makes no performance claim. Historical error logs remain unchanged.
