# 2026 archive months — curation and packing, 2026-10-30

Months provisioned under `data/replays/` by the user: `202607`, `202608`,
`202609`. Same criteria as the `202412` pull: standard era, mainline content,
a frozen 1.18.8 board, all-human sides, at least 20 decisions. Numbers in
`funnel.json`; the sweep scripts sit beside this report.

Environment: Windows reference box, no Wesnoth install. Ubuntu acceptance
**NOT RUN**; no replay was executed.

## Inventory (50,424 files, 4.57 GB bz2)

Version is the headline difference from `202412`: 18,430 files are exactly
1.18.8 and 16,663 are 1.18.7, so the rules-version gate finally has survivors
instead of ruling out the whole archive.

| Gate (first failure, `learning/human.compatibility` order) | Files |
| --- | --- |
| custom era | 34,167 |
| map not frozen | 5,476 |
| required add-ons/mods | 5,237 |
| add-on scenario | 4,417 |
| version != 1.18.8 | 582 |
| missing `[replay_start]` | 329 |
| malformed | 216 |

2,009 files play one of the ten frozen boards. 911 pass era, map, add-ons and
add-on-scenario; of those **329 are 1.18.8** and stop only at
`missing_native_initial_state` — the hosted archive layout carries no
`[replay_start]`, so `prepare_capture` has nothing to attach its observer to.
That, not the version, is now the binding constraint for humans data.

## Corpus

642 games (642 families: no duplicate history in the pull), 211,627 decisions.
Provenance defects under the same detector as `202412`: 196 games mix two
humans on one side, 24 have one player on both sides, leaving **446 clean games
with 136,808 decisions**, 146 of them at 1.18.8.

Regenerated together with the `202412` games so one corpus keeps one inventory:

| Corpus | Games | Families | Decisions | Clean | Clean decisions |
| --- | --- | --- | --- | --- | --- |
| `data/replays_curated/` | 1,076 | 1,076 | 359,526 | 757 | 233,899 |

All 1,076 curated payloads rehash to their recorded `payload_sha256` (0
mismatches), 0 AI sides anywhere, formats 724 duel + 352 team2v2, versions
1.18.8 197 · 1.18.3 290 · 1.18.7 218 · 1.18.0 210 · 1.18.5 66 · 1.18.2 46 ·
1.18.1 27 · 1.18.6 17 · 1.18.4 5.

## Packing

Each month is now one tar with the same member paths as before
(`<YYYYMM>/<DD>/<file>`), verified by re-reading every member and comparing
its SHA-256 and size against the loose file:

| Archive | Members | Bytes | SHA-256 |
| --- | --- | --- | --- |
| `data/replays/202607.tar` | 15,569 | 1,404,375,040 | `a86c152ab4064709cc7d0f7e09e63433c64db6c06cae90fbbb1ced2c989194d6` |
| `data/replays/202608.tar` | 15,693 | 1,447,782,400 | `97594394bb051d94e5b2d30b09ab5537147da406a2ec791e43031d2a4ea2ecb7` |
| `data/replays/202609.tar` | 19,162 | 1,716,736,000 | `3aed13c7225a19fa4a680564c218f92f2f6b3b2ab175960c68955b44ad2baf17` |

0 members missing, 0 mismatched. The loose trees were removed only after their
month verified.

## Limits

- Board identity is a terrain-multiset match against the frozen boards, not a
  replay execution.
- No file was replayed under native 1.18.8: legality, roll reproduction and
  observation formation remain unproven for all 1,076 games.
- The 582 non-1.18.8 shape-passers (331 of them 1.18.7) stay in the corpus as
  staging only, exactly as the `202412` ones did.
