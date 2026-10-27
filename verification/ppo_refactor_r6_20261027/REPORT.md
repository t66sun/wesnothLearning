# R6 explicit reward-row semantics — 2026-10-27

Issue #62, parent #48. Implementation/acceptance source `30cd046fe0f3a1f4e3ee17c41631b8d1d7f5c2cc`, based on R5 main `9fb8fe2`.

## Result

The shared shard writer used by native and lite emits reward metadata schema 6: `terminal_reward` carries the game outcome and `reward_step` carries the original shaped own-turn transition reward. The ambiguous `reward` field is removed from new stored rows. Raw reward terms, post-action terms, potentials and bootstrap data remain. Policy feature schema stays 5 and rowpack stays v2; neither vectors nor checkpoint model compatibility changes. The manifest freezes `row_schema=6` separately.

Schema 5 remains readable/trainable using its terminal `reward`; schema 6 reads the named terminal field only on a non-truncated terminal transition. `advantages` recomputes each step and rejects inconsistent recorded steps. Both primary and rehearsal rows must have one homogeneous schema. Reward metrics read/audit new fields. Reward formula, summation order, coefficients, gamma, lambda and optimizer defaults are unchanged.

The writer makes a scalar-only lookahead pass, retaining one small reward context per side and one scalar per row; it does not retain observations/candidates or rebuild the raw row list. Output order is preserved. Teacher/human rows without sufficient raw/terminal-bootstrap evidence store an explicit unknown (`reward_step=null`); policy rows require a finite step reward and cannot train on missing evidence. This preserves honest BC label handling without inventing a reward target.

## Local reference and unresolved attempts

- The new writer assertion first failed on schema 5 versus 6 after correcting the test's unpack API use. Four new reward-schema tests then passed (3.948 s), including the five-step hand oracle, bitwise legacy/new GAE, mismatch rejection, truncation and homogeneous 5/6 training.
- The current valid reward, reward-metrics, rowpack and scenario checks passed: 32 tests, 6.497 s. Manifest checks passed: 3 tests, 0.955 s.
- A broader affected-module attempt ran 38 checks: **29 PASS, 3 FAIL, 6 ERROR** (38.429 s). Remaining failures are explicitly not acceptance: old core/revision fixtures stamp invalid Astra RNG/combat identities (five errors), the SDK fixture fails checkpoint identity (one error), old expected parameter count differs, sequence-payload fixture lacks R1's explicit split-rule field, and local real-collector adapter rejects the installed extension's `lite-0.1` identity. A read-only pre-R6 validator probe reproduces `Astra teacher engine/combat identity differs` on the old core fixture; model/export source and these old identities were not repaired in this phase.
- A second bounded 21-check attempt passed 19 and had **1 FAIL / 1 ERROR** (2.576 s): the same local extension mismatch on actor isolation, and the grandfathered shard fixture's bootstrap supplies `raw=0.2` without `reward_raw`, which cannot establish a schema-6 policy step reward. That fixture remains **not passed**, and is not edited or counted as a pass. Proper reward-raw bootstrap behavior is covered by the new truncation oracle. The file's reward-metrics section itself passes.

No full suite was run and no gate was weakened to make these attempts green. The local extension was not rebuilt for an unrelated metadata change. Ubuntu uses the already accepted current extension and supplies acceptance for the affected real collector/actor-isolation paths.

## Ubuntu isolated acceptance

Directory `/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r6_20261027_30cd046`; shared dependencies and read-only frozen inputs reused. Python 3.12.3, torch 2.9.1+cpu; rules hash `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`. [Environment](ubuntu/environment.log).

Source-only archive: 2,099,200 bytes, SHA-256 `9323968ae82e6ad6f4ca34f3a7d24a452f9ba051a4f778f26ec9f3a4a4e6f944`. Includes parent `learning/data.py` solely for the arithmetic baseline/revert. Baseline file SHA-256 `a891c8722652cecd71039c257185135b7c4925e0d9ec61d0520ef868e15b8474`.

```powershell
scp tmp/refactor_r6_20261027/source.tar cpuServer:/tmp/wesnoth-r6-30cd046.tar
scp verification/ppo_refactor_r6_20261027/run_ubuntu.sh cpuServer:/tmp/wesnoth-r6-30cd046.sh
ssh cpuServer "bash /tmp/wesnoth-r6-30cd046.sh 9323968ae82e6ad6f4ca34f3a7d24a452f9ba051a4f778f26ec9f3a4a4e6f944"
```

[Script](run_ubuntu.sh) specifies the 37 focused unittest checks. It runs only the reward section of the grandfathered pipeline file plus actor isolation; no source/test growth there. Pytest remains unavailable; stdlib unittest runs the same assertions.

| Check | Observed | Evidence |
| --- | --- | --- |
| Reward/schema/metrics/rowpack/scenario/manifest and real collector/actor isolation | 37 PASS, 2.921 s | [targeted](ubuntu/targeted.log) |
| All 421 frozen duel-v99 rows against parent GAE; legacy 5 and derived-in-memory 6 | Float64 GAE and returns bit-identical; four input hashes unchanged | [parity](ubuntu/frozen_parity.log), [probe](frozen_parity.py) |
| Parent writer restored; named reward-row assertion | Expected FAIL: schema 5 versus 6 | [reverted](ubuntu/reverted.log) |
| Fixed writer restored; repeat assertion | PASS | [restored](ubuntu/restored.log) |
| Source before/after revert | Identical | [before](ubuntu/source_before.sha256), [after](ubuntu/source_after.sha256), [status](ubuntu/status.log) |

The frozen parity probe reads every row, including validation rows, solely for arithmetic comparison; it does not admit them to an optimizer, change their partitions or persist converted rows. Its four input hashes are recorded in the raw log.

## Limits

Acceptance covers the named R6 contract, not the unresolved local/legacy attempts above. No native game, real-rule match, new corpus, historical re-encoding, full suite or formal training occurred; synthetic fixture steps/updates prove wiring only. No convergence/strength claim. Existing R1–R5 evidence is reused where unchanged. R7–R10, native capture fixtures, N1 and existing numerical/package failures remain open. Compatible schema-6 qualified rehearsal data remains a prerequisite for a new run; this report grants no collection permission.
