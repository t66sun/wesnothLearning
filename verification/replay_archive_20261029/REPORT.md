# Replay pull analysis — 2026-10-29

Question: does `data/replays/202412` (a December 2024 whole-month pull from
replays.wesnoth.org) yield a BC-usable human corpus under the frozen 1.18.8
contract, and what should be kept?

Environment: Windows reference box, no Wesnoth install, so no native replay of
any file. Ubuntu acceptance **NOT RUN**. Numbers in `funnel.json`; the four
scripts that produced them sit beside it.

## Inputs

- `data/replays/202412/**`: 16,871 files, 1,225,379,840 bytes, `*.bz2`, named
  `<title>_Turn_<N>_(<server id>).bz2`, 16,862 unique names.
- Frozen boards: `data/rules/1.18.8/maps/*.json`, the ten maps in
  `learning/maps.SPLITS` (`the_freelands`, `weldyn_channel`, `sablestone_delta`,
  `hamlets`, `caves_of_the_basilisk`, `ruined_passage`, `clash`, `isars_cross`,
  `loris_river`, `morituri`).

## Layout of a lobby archive

Unlike a local save, a replay dropped from the multiplayer lobby has no
`[replay_start]`: the starting state is `[scenario]` (board, sides, turn limit)
plus `[carryover_sides_start]` (the initial `random_seed` and `random_calls`),
and the history is split across two `[replay]` blocks — the first holds only
`[upload_log]`, the second holds every `[command]`. Parsing either container as
the other finds no starting state or an empty history, which is why
`learning/replay_curate.py` now reads both (`layout` = `save` or `archive`).

3,286 of the 16,871 files do carry `[replay_start]`, but those are mid-game
lobby uploads with no `[scenario]` and therefore no board: 3,288 files have no
map at all. None of the 1,103 files on a frozen board has a `[replay_start]`.

Map identity was decided by terrain multiset rather than by scenario id, because
the ladder names boards after the map they imitate while changing the terrain
(e.g. `2p__Hamlets_+_(ladder)` has 870 cells against the frozen 756). Server
`map_data` pads the board with a one-cell ring, so 628 files match exactly and
475 match after stripping one ring.

## Funnel, first failing gate over 16,871 files

| Gate | Files |
| --- | --- |
| map is not one of the ten frozen boards | 15,578 |
| `version` is not `1.18.8` | 591 |
| required addons or active mods | 239 |
| era is not `era_default` | 227 |
| malformed WML | 190 |
| scenario supplied by an add-on | 46 |
| **eligible** | **0** |

Version census of the whole pull: 1.18.3 10,545, 1.18.0 4,632, 1.18.2 1,368,
1.18.1 74, 1.18.3+dev 30, 1.17.26 18, 1.18.2+dev 14. **No file anywhere is
1.18.8**; the pull predates that release.

## What the 591 shape-passers are

Standard era, mainline board, no add-ons or mods, no add-on scenario — i.e.
everything `learning/human.compatibility` checks except the two structural ones:
478 are all-human, and 434 of those carry at least 20 decisions. Those 434 form
434 distinct game families (no identical histories, no strict prefixes), 311
duel and 123 team2v2, so the `learning/formats` gate already passes for all of
them.

## Corpus

`data/replays_curated/` holds those 434 games (147,899 decision intents out of
372,953 semantic commands), versions 1.18.3 274, 1.18.0 91, 1.18.2 42, 1.18.1 27.
Every curated `.gz` rehashes to the recorded `payload_sha256` (434/434, 0
mismatches) and `originals_unchanged` is true; the inventory records
`layout=archive` and the source member path for each.

The remaining 16,437 files were packed with the rest of the pull into
`data/replays/202412.tar` (16,871 members, `202412/<day>/<file>`), which was
re-read member by member: 0 missing, 0 mismatched, 1,225,379,840 bytes,
SHA-256 `5db48380b62ac57badbf4f8f40dc304d95578539dc90f4ffac477216436a22ad`.
The loose tree was removed only after that verification.

## Why zero games are BC-eligible

1. `learning/human.compatibility` stops every file at `other_version`
   (`row.get('version') != '1.18.8'`). Labels must describe the frozen 1.18.8
   combat and recruit numbers; a 1.18.3 replay does not reproduce under them.
2. The same function then stops them at `missing_native_initial_state`, and
   `prepare_capture` needs `[replay_start]` to find the human sides and to hang
   the `learning_observe` event on. Archive-layout support in the curator is not
   a capture path.

Replaying these games under 1.18.8 would not preserve their rolls, so the corpus
is a staging set, not an importable one: it is labelled by rules version and
waits for either a rules-version-aware BC path or an archive-layout capture
path. Neither exists, and this report claims neither.

## Limits

- Reference evidence only; nothing here ran under Ubuntu or under native 1.18.8.
- Board identity is a terrain-multiset approximation; no replay was executed to
  confirm it.
- 190 files fail to parse and are counted as unusable, not as empty games.
- Curation selects games, never labels: no outcome, reward or split is inferred
  from filenames or turn counts.
