# Authorized local-trial installation — 2026-10-26

After reviewing `REPORT.md` and the concrete draft, the user explicitly replied: **“允许本次本地试用例外安装，保留未通过标记”**. This authorizes this local installation only. It does not change the original 1e-5 numerical threshold or relabel the FFA4 failure, the final lite results or native strength acceptance.

Installed add-on: **Arena AI: NeuralArena20261026**.

Location: `C:/Users/Toshu/OneDrive/文档/My Games/Wesnoth1.18/data/add-ons/NeuralArena20261026`.

Selected versions are duel **400**, FFA4 **100**, team2v2 **100**, with the checkpoint hashes already recorded in the original report and installation manifest. `delivery/lite_final_20261026_draft/` retains the verified downloaded package and checkpoints; its original `installation_allowed=false` metadata is unchanged. The explicit exception is recorded separately rather than retrofitting that evidence.

Command:

```powershell
$env:PYTHONUTF8='1'
.venv/Scripts/python.exe -B verification/lite_export_20261026/install_local.py
```

Exit 0. Actual checks, not inferred from a copy command:

- All **19** original installed files match the reviewed export's SHA-256 entries.
- The new `LOCAL_TRIAL.json` records the user's authorization, source/checkpoint identities, `numeric_gate_status=not_passed`, FFA4 error `2.210623698939429e-5`, original threshold `1e-5` and actual evaluation labels.
- All **44** existing files under prior NeuralArena model directories have identical before/after hashes; all previous add-on directories remain.
- Installed Wesnoth **1.18.8** successfully preprocesses the actual installed `_main.cfg` (exit 0); expanded AI ID is `arena_NeuralArena20261026`, Lua entry points to `~add-ons/NeuralArena20261026/lua/bot.lua`.
- Installation includes **20** files: 19 unchanged package files and the explicit trial metadata. Full hashes and checks are in `installation.local.json`; native output is in `installed-native-preprocess.local.log` and `installed-native-preprocess/_main.cfg`.

Reuse the prior 14-file Lua syntax pass and original selected-weight identity/numeric results, because those package files are byte-identical. Duel/2v2 passed their bounded numerical audits; FFA4 remains **FAIL** under the unchanged float32 gate. No new training, game collection, runtime inference changes or full-suite rerun occurred. No native match, long-game sequence acceptance or native playing-strength test was run.

To use it, restart/refresh Wesnoth, enable **Arena AI: NeuralArena20261026** in multiplayer modifications, and select the same-name computer AI. Public roster/team routing selects duel/FFA4/2v2 weights automatically. Older model entries remain available. Removing only this new add-on directory reverses this installation; no removal was executed.
