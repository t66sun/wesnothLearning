# Adaptive reward window refresh — 2026-10-24

Fixed `learning/control.py:307`: consume every complete 12-block window instead
of stopping permanently once three windows exist. The existing `[-3:]` retention
keeps the latest three; partial blocks stay queued in their original order.
Only that loop condition changes in production code. No reward threshold,
coefficient, event/version rule, 50-batch/64-game trigger, KL or learning algorithm
changes. Root-cause evidence remains in the original [quality investigation](../training_stall_20261024_1544/REPORT.md).

## Minimal regression and Ubuntu acceptance

New standalone suite: `tests/test_reward_windows.py` (88 lines), leaving the
existing grandfathered pipeline-contract file unchanged. The assertions cover:

- Two new windows after the first three change the actual boundary decision;
  the existing adaptive queue applies exactly one versioned event, then state
  restoration and duplicate evidence preserve the result.
- A 55-block backlog retains the correct newest three windows and seven
  unfinished blocks, without inventing a coefficient change.
- Eleven blocks do not evict a window; the twelfth advances it.

All three fail before the fix (`red.windows.txt`). With the fix, all three plus
11 existing `BoundaryTests` pass locally (`green.windows.txt`, 14 tests / 0.639s).

Ubuntu acceptance uses a separate short-lived process under
`/home/tongshu/myDev/wesnothLearning/validation_memory_repair_20261024_1321`.
`ubuntu_probe.py` loads old/new controller modules into that process's module
table and runs the exact new test source. It does not replace any server file
or inject code into a training process. Results (`acceptance.ubuntu.txt`):

- Frozen old implementation: exactly three expected assertion failures.
- Patched implementation: all 14 affected tests pass, 0.635s.
- Real previously captured duel controller state: 55 pending blocks → 7, latest
  three windows correct, no coefficient recommendation, reward_version still 0.
- Live `learning/control.py`, run manifest and clock hashes unchanged before
  and after the probe. No game, training update, restart or live control command.

Local command:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.venv/Scripts/python.exe -m unittest tests.test_reward_windows tests.v5.test_pipeline_contract.BoundaryTests -v
```

Ubuntu payload command: `.venv/bin/python -u - < ubuntu_probe.py`, executed from
the isolated source root using the existing accepted environment. Its source
strings are supplied from the local patched controller and new tests; the raw
capture embedded in the payload is unchanged historical evidence. The probe
asserts the sole production difference is the loop condition before running.
No unaffected game/engine/pressure acceptance was repeated.

## Identity and deployment status

Old normalized controller SHA-256:
`31ec73be29b73188ab53bd60678a0189f01576e195d727be128201667d48d6d6`.
Patched controller SHA-256:
`2d79571785ab3ebd1b4299653791b78e7a3f85c3cf9338684de855a3c858d1a9`.
Rule SHA remains
`d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`;
no rule-dependent collection was needed for this pure controller change.
The running manifest remains
`8ec090d7b5626a093695a5f94fb6a809f5d7bb0f252aaf49af73067cc0140569`.

The fix is accepted source, **not deployed into the active formal training**.
That process already imported its frozen old module; updating GitHub or changing
a local file would not update its in-memory controller. A new run or separately
authorized controlled source migration is required. Original deadlines and
checkpoints stay intact. KL stopping and omitted PPO exposure counters remain
outside this change. This acceptance claims rolling-window correctness, not
improved convergence or play strength. TEST.md keeps only its existing pending
native terminal-state capture; this passed item is archived here.
