# Open blockers — 2026-10-31

Temporary working note; delete this file when the list is empty or the task it serves ends.
Each blocker states the measured evidence and the smallest action that would clear it. The
host-memory blocker is absent on purpose: it was cleared on 2026-10-31
(`verification/server_release_20261031/REPORT.md` — 32 orphaned pool workers released, 14 GB
available). The BC start-block blocker is absent for the same reason: it was cleared on 2026-10-31
(`verification/curated_bc_20261031/REPORT.md` — three lobby-archive replays played by official
1.18.8 and imported as 84 BC rows).

## 1. The Windows reference host cannot start native work

**Evidence:** `.runtime/` is absent and no Wesnoth is installed on the Windows box, so N1, L1 and R3
cannot start there.

**Solution:** run on the Ubuntu acceptance host. `~/myDev/wesnothLearning/WesnothLearning/.runtime/
build/wesnoth` reports `Battle for Wesnoth v1.18.8 x86_64`, so no rebuild is needed.

## 2. Only 197 of the 1,076 curated games match the frozen rules version

**Evidence:** `learning/human.py:58` returns `other_version` for anything but 1.18.8. Corpus
versions: 1.18.8 197 · 1.18.3 290 · 1.18.7 218 · 1.18.0 210 · 1.18.5 66 · 1.18.2 46 · 1.18.1 27 ·
1.18.6 17 · 1.18.4 5.

**Solution:** enable the 197 matching games first; keep the rest as staging until a version policy
exists. Freezing rule snapshots per old version costs more than it returns.

## 3. `mp_checkup` is not recognised by the curator

**Evidence:** the checkup handling in `learning/replay_curate.py` matches the `checkup` tag only.
Two games use `mp_checkup` (1,344 commands in `06/2p__Weldyn_Channel_Turn_18_(1927).bz2`, 252 in
`28/2p__Hamlets_Turn_5_(11853).bz2`), so their per-action sync is invisible to duplicate and
prefix detection.

**Solution:** accept both tags in the same branch, and add an assertion that fails when the
`mp_checkup` case is dropped again.

## 4. The Ubuntu host has no `git`, no GitHub and no PyPI

**Evidence:** `git` is not installed; `github.com` and `pypi.org` time out; `sudo -n` requires a
password, so neither can be fixed at the system level. Reachable: the Tsinghua PyPI mirror and
`archive.ubuntu.com`.

**Solution:** ship source with `git bundle create` or a source tarball over `scp` (byte-level
replacement already works) and install packages with
`PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple`.

## 5. The checkout on that host is stale, and no convergence or strength evidence exists

**Evidence:** `unittest tests.test_replay_curate` in `~/myDev/wesnothLearning/WesnothLearning` runs
8 tests instead of the current 11, so it predates the archive, provenance and LF work.
`docs/architecture.md:205-211` states that no run has a convergence or playing-strength claim.

**Solution:** sync the checkout by the route in blocker 5, then run the reduced full loop from
`docs/TEST.md` (L1) and archive the result under a new dated `verification/` directory.

## 6. A native game cannot be reproduced from its seed

**Evidence:** one stock game (two `baseline` bots, `map_override` absent, `max_turns` 30) played twice
from seed `20261017` ended `last_leader` at turn 5 and turn 3 with different decisive event streams
(`verification/acceptance_20261031/L1/native_repeat/repeat.json`). The twin L1 run reproduced the
same 40 teacher job ids, seeds and map yet shared 0 of 40 payloads
(`verification/acceptance_20261031/L1/same_future.json`). `learning/schedule.py:152` derives those
seeds as `random.Random(seed + batch_index)`, so the identity is recorded but insufficient.

**Solution:** make native play deterministic for a recorded identity before any acceptance clause
compares one run against another — pin the AI's own RNG consumption (Wesnoth seeds the Lua `math.random`
separately) and re-run the two-game probe as the assertion. Until then, compare independent runs only
through recorded counts.

## Not blockers

- PKG1 (training-bundle acceptance) was dropped by the operator, so it needs nothing.
- Lite rules approximate 470 of 587 units: a declared limit that only forbids native-equivalence
  claims, not training progress.
