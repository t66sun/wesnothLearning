# Native teacher ambush interruption — 2026-11-03

The full R3 panel exposed an execution fault shared by the adapted and frozen
teachers. A successful native move can reveal a forest Wose and return
`ok=false, status=2005` after changing the board. The teacher asserted `ok` and
the arena therefore disqualified the side. The maintained duel/four/eight move
helpers now stop the current plan on that specific status. Other move errors
retain the existing failure behavior. The frozen opponent archive is unchanged.

## Identity and commands

Both sources were shipped with `git archive --format=tar` and extracted into
fresh directories on Ubuntu `cpuServer`:

| Phase | Source | Archive SHA256 | Ubuntu directory |
| --- | --- | --- | --- |
| Red | `c630976e5435c9ffcf680476abbcc19c959a6a18` | `e2b51913ba4e5ea641302213984b39dd0aea7a0da841cc33b4f800193a9ce5e4` | `/home/tongshu/acceptance/teacher_ambush_red_20261103` |
| Green | `c4907460eb157d34acbadbb6b23d4b02b45e1ced` | `20ced4fbd896230a03f18bb51ee2224a7b58854256a4288d38310ffb9e4176ed` | `/home/tongshu/acceptance/teacher_ambush_fixed_20261103` |

Local and remote archive hashes match. Native executable SHA256 is
`33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf`
(Wesnoth 1.18.8); rules are `wesnoth-1.18.8-native-v2`. The existing entropy shim
was built from each extracted source with `cc -O2 -fPIC -shared -o
.runtime/entropy.so vendor/arena/entropy.c -ldl`; both builds hash to
`f12d763303445aa437de06d0dba129dc923e3d81fd1fc82d72b8e331916480cf`.
The teacher profile remains `probabilistic_combat_v6`; source identity changes
from `d0eb8d922b0c5b8092863ff712b9f2b4df097ac3653d90432c5d2d906aa87a38`
to `24aa546bbcce6670b0baef8751730d64c229b37cfe608d6cc59fd3e4c211eb98`.

From each extracted root, with `PYTHONPATH=<root>:<root>/vendor/arena`,
`OMP_NUM_THREADS=1`, `SDL_VIDEODRIVER=dummy`, `SDL_AUDIODRIVER=dummy`:

```sh
/home/tongshu/venv/bin/python -m unittest tests.v5.test_teacher_movement -v
/home/tongshu/venv/bin/python tests/diagnose_teacher_ambush.py \
  --wesnoth /home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth \
  --source <source-above> --output native
```

The red command used the abbreviated source label `c630976`; the green command
used its full commit. The shell's final display command received a trailing CR
from PowerShell and failed to display the native log in both phases. This was
after the test processes and `exit-codes.txt` writes; the logs were subsequently
read directly. No test was rerun for that display error.

## Observed results

| Check | Red | Green |
| --- | --- | --- |
| Ambush stops the old combat plan, three strategies | Three assertion errors | PASS |
| Normal arrival executes the planned attack, three strategies | PASS | PASS |
| Other native move error remains a failure, three strategies | PASS | PASS |
| Real native four-player teacher module execution | Assertion at `four.lua:314`, side disqualified | PASS, zero faults |

The Python suite is three tests with three strategy subcases each; red exits 1
and green exits 0. It takes 0.006 s / 0.005 s. Each native fixture runs once,
seed 713, one action, maximum one turn; red exits 1 and green exits 0, with
native game durations 1.0698 s / 1.0661 s.

The native fixture delegates to the actual teacher `execution`, not the shared
candidate executor. A visible board contains a hidden Wose on `Gs^Ft`; before
execution `ai.check_move` succeeds and the Wose is absent from the visible enemy
list. Both runs record `status=2005, ok=false, gamestate_changed=true` after the
actor moves from `(4,3)` to `(3,4)`. Green then records zero attack calls, the
actor at `(3,4)`, and the Wose visible. Thus the actual native path proves that
the old attack plan is stopped, in addition to the mocked regression.

Raw logs, exit codes, staged fixture add-ons, summaries, event streams and native
replays are preserved under `red/` and `green/`. The unmodified production
teacher fails the same fixture that passes after the three-line-per-helper fix.

## Scope

No collection, training or Windows tests ran. No forecast, scoring, RNG,
candidate-generation, production RPC or frozen opponent package changed. The
existing combat and 18 legal-board evidence remains applicable to those
unchanged behaviors. This accepts only the ambush interruption fix, not R3
strength or complete native/Lite equivalence. A new complete R3 panel remains a
separate evaluation. The two grandfathered oversized tests are unchanged; every
changed source file is below 1000 lines. `git diff --check` passes.
