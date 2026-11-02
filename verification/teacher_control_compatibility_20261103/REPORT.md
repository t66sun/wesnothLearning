# Frozen control ambush compatibility — 2026-11-03

The original native teacher panel recorded a frozen-control assertion at turn
21 in `r3-panel-ffa4-b0001-solo-r0`. The parent archive still contains the same
move assertion in all three strategies. A new staging helper applies only the
already-accepted ambush interruption hunk to a copied control add-on. It does
not change the original archive, scoring, tactics, or any acceptance gate.

## Source and execution

- Source commit: `b0d67cd9e71f595124b8cc84070e1a9ffa2e3a51`.
- `git archive --format=tar` SHA256, local and Ubuntu:
  `7370ad2a79ed62045b72f36fa7aaad83250d9aac92c7666a4593520504214492`.
- Ubuntu acceptance directory:
  `/home/tongshu/acceptance/teacher_control_compatibility_checked_20261103`.
- Python: `/home/tongshu/venv/bin/python`.
- Frozen parent `data/opponents/gpt6astra.zip` SHA256:
  `2a216c96081990621dc15772e9de1bf40e4f5f451223fe52e5b20625464dc933`.

The archive was initially unpacked before its transfer finished, which failed
before tests started. After transfer completion, the remote SHA256 matched the
local archive. The complete archive was extracted into the fresh acceptance
directory above; the test command ran once there.

```sh
/home/tongshu/venv/bin/python -m unittest \
  tests.v5.test_teacher_control_compatibility \
  tests.v5.test_teacher_movement -v
```

All six tests pass in 0.015 seconds, exit 0. The raw output and exit code are
preserved beside this report.

## Observed behavior and scope

The new tests unpack the real frozen parent into a temporary directory and
reuse the existing Lua movement harness. For each of duel, four and eight:

- Original frozen execution raises `LuaError` on native status 2005.
- Derived execution performs the move and stops before the old planned attack.
- Normal arrival still performs the planned attack; status 2008 still fails.
- Reversing exactly the declared three-line replacement restores every byte of
  each changed parent file, and all other extracted files remain unchanged.
- The derived move helper equals the maintained teacher's accepted helper.

`apply_ambush_compatibility(staged_root)` returns `files`, keyed by relative Lua
path, with each changed file's `old_sha256` and `new_sha256`. It preserves the
staged file's newline convention and rejects an absent or repeated old hunk.
The caller must supply an already-copied add-on, before packaging; no caller
integration or new strength panel is claimed by this helper acceptance.

The actual native meaning of status 2005 and stopping the old plan is reused
from `verification/teacher_ambush_20261103/REPORT.md`: the helper code is identical.
No native game, collection, training or Windows test was run for this change.
This is control execution compatibility evidence, not non-inferiority or
strength acceptance. The frozen parent and all previous evidence remain unchanged.
