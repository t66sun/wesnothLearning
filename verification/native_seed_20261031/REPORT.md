# Native play replays from its seed — 2026-10-31

Clears blocker 1 of the 2026-10-31 blocker list: a stock native duel played twice from one seed
ended at turn 5 and turn 3 with different decisive event streams. Two runs of the same seed now
emit identical decisive event streams, twice in a row across separate processes, and the probe
fails when the entropy shim is not preloaded.

## Decision

`--rng-seed` only calls C `srand`, and three entropy sources bypassed it:

- `randomness::rng::default_instance()` seeds from `boost::random_device` at static construction
  (`src/random.cpp:35-49`).
- Every synced action with an empty `random_mode` calls `generate_random_seed()` →
  `seed_rng::next_seed()` → `boost::random_device` (`src/synced_context.cpp`, `src/seed_rng.cpp`).
  A fresh `--multiplayer` game cannot supply `random_seed` through WML, because
  `set_random_seed()` runs before the scenario's `[carryover_sides_start]` is merged
  (`src/game_initialization/mp_game_utils.cpp:68-70`, `src/saved_game.cpp:170-180`).
- Lua seeds its own `math.random` in `luaopen_math`/`luaL_makeseed`, independently of Wesnoth.

`random_mode=deterministic` would not pin the initial `random_seed` and would change stock RNG
semantics; a prepared start-save would change the launch path. The shipped lever leaves the game
rules and the official binary untouched:

- `vendor/arena/entropy.c` interposes `open`, `open64`, `read`, `__read_chk`, `close`,
  `getrandom` and `getentropy`; an entropy read is answered from an xorshift64 stream selected by
  `ARENA_ENTROPY_SEED` (hex), falling back to the fixed FX1 constant when the variable is absent.
- `vendor/arena/match.py` puts the seed into the scenario config and preloads
  `.runtime/entropy.so` with `ARENA_ENTROPY_SEED` for the Wesnoth child only; the parent
  environment is untouched.
- `vendor/arena/runtime/runtime.lua` calls `math.randomseed(config.seed)` at setup, guarded so the
  two `native.scenario` callers that pass no seed keep working.
- `setup.sh` builds `.runtime/entropy.so` with `cc -O2 -fPIC -shared … -ldl`.
- `tests/smoke_native_repeat.py` is the assertion: two `play_game` processes from one seed, exit 0
  only when the decisive event streams and `reason`/`turns`/`seed` match.

## Commands

Host: Ubuntu acceptance box (`ssh cpuServer`), Ubuntu 24.04.5 LTS, kernel 7.0.0-38-generic, 8
cores, Wesnoth `~/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth`
(`Battle for Wesnoth v1.18.8 x86_64`), interpreter `~/venv/bin/python` 3.12.3, `cc` 13.3.0.

The host has no git, so the accepted source was shipped as a `git archive` tarball of
`origin/master` with the five changed/added files overlaid, extracted to
`~/myDev/wesnothLearning/acceptance_native_seed_20261031/src`.

```sh
cd ~/myDev/wesnothLearning/acceptance_native_seed_20261031/src
export WESNOTH_EXE=$HOME/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth
export PYTHONPATH="$PWD:$PWD/vendor/arena"
PY=$HOME/venv/bin/python

# 1. the shim, exactly as setup.sh builds it
mkdir -p .runtime
cc -O2 -fPIC -shared -o .runtime/entropy.so vendor/arena/entropy.c -ldl
nm -D .runtime/entropy.so | grep -E ' (open|open64|read|__read_chk|close|getrandom|getentropy)$'
# close / getentropy / getrandom / open / open64 / read / __read_chk — all seven interposed

# 2. the no-seed caller still works (the math.randomseed nil guard)
$PY -m unittest tests.test_schedule -v          # Ran 8 tests … OK

# 3. the acceptance probe, twice, into separate directories
$PY tests/smoke_native_repeat.py --wesnoth "$WESNOTH_EXE" --output verification/native_seed_20261031/probe
$PY tests/smoke_native_repeat.py --wesnoth "$WESNOTH_EXE" --output verification/native_seed_20261031/probe2
diff verification/native_seed_20261031/probe/repeat.json verification/native_seed_20261031/probe2/repeat.json
diff verification/native_seed_20261031/probe/first.replay.events.jsonl \
     verification/native_seed_20261031/probe2/first.replay.events.jsonl

# 4. a second seed proves the stream is derived from the seed, not from one fixed constant
$PY tests/smoke_native_repeat.py --wesnoth "$WESNOTH_EXE" \
  --output verification/native_seed_20261031/probe_seed2 --seed 20261018

# 5. negative control: same tree, entropy shim not preloaded (`_child_env` returns the plain env)
#    run from ~/myDev/wesnothLearning/acceptance_native_seed_20261031/noshim
$PY tests/smoke_native_repeat.py --wesnoth "$WESNOTH_EXE" --output ../negcontrol

env | grep ARENA_ENTROPY_SEED        # no output: the variable never reaches the parent shell
```

## Result

| run | seed | turns | decisive events | `events_equal` | exit |
| --- | --- | --- | --- | --- | --- |
| `probe` | 20261017 | 5 / 5 | 11 / 11 | true | 0 |
| `probe2` (separate invocation) | 20261017 | 5 / 5 | 11 / 11 | true | 0 |
| `probe_seed2` | 20261018 | 6 / 6 | 14 / 14 | true | 0 |
| same tree, shim not preloaded | 20261017 | 15 / 2 | 32 / 5 | false | 1 |
| archived pre-fix probe | 20261017 | 5 / 3 | 12 / 7 | false | — |

Both `repeat.json` files are identical (`diff` printed nothing), the two
`first.replay.events.jsonl` streams are identical, and the two `probe` games report the same
`reason` (`last_leader`) and `seed`. Seed 20261018 ends at turn 6 with 14 events, so the stream
follows the seed rather than one frozen constant. With the preload disabled and Lua still seeded
from the same value, the two games diverge at turns 15 and 2 — the shim, not the Lua seeding, is
what makes a stock C++ baseline replay.

The archived pre-fix run is `verification/acceptance_20261031/L1/native_repeat/repeat.json`
(seed 20261017, turns 5 vs 3, `events_equal: false`); it is quoted, not rerun.

## Limits

- One stock `baseline` vs `baseline` duel on the default arena2 map with `map_override` absent and
  `max_turns` 30. Other formats, maps, contests and turn caps are not exercised here.
- The pinned stream is not the previous OS-entropy stream, so the seeded duel ends at turn 5
  rather than at the old 5 or 3; the criterion is equality between runs of one seed, not
  reproduction of an older outcome. The seed was not tuned to force a winner.
- Exported Lua candidates now inherit the seed too (`math.random` is the only random source in
  `lua/network.lua`); that is intended but only the stock C++ baseline is measured here.
- Native play is still stochastic across different seeds, so cross-seed comparison uses recorded
  counts only, and no lite/native equality is claimed.
- The shim is a glibc `LD_PRELOAD` object: Linux x86_64 only. On Windows, or without
  `.runtime/entropy.so`, the child runs unshimmed and only the Lua seed applies.
- No convergence, playing-strength or training claim; no collection or training was run.

## Identities

```text
commit                                  bd1bc211bc4c258f203552a6e193b117b213f3ac
source tarball                          dd300db922c73de68f227643b20b3433cc4663f9446e219b9d1dcdaf86b2a621
vendor/arena/entropy.c                  707dd06bf27494a7c5b17631486a14e71b16d7949eec2c5845c811259af80bd7
vendor/arena/match.py                   ebdde7eb92bb425730727f96530253b920a6027ecb49de47009d26baf63692b0
vendor/arena/runtime/runtime.lua        dd75b50e87368ab446517b13736918f35d345b2b74d69bb95e050cb10da9325a
setup.sh                                31c2c71e0bca3440412cc9dc75e75560f1ad147ba9eb26428d39e0258391b31a
tests/smoke_native_repeat.py            5811e52c30d6cbb4e3067f21d6f92309c0a3253e169e8258e67ac45e2fa11df5
.runtime/entropy.so (built)             f12d763303445aa437de06d0dba129dc923e3d81fd1fc82d72b8e331916480cf
Wesnoth .runtime/install/bin/wesnoth    33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf
probe/repeat.json                       7d567f16b8ba4205f8489e3c37840f01a17013d072dfa85614d02998eeb82a60
probe2/repeat.json                      7d567f16b8ba4205f8489e3c37840f01a17013d072dfa85614d02998eeb82a60
probe_seed2/repeat.json                 68018ea5f2b11efbd307ebfe8aa5be584f376f2e6fe69f360f5d5529c16011a1
negcontrol/repeat.json                  68f7ea008522766e8976b80f265602ef0e221579ae2bd3a712bb680d4922d46c
```

The per-run `*.replay.events.jsonl`, `*.replay.log` and replay files stay on the host under
`~/myDev/wesnothLearning/acceptance_native_seed_20261031/src/verification/native_seed_20261031/`;
they are regenerated by the probe commands above.
