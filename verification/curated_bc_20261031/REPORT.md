# Curated lobby-archive replays enter BC — 2026-10-31

Clears blocker 2 of the 2026-10-31 blocker list: no curated replay could enter BC because the
lobby archive has no `[replay_start]` block. Three 1.18.8 curated games were prepared, played by
official Wesnoth 1.18.8, and imported as BC rows.

## Decision

`[scenario]` is the start block for a server archive; no `[replay_start]` is synthesised.

Engine 1.18.8 builds the initial state itself and merges the recorded RNG, so a hand-written
start block could only disagree with it:

- `src/saved_game.cpp:617-633` `get_replay_starting_point()` falls back to `expand_scenario()` and
  `expand_carryover()` and returns the `[scenario]` starting point.
- `src/game_initialization/playsingle_controller.cpp:170-172` replaces an empty
  `replay_start()` with the loaded starting point.
- `src/carryover.cpp:203-210` `carryover_info::transfer_to` writes `random_seed`/`random_calls`
  into the level block when absent; `src/game_data.cpp:36-40` and `src/mt_rng.cpp:53-54` seed the
  game RNG from that block.
- `src/save_index.cpp:407` documents the layout: server-generated replays carry `[scenario]` and
  no `[replay_start]`.

Two replay-machine constraints were measured, not assumed:

- `src/replay.cpp:869-874`: a `[custom_command]` reached while a synced context is active is a
  fatal "expecting a user choice". A marker placed directly after an action command is reached
  from inside that action's `synced_context::run`, so markers are emitted only **before** an
  action (`learning_observe`) and once at the end (`learning_complete`). The observer flushes the
  previous sample when the next marker runs.
- `src/replay.cpp:847-865`: a dependent command (`[random_seed]`) is served to the engine's RNG
  handshake mid-action, so nothing may sit between an action and its dependent commands.
- `src/ai/lua/core.cpp:1052-1099`: `wesnoth.sides.debug_ai(side)` returns the AI state table whose
  `ai` field is the functions table; the global `ai` is a scope guard that is removed on return,
  so the observer reads `debug_ai(side).ai` and restores `rawget(_G,'ai')` afterwards.

## Commands

Host: Ubuntu acceptance box (`ssh cpuServer`), Wesnoth
`~/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth`
(sha256 `33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf`,
`Battle for Wesnoth v1.18.8 x86_64`), interpreter `~/venv/bin/python` 3.12.3.

Source shipped as a `git archive` tarball (the host has no git) into `~/curated_bc_20261031/src`,
with `data/replays_curated/{games.jsonl,replays/standard_multiplayer/*.gz}` beside it.

```sh
# 1. prepare: start block, injected markers, per-capture userdata and launch command
cd ~/curated_bc_20261031/src
WESNOTH_EXE=$HOME/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth \
  ~/venv/bin/python -m learning import-human \
    --curated ~/curated_bc_20261031/data/replays_curated --output data/datasets/human
# {"statuses": {"prepared_pending_native_replay": 3}, ...}   (intents 38 / 35 / 50)

# 2. play each prepared replay in official 1.18.8 (Xvfb :99, synthetic 'p' keypress starts playback)
DISPLAY=:99 ~/venv/bin/python drive_native.py src/data/datasets/human/capture/game_0361 150
DISPLAY=:99 ~/venv/bin/python drive_native.py src/data/datasets/human/capture/game_0024 150
DISPLAY=:99 ~/venv/bin/python drive_native.py src/data/datasets/human/capture/game_0648 150

# 3. import the retained logs
cd ~/curated_bc_20261031/src
~/venv/bin/python -m learning import-human \
  --curated ~/curated_bc_20261031/data/replays_curated \
  --captures data/datasets/human/capture --output data/datasets/human
# {"statuses": {"imported": 3}, "samples": 84, ...}
```

`--load` only accepts a save name inside `<userdata>/saves/` (`game_launcher.cpp:190-200`
prepends the saves directory), so the driver gzips the prepared `.cfg` to
`userdata/saves/<game>.gz` and launches `--load <game>.gz`. `--with-replay` opens playback
stopped, so the driver injects the `playreplay` hotkey and presses it with XTest.

## Result

| game | format | human actions | samples in log | complete markers | engine errors | executable actions | BC rows | move coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| game_0361 | duel | 35 | 35 | 1 | 0 | 91/91 | 21 | 5/19 |
| game_0024 | duel | 38 | 38 | 1 | 0 | 101/101 | 24 | 4/18 |
| game_0648 | team2v2 | 50 | 50 | 1 | 0 | 150/150 | 39 | 15/26 |

Every replay ran to its final action, produced exactly one `complete` marker, and
`import_capture` accepted the sample order (`action_index` covering `range(expected_actions)`).
`recruit`, `attack` and `end_turn` intents match a generated candidate in every case; a `move`
becomes a BC row only when the played move is among the generated candidates, which is why rows
are fewer than actions.

Per-game details are in `import.json`, the prepared launch command and marker for game_0361 is in
`prepare_game_0361.json`, and the counts above are reproducible from `evidence.log`.

## Limits

- Breadth is not claimed: 3 of the 197 curated games whose version matches 1.18.8 were played. No
  collection or training was run.
- Playback needs a display. It ran under `Xvfb :99` with a synthetic `p` keypress; the engine never
  auto-plays a `--with-replay` load outside unit-test mode.
- A lobby archive without `[carryover_sides_start].random_seed` is skipped as
  `missing_initial_rng`, because the replay then has no recorded RNG stream to reproduce.
- A `[custom_command]` marker is only safe where the replay machine is unsynced; the marker
  layout above is the measured safe subset, and `tests/test_human.py` pins it.

## Identities

```text
source tarball           260b1bbfae39ae327ed1a16b48acb31b0ad15041d5f299631b847fb919ed77c3
data/replays_curated/games.jsonl  0f56a578748d68bf353c8d41105c6d749508021458aa62d74f2c6f2de670abdb
replays/standard_multiplayer/game_0361.gz  0df1b7787be842db869703e8ddf5e1aa82d8d890e99bb723d26f465b8977a852
replays/standard_multiplayer/game_0024.gz  92ead698b78484af2b99f39d49d956d9377aed6056d7c362a44039245a3a0aea
replays/standard_multiplayer/game_0648.gz  c48a53af35aa609d1685e20bd45f1ffc4b40a3b724bf379de6a96440e0ebeb7c
prepared game_0361.cfg   439ab55577fd4aaa56d833552fc1bef273a79bf6b455d666b2ae3381ef74d6e3
prepared game_0024.cfg   1d19926f1894d8ca72e91035d3311e69a694526c937334b82308bd371ca82e39
prepared game_0648.cfg   1df5a641a92976454b3ba854ed79dc67e420173e6460ad7948c32e5ccd48fe31
game_0361.log             a6f5c2b8901e6c85c5935e042699499cd98bf3ff5e8e83cf2e61822605741284
game_0024.log             79c82a7988136e172e497b7b1252712507bd1a8756b8d7f634f95969e4df51c9
game_0648.log             a26e827137f138efeaa42b03f54d363a8318483678578672cb1a94badb09c9f9
duel/game_0361.jsonl.gz   e1903473bfc772788adf61e40d8747ad3bbcc9f261fd44dda6d6e4c42adc65ec
duel/game_0024.jsonl.gz   391c80e665c5ff95695c4b7b2b5763a7a53e6de0930c4238dc650235855b4b8d
team2v2/game_0648.jsonl.gz  3a9ce33d85931d370a841359ae4f405cc9dafe464c0237df09e5154f36c4500f
```

`drive_native.py` and `keyplay.py` in this directory are the drivers used for the runs above
(gzip to `<userdata>/saves`, `--load <game>.gz`, `--no-log-to-file`, `--log-info=scripting/lua`,
`--nodelay`, XTest `p`).
