# Selected-model export and local installation — 2026-10-26

User requested export and installation of the completed fresh 30-hour run. Source is frozen `822082d654cd19a6474aa36f837137c1ec7cb83c`; run is `/home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source/runs/v5_lite30h_20261025`. No training, new games, reward changes or frozen-source changes were made for export.

## Completed training

The run finished normally at **2026-10-26 16:35:34 Asia/Shanghai**, within the 30-hour cap. Each trainer exited 0; all BC gates passed without forced PPO. Each final panel has 30 complete blocks, no missing blocks and no fault games. This is deterministic-lite Astra evidence only, not native strength.

| Format | Latest / selected version | Final result | Score difference | 95% interval |
| --- | --- | --- | ---: | --- |
| duel | 470 / 400 | not_passed | -1.75 | [-2.25, -1.25] |
| ffa4 | 213 / 100 | inconclusive | +0.0138889 | [-0.0166667, +0.0444444] |
| team2v2 | 136 / 100 | not_passed | -1.625 | [-1.9875, -1.275] |

Latest candidates were not substituted after final evaluation. Duel/2v2 nomination did not pass Astra; FFA4's nomination panel was incomplete. The retained selected checkpoints are exported byte-for-byte under their original selection identities.

## Identity and numerical checks

`verify_frozen` passed on Ubuntu before export. `load_model`, `validate_checkpoint`, original manifest hash, selected hash/version, complete-batch state and all engine/combat/teacher fields are checked against the matching installed extension and frozen teacher. Actual source/teacher/rule identities remain in the downloaded manifest and `installation_manifest.json`.

| Format | Selected SHA-256 | Actual float32 Python / Lua max error | Original 1e-5 gate |
| --- | --- | ---: | --- |
| duel | `1f619c272dd132aaef5ddd7c549b8fc305b1b5195ad525d5596ddb95774d19cf` | 7.683312901463069e-6 | PASS, reused from v2 |
| ffa4 | `e1148429ee936c5c163f09502e9381dba0139dae6c69aa00f200c7233c5b8c25` | 2.210623698939429e-5 | **FAIL** |
| team2v2 | `aff0675bbda26a879b261f8702fd448e41001007abfa05acdd584ce4f9e0193b` | 7.781499834713657e-6 | PASS |

Each audit uses the complete first eight raw teacher records spanning own turns 1–2, includes 128 retained candidates and exercises memory commit/replay with the actual selected weights. Original recorded inputs are read-only; derived prefixes go to a new export directory. This is bounded sequence wiring, not long-game deployment acceptance.

The first helper incorrectly treated `unpack_line`'s `(row, numeric_bytes)` return as a row and failed before export. `export_remote.py` and `export.ubuntu.log` preserve it. `export_remote_v2.py` corrects unpacking in a new `_v2` output directory, then preserves the actual FFA4 gate failure in `export_v2.ubuntu.log`. Neither failed directory is overwritten.

Read-only diagnosis on the same FFA4 weights/input shows Lua agrees with a float64 reference to at most 7.460698725481052e-14, and all eight greedy choices agree with float32. The larger discrepancy is float32 accumulation rather than a demonstrated mathematical/layout difference on this prefix. A diagnostic-only linear-output rounding probe still failed (max 2.384185791015625e-5) and was **not adopted**. Double precision diagnosis does not replace the original float32 gate; original source and its threshold are unchanged. Full evidence is in `numerics_diagnosis.ubuntu.log` and `rounding_probe.ubuntu.log`.

## Reviewable local package

`prepare_draft.py` creates the unaccepted draft using the existing `export(..., package=False, identity=...)` API. It reuses the exact prior duel PASS and FFA4 FAIL, runs the remaining 2v2 audit and records every actual result. `installation_allowed=false` preserves the failed aggregate gate. The package is a local add-on directory, not an SDK competition submission; the SDK 16 MiB gate is unchanged and no competition archive validation is claimed.

- Local directory: `delivery/lite_final_20261026_draft/NeuralArena20261026`.
- Downloaded archive: `tmp/lite_final_20261026_draft.tar.gz`, SHA-256 `ac4aed7a51f17c9d754c61be6d7133a42438f4306f9177a6bcf3081a4337172e`, 47,394,673 bytes.
- Three checkpoint hashes and all 19 package-file hashes match the Ubuntu installation manifest.
- All 14 Lua files compile locally. Installed Wesnoth **1.18.8** successfully preprocesses the registration in a separate workspace userdata directory; this does not install into the real game directory. See `draft_checks.local.json` and `native-preprocess.local.log`.
- Real game target, if explicitly allowed: `C:/Users/Toshu/OneDrive/文档/My Games/Wesnoth1.18/data/add-ons/NeuralArena20261026`. Existing NeuralArena/NeuralArena20261024/NeuralArenaDuel directories remain untouched.

At preparation time the original numerical gate remains FAIL and the actual game installation is **pending the user's explicit local-trial exception decision**. No native game was started, no native strength acceptance is claimed, and no broad test suite was rerun. Passing prior unchanged checks is reused under its original scope. Later authorization and installation, if any, must be recorded separately without relabeling FFA4's original failure.
