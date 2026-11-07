# Frozen teacher role routing

Ubuntu acceptance, 2026-11-07. Final implementation: `a5c1fa00e12e716c9c4c630e696839a7b0fed4f7`; baseline: `a8d4af7`.

All four experiment consumers now resolve per-format teacher roles: supervision, fixed opponents, evaluation and reward references. Mixed execution is explicit; the default remains Astra pending the authorized 48-game panel. Official baseline, opponent proportions, teammate rotation, candidate tensors, task and reward equations remain unchanged.

BC game quotas require the current teacher identity and complete original games. Reward reference cache keys bind teacher, backend, rules and task. Checkpoints and progress exports preserve separate role identities. Branches with a different execution identity require weights-only initialization. The training bundle carries the exact delivered teacher ZIP and manifest; other delivery output remains excluded.

## Checks

Each command ran in a fresh `git archive` extraction on `cpuServer`, using the isolated `teacher-host-v1` release build. The source, command, full output and exit code are preserved in each directory below.

| Check | Commit | Result |
|---|---|---|
| [Initial affected suites](checks/20261107T074407_roles_fixed_efaeff62ad66/output.txt) | `efaeff62ad6604ace43622d973c2670a001f28a4` | 120 tests; 2 failures and 3 errors retained |
| [Affected fixes](checks/20261107T074514_roles_fixes_54f645159e45/output.txt) | `54f645159e45702b5ea5e8ab9121c35b0d394a11` | 26 tests; 25 passed, one legacy report-label regression |
| [Legacy label](checks/20261107T074539_roles_legacy_8114eb5f0d58/output.txt) | `8114eb5f0d589ddd51b5489dd5159d7027e4e6ce` | 3 passed |
| [Independent deployment and progress export assertions](checks/20261107T075123_roles_exports_a5c1fa00e12e/output.txt) | `a5c1fa00e12e716c9c4c630e696839a7b0fed4f7` | 2 passed |

The 122 distinct tests pass at their final affected revisions. Fixed defects: legacy identity lookup accessed absent modern metadata; the legacy calibration label changed. New fixtures now supply the existing task and BC gate contract and apply the production 30-turn override. Faction assertions check the existing six-faction schedule coverage, including per-seat coverage for 2v2; they do not alter scheduling.

Coverage includes six role/backend cells, independent evaluation/reference routing, unchanged PPO pool and teammate composition, teacher quota filtering, reference cache isolation, legacy controller arithmetic, teacher contract/provenance, mixed export, bundle validation, progress planning, branch reset, frozen BC anchors and reward metrics. The progress check exports actual model weights and loads the frozen policy/control configuration without launching games or optimization.

Standards and specification reviews completed independently. The sole standards finding (bundle tests depended on production required-file constants) was fixed with independently named paths, byte assertions and missing-member rejection; the follow-up review closed it. No open findings.

These fixed tests establish routing and compatibility. They do not establish sampling coverage, throughput, BC qualification, student strength or Native/Lite equivalence. No formal corpus collection or neural training ran. The 48-game panel remains the default-activation gate.
