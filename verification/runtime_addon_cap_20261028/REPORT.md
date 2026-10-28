# Runtime add-on directories are exempt from the submission size cap - accepted on Ubuntu

Date: 2026-10-28 (Asia/Shanghai). Source `4cdf3e7`. Archive `runtime_addon_cap.tar.gz`,
SHA-256 `7bc019b24661864cd8568be7d367022a7f9736dd151e78d6229b87ee45b478d0`.

## Defect observed

In the authorized run `v5_stock30h_20261028`, every validation and reward-reference game
failed with `ValueError('missing lua/bot.lua or submission exceeds 16 MiB')`: duel 12 and
team2v2 16 infrastructure errors. The exported policy directory
`duel/policies/v000020-greedy/SnapV000020` was 17 MB: its `lua/weights_duel.lua` alone is
16,735,005 bytes and the allowed companion files push the total over the 16 MiB
`MAX_PACKAGE_BYTES`. `learning/export.py` documents that internal policy/support exports are
not SDK submissions and may exceed the cap, but `addons.open_addon` applied the submission
cap to runtime directories, so the native runner rejected every student-controlled game.
The run was stopped at 22:21 after collection had reached duel 204, ffa4 32, team2v2 148
jobs (3.2 GB); its directory is retained.

## Change

`vendor/arena/addons.py`:
- `validate(directory, limit=MAX_PACKAGE_BYTES)` keeps the submission cap as the default and
  splits the missing-entry diagnostic from the size diagnostic.
- `open_addon` validates a runtime **directory** with `limit=None`; a working add-on is not a
  submission. Zip input and `pack()` still enforce the 16 MiB / 512-entry submission limits,
  so SDK package acceptance and `arena.py bot` behaviour for archives are unchanged.
- `tests/v5/test_addon_runtime_limit.py`: a directory over the cap is rejected by
  `validate` but opens through `open_addon`; the 19 vendored SDK tests still pass.

Source hashes: `vendor/arena/addons.py` `2073bf78d54cab4b4b96bc59896f7a2ee4bba5ca5c9e17489c2930965d2daaa0`,
`tests/v5/test_addon_runtime_limit.py` `715a6b641a6939b536227857041c4e3233cbff16c9d3250d042c90c846cd1a52`
(local working copies; LF archive copies differ by line endings).

## Ubuntu result

Linux 7.0.0-38-generic, Python 3.12.3. `ubuntu/pass.log`: 1 PASS. `ubuntu/sdk.log`:
19 tests OK. Reverting `validate(path, limit=None)` to `validate(path)` in
`ubuntu/revert.log` makes the new test fail with `ValueError: submission exceeds 16 MiB`,
exit 1; the file is then `cmp`-identical. Reproduction:
`rerun_ubuntu.sh <archive> <sha256> [python]`.

## Limits

This exempts a runtime directory from the *submission* cap only. The 16 MiB archive cap,
the 512-entry limit and `arena.py bot` package validation are unchanged; a three-format
delivery archive still exceeds the cap, and the SDK package-size item remains failed. The
change does not judge BC data quality, the coverage ratios, or training. The formal run must
be restarted from a fresh directory on this source; its own evidence is separate.
