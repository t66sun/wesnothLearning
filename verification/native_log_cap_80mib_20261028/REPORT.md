# Runner native log cap 80 MiB - accepted on Ubuntu, not a corpus or strength claim

Date: 2026-10-28 (Asia/Shanghai). Branch `codex/native-log-cap-80mib`, source `76978ef`
(`132b928` raised the cap, then two probe/script fixes). Acceptance archive
`native_log_cap_cap3.tar`, SHA-256
`28dd906c791f852972f1b952499907b504eee9e1518a147111cb655319e05b13`.

## What changed

`vendor/arena/match.py` replaces the inline `log_bytes>16*1024*1024` test with
`NATIVE_LOG_LIMIT = 80*1024*1024`, `log_exceeded(size)`, and
`RuntimeError(f'native log exceeds 80 MiB')`. `tests/v5/test_native_log_cap.py` asserts a size just
past 16 MiB is accepted, 80 MiB is accepted, and 80 MiB + 1 is rejected.

## Ubuntu acceptance (2026-10-28)

Environment: Linux 7.0.0-38-generic, Python 3.12.3. Logs in [`ubuntu/`](ubuntu/).

| Check | Result | Log |
| --- | --- | --- |
| `tests/v5/test_native_log_cap.py` | **2 PASS** | `ubuntu/cap.log` |
| Revert `NATIVE_LOG_LIMIT` to 16 MiB | both tests fail with `True is not false` (exit 1) | `ubuntu/revert.log` |
| Restored `vendor/arena/match.py` | `cmp` byte-identical | `ubuntu/restored.log` |

Source hashes: `vendor/arena/match.py` `554d3395...`, `tests/v5/test_native_log_cap.py`
`6de4ad08...` (see `ubuntu/source.sha256`).

## Limits

- **Predicate only.** No real 60-turn native game was run here, so the 80 MiB value is not shown to
  bound a measured worst case; it is the authorized limit, four times the rejected one.
- **No corpus or training.** Raising the cap removes a refusal path; it does not create stock
  teacher games, labels, BC coverage or strength.
