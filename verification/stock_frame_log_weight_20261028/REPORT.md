# Captured STOCK frames are excluded from the native log cap - accepted on Ubuntu

Date: 2026-10-28 (Asia/Shanghai). Parent #48. Branch `codex/stock-frame-log-weight`.
Source commit `4123894`. Archive `stock_frame.tar.gz`, SHA-256
`d77e0d5f6d26bae81f0468309d6ffc4af0be86af77c45234caa2f3bc0de38ebb`.

## Defect observed

The authorized stock-RCA run `runs/v5_stock30h_20261028` stopped in its first ffa4
batch: job `stock-00003-ffa4-t0` returned `native log exceeds 80 MiB`. Its runner log
held 81 MiB in 1,466 lines, all but two of them `ARENA2 <game> STOCK {...}` capture
frames (roughly 55 KiB per line). `vendor/arena/match.py` counted only `LEARN` frames
as learning data, so a stock game's own observation/candidate stream was charged to
the native-chatter cap and the game was rejected while collecting a corpus.

The aborted run directory was removed; the strings above were read from the job
record and the rejected log before removal.

## Change

`vendor/arena/match.py` gains `log_weight(line, prefix)`: a line is weight 0 when it
starts with the game prefix plus `LEARN ` or `STOCK `, and its length otherwise.
The reader uses the helper for `log_bytes` and no longer writes capture frames to the
native log, so the 80 MiB cap still guards native chatter and the LINE/queue limits are
unchanged. No game behavior, seed, candidate, label or gate changes.

Source hashes: `vendor/arena/match.py` `a832536c8bb112ddd91255ca4e4767ef865f11f5e8bb0ad90153918df5f124b8`,
`tests/v5/test_native_log_cap.py` `bf9bd9bc78dc376495096739ebfc3de84ec2d347ab685cbd6173d6812b85874e`.

## Ubuntu result

Environment: Linux 7.0.0-38-generic (Ubuntu 24.04 kernel), Python 3.12.3. `ubuntu/pass.log`:
3 tests pass, including `test_captured_frames_do_not_count_against_the_cap`.
`ubuntu/revert.log`: reverting `log_weight` to `LEARN` only fails with
`AssertionError: 57 != 0`, exit 1; `restored=identical` after `cmp`.
Logs: `ubuntu/ubuntu_env.log`, `ubuntu/pass.log`, `ubuntu/revert.log`;
reproduction: `rerun_ubuntu.sh <archive> <sha256> [python]`.

## Limits

This is a log-accounting fix with a unit check. It does not re-run a native stock game,
does not prove capture noninterference and does not accept any corpus, BC/PPO result or
strength claim. The authorized 30-hour run was restarted from a fresh directory after
this fix; its own evidence is separate.
