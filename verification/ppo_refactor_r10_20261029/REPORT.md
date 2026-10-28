# R10 acceptance — corpus, packaging and report identity

Behaviour accepted on 2026-10-28 as capability evidence: every packaged artefact names the teacher it came from, and
a stock-RCA bundle ships no opponent package at all.

## What changed

- `learning/bundle.py` writes `identities.teacher` — kind, version, query, action source, rules hash, capture hash and
  the list of opponent packages the teacher declares — and drops any `data/opponents/` member that list does not
  contain. For the stock RCA teacher the list is empty, so the bundle carries no Astra zip.
- `verify_bundle` re-derives both hashes from the shipped sources: `rules_sha256` from `data/rules/*/rules.json` and
  `capture_sha256` from the shipped `lua/stock_rca_capture/*.lua`, and rejects a member under `data/opponents/` that the
  teacher does not declare. Manifests written before this behaviour carry no `identities` key and keep their historical
  meaning (their opponent list is still verified, but not against a teacher).
- `learning/stock_rca.py` exposes `capture_sha256_from`, so the bundle and the teacher record hash the same sources with
  one formula.
- `learning/evaluate.py:gate_design` records `split_rule` in the BC design gate, and `learning/report.py` prints the
  teacher line (`Teacher: <kind> v<version> (query: …; DAgger: …)`) and `Split rule:` from a summary that carries them.
- `setup.sh` preflight now requires `lua/stock_rca_capture/{main,observer}.lua` instead of `data/opponents/gpt6astra.zip`.

## Revert proof

`revert_ubuntu.sh` restores the pre-R10 payload rule (`_needed` always true) and drops the `identities` key from the
manifest, then runs `tests.v5.test_bundle_identity.BundleIdentityTests.test_bundle_omits_unused_teacher`:

```
File ".../learning/bundle.py", line 308, in build_bundle
    teacher=manifest['identities']['teacher'],
KeyError: 'identities'
Ran 1 test in 0.006s
FAILED (errors=1)
```

Restoring the file returns `OK` (0.009 s). Logs: `rerun/revert.log`, `rerun/restore.log`.

## Ubuntu procedure

Acceptance ran in `/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r10b_20261029` from the archive built by
`git archive 5aafd40`, plus `SOURCE_REVISION`:

| Item | Value |
| --- | --- |
| Source commit | `5aafd40366c66fb3d39d40d5fe211d9757014720` |
| Source archive | `/tmp/wesnoth-r10.tar`, sha256 `f9ee6e988e39106e80e20da8ec98779d5f609c18489db8a0a2a5abd94fa4402a`, 7,777,792 bytes |
| Kernel | Linux 7.0.0-38-generic |
| Python / torch / lupa | 3.12.3 / 2.9.1+cpu / 2.6 (`wesnoth_learning_lite` is not installed in the base interpreter) |
| Provisioned data | `training_lite30h_20261025/source/data/{rules,opponents}` and `WesnothLearning/humanData_curated`; curated `games.jsonl` sha256 `1c94bb8d6ff51c192cf49fa24b5ce13adfefd8b3f6c5d08cf352e57536c3695f` |
| Built bundle | 321 files, 245,230,852 bytes, sha256 `ea8a6467afefd986baf87bc529eec0b92bc14687ebe33639fb09306166186ac5` |

`rerun_ubuntu.sh` verifies the archive hash, refuses an existing root, extracts, provisioned the data directories above,
runs the focused tests, builds the bundle twice with a fixed `--created-at`, runs `verify-bundle` and `setup.sh
--preflight`, then asserts the identity from the built archive itself.

## Results

| Check | Result |
| --- | --- |
| `tests.v5.test_bundle_identity`, `tests/test_bundle`, `tests/test_bundle_scripts` | 33 PASS (0.202 s) — `rerun/targeted.log` |
| Repeat build with fixed timestamp | byte-identical sha256 `ea8a6467…` — `rerun/identity.json: reproducible: true` |
| `verify-bundle` | `ok: true`, `errors: []`, teacher `wesnoth_default_rca` / `query: none` / `packages: []` — `rerun/verify.json` |
| `setup.sh --preflight` | `preflight: ok (10 required paths present)` — `rerun/preflight.log` |
| Teacher identity | kind `wesnoth_default_rca`, version `1.18.8`, query `none`, action source `engine_events`, rules `d6fceafe…`, capture `26d2894a09ccc66e5d7274d684644815d659d56b0110b0f0d22a83eb0e539557` |
| Shipped capture sources | `lua/stock_rca_capture/main.lua` `27a203b9…`, `observer.lua` `e56ed8ac…`; they reproduce the recorded capture hash |
| Astra package | absent: `manifest.data.opponents == []`, no `data/opponents/` member in the archive |

The capture hash is the canonical LF value measured for R8/R9 (`26d2894a…`). A working tree with CRLF line endings
hashes differently (`1706372d…`), which is why the acceptance build uses the `git archive` extraction.

## Limits

- The bundle is verified statically: it was built, verified and preflighted, but not installed, and no run was started
  from it.
- Only the stock teacher shape is exercised end to end. A queryable teacher must declare its own package; the verifier
  path for a non-empty `packages` list is covered by a synthetic unit test (`test_a_teacher_package_must_be_declared`)
  but not by a real bundle.
- The plan's interface line asks pools to carry `teacher_impl`/`corpus_id`. `teacher_impl` is recorded in pool source
  identities (`learning/data.py:259`); `corpus_id` is not implemented. A separate corpus identifier would duplicate the
  teacher record, `rules_sha256` and the shard list that already travel with every row, and nothing reads it, so this
  phase adds the bundle, gate and report surfaces and records the omission instead of adding an unused field.
- No corpus, training, strength or convergence claim follows from this evidence.
