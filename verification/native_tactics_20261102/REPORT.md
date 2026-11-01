# Six native/lite tactical comparisons

Ubuntu `cpuServer`, source `b5bb94a6f2ddd112009be4d8697b9c1941816046`, extracted to `/home/tongshu/acceptance/native_tactical_audit_20261102` from `git archive`. Rules SHA-256: `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`. Native executable: `33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf` (installed Wesnoth 1.18.8). Full transport identity is in `tactical/summary.json`.

Only the opt-in differential probe gains native weapon number/name/damage/strike-count fields. Normal training and native deployment never load this probe. The runner reuses six legal, visible starting positions and checks that each requested attack is legal in both engines and that lite forecast HP matches its execution. Initial unit type, side, position, HP, moves, attacks and XP match between engines for all six recorded inputs. Native probabilities come from `wesnoth.simulate_combat`, not frequencies inferred from one random battle.

```bash
cc -O2 -fPIC -shared -o .runtime/entropy.so vendor/arena/entropy.c -ldl
PYTHONPATH=.:vendor/arena OMP_NUM_THREADS=1 timeout --signal=TERM --kill-after=10 360 \
  /home/tongshu/venv/bin/python -u tests/diagnose_native_tactics.py \
  --rules data/rules/1.18.8-training \
  --wesnoth /home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/install/bin/wesnoth \
  --source b5bb94a6f2ddd112009be4d8697b9c1941816046 --output tactical
```

Completed **six cases**, exit 0, 7.668 seconds; no case was skipped. The preceding BC experiment had exited. A read-only checkpoint audit briefly overlapped; no timing performance claim is made. Raw commands' output, errors, exit code, complete public inputs/legal sets, forecasts and actual strikes are preserved beside this report.

| Fixed public position | Native probability/result | Lite result |
| --- | --- | --- |
| Elvish Fighter attacks 14-HP Orcish Grunt | kill probability 47.52% | certain kill |
| 8-HP Elvish Fighter attacks healthy Grunt | attacker death probability 84% | certain death |
| Orcish Assassin poisons Elvish Fighter | poison probability 93.6% | certain poison |
| Elvish Shaman slows Grunt | slow probability 84% | certain slow |
| Skeleton attacks Dwarvish Fighter | hammer retaliation, 10 damage × 2 blows before hit rolls; Skeleton mean remaining HP 22 | axe retaliation, three 3-HP hits; Skeleton HP 25 |
| Mage attacks Grunt at range | no retaliation; Grunt mean HP 23.3 | no retaliation; Grunt HP 20 |

The resistance-sensitive choice is an actionable semantic gap: the original game's `src/actions/attack.cpp:570` evaluates available matching-range weapons through modified combat statistics and simulation. Lite's `combat::counter_weapon` chooses raw damage × strikes without the attacker's resistance. The recorded three retaliations match the captured axe, whereas native explicitly reports weapon 2, hammer.

Kill/death/status differences are structural consequences of the declared deterministic `expected_damage_v1` surrogate, not newly introduced random bugs. This audit does not relax native-semantic acceptance or claim native playing strength. Item 5 stays open. Next implementation should separately version and test a retaliation selector against these public cases while maintaining forecast/execution agreement; probability-sensitive tactical transfer still needs native training/selection evidence or an explicit surrogate redesign. Teacher-policy ranking and the full R3 comparison were not run by this audit.
