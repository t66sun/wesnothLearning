# R8 stock RCA capture — partial implementation, NOT accepted

Date: 2026-10-28 (Asia/Shanghai). Parent #48, task #66. Branch `codex/r8-stock-event-capture`.
R1–R7 are merged; master is `aa7744c8f7e040da7e4f0f89fc0c28785de4d39b` at handoff.
R8 is preserved for review; it must not be treated as accepted or training-ready. R9/R10 are unimplemented.

## Implementation and identities

- `f97b142f4060b4ca494d5b14d539d0f228e73798`: stock engine-event handlers, a zero-score observer CA, fresh-context matching, per-kind unmatched/ambiguous counts, capture/runtime provenance. Stock controllers are not replaced. Shared candidates receive legal public observations; referee SNAPSHOTs are used only for comparison, never labels.
- `4d4144f5ff2e9587639dfea22bd9a3c3bd1c2d65`: fixed the detached recruit probe's facing to avoid a native default-RNG draw; strengthened the attack assertion through the actual Lua handler. This does not prove total capture noninterference.
- Archive A SHA-256: `d5dcd4ac2cc347c86560e57ee914dd86a95778aad1cde96b7c27c07ec8de37fd` (2,119,680 bytes).
- Archive B SHA-256: `592a77d109c1373999e869ac0b9fc39b12677a94ca1d07560995c49cda87a1dd`.
- Runtime SHA-256: `33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf`; native 1.18.8.
- Rules SHA-256: `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`.
- Ubuntu Python 3.12.3, torch 2.9.1+cpu, existing shared environment. No dependency installation. Tests use stdlib unittest; pytest is unavailable.

Server roots:

```text
/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r8_20261028_a
/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r8_20261028_control
/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r8_20261028_b
```

All source/rule inputs and old runs remained read-only. New fixtures are capability evidence, not an imported corpus.

## Observed checks

| Check | Result | Evidence |
| --- | --- | --- |
| Local original affected checks | 13 passed | `python -m unittest tests.v5.test_native_capture tests.v5.test_teacher_identity tests.v5.test_reward_row_schema -v`; observed before archive A |
| Ubuntu same affected checks, source A | 13 passed, 1.467 s | [targeted](ubuntu_a/targeted.log) |
| Local strengthened capture/probe checks | 4 passed | [local restored](probe_restored.local.log); later strengthened handler path also passed before commit B |
| Ubuntu strengthened capture/probe checks, source B | 4 passed, 0.646 s | [targeted](crash_recovered/ubuntu_b/targeted.log) |
| Lua syntax, source B | 4 files passed | [syntax](crash_recovered/ubuntu_b/lua_syntax.log) |
| Remove attack handler / remove fixed facing | Both fail (exit 1); restoring both passes | [attack](crash_recovered/ubuntu_b/attack_reverted.log), [facing](crash_recovered/ubuntu_b/facing_reverted.log), [restored](crash_recovered/ubuntu_b/restored.log) |
| Fault-injection restoration | Source hashes identical | [before](crash_recovered/ubuntu_b/source_before.sha256), [after](crash_recovered/ubuntu_b/source_after.sha256), [status](crash_recovered/ubuntu_b/status.log) |
| FX1 stock capture on/off | **FAILED**: per-turn SNAPSHOTs differ; stable RESULT and TURN/TURN_END comparison passed before failure | [original failure](ubuntu_a/native.log), `native_probe.py` |
| FX2 labels from existing FX1 events | Measured, partial; no quality acceptance | [analysis](ubuntu_a/recorded_analysis.json), raw `capture_on.events.jsonl.gz` |
| FX3 API surface | Two read-only evaluation contexts expose no `teacher_turn`/`play_turn`; full takeover **NOT RUN / NOT PROVEN** | [capability records](ubuntu_a/recorded_analysis.json) |

Three games total, one arena2 duel scenario, seed 20261028, Loyalists/Rebels, maximum five turns each; both first games ended at turn 2. The third game repeats the uninstrumented control once, rather than retrying acceptance. No more native games were run. Source B supplemental checks do not start a game.

### FX2 coverage

| Event | Matched | Unmatched | Ambiguous | Status in this fixture |
| --- | ---: | ---: | ---: | --- |
| recruit | 3 | 9 | 0 | Partial |
| moveto | 3 | 0 | 2 | Partial; ambiguous choices are -1 and excluded from exact accuracy |
| attack | 0 | 2 | 0 | Uncovered in native evidence; synthetic handler-to-label path passes |
| recall | 0 | 0 | 0 | Not exercised; no matching policy action implemented |
| advance | 0 | 0 | 0 | Not exercised; no matching policy action implemented |

Eight public-context rows, six exact labels; all 19 observed engine actions are accounted for. No LEARN frames came from stock side controllers. A context can supervise only its first event; later events remain unmatched. This is not full stock-CA pre-action coverage, and silent state changes between CA evaluation and its first event have not been comprehensively audited. Existing per-kind BC and scenario gates remain unchanged; these data do not establish a passing BC gate.

## FX1 failure diagnosis and remaining work

The same seed does not freeze every native random source. Actual installed 1.18.8 sources show `--rng-seed` calls C `srand`, while the default RNG is separately initialized from system entropy. Recruitment uses that RNG, including tie shuffling; detached unit construction also draws a random facing when none is specified. Source paths, hashes and excerpts are in [native_rng_source.json](ubuntu_a/native_rng_source.json).

The independent, capture-off repeat also differs from the first capture-off game ([comparison](ubuntu_a/comparison.json)). This demonstrates that the original equality comparison has an uncontrolled source. It does **not** prove that capture is harmless, and does not waive the failed gate. The facing draw is repaired in source B and tested at the external constructor boundary; native on/off comparison after that repair is **NOT RUN** because the three-game budget is exhausted.

Next owner must resolve the noninterference acceptance design without changing production randomness or weakening the gate, audit genuinely fresh pre-action contexts, and improve/document label coverage. A different seed, repeated retries or an unchanged final winner is not sufficient evidence. Full takeover remains unproven; R9 must conservatively retain stock query=none unless separately proven. R9 stock BC scheduling/DAgger retirement and R10 bundle/export/corpus/report identities have not been implemented. Existing R4 scenario insufficiency, R5 qualified-rehearsal prerequisite, R6 recorded local failures, N1 and numerical/package failures remain open.

Event API reference: [official EventWML](https://wiki.wesnoth.org/EventWML). Runtime behavior was checked against installed 1.18.8, not inferred from newer development documentation.

## Crash audit and recovery

The user's Windows crash zeroed the current branch ref (41 NUL bytes) and nine newly downloaded archive-B evidence files. The index and tracked working files still matched commit `4d4144f`; both implementation commits and reflog were intact. Only the damaged branch ref was restored from that verified commit. `git fsck --full --no-reflogs --no-dangling` then exited 0; no tracked source or committed history loss was found. Both local scratch archive hashes still match their transmitted identities.

The nine logs were re-fetched into **new** `crash_recovered/ubuntu_b/` and every SHA-256 matches the server. Corrupt local copies in `ubuntu_b/` are not valid evidence and are not included as passing logs. See [damage inventory](crash_audit/evidence_damage.json), [server hashes](crash_audit/remote_b.sha256), [verified recovery](crash_audit/recovered_checks.json), [archive checks](crash_audit/scratch_archives.json). Original damaged ref bytes are retained in `crash_audit/branch_ref_before.bin`. No R8 native/probe process remained at the final status check. This audit covers this repository and these experiment artifacts, not the rest of the computer.

## Handoff / 接手说明

按 `docs/ppo_refactor_plan.md` / `_zh.md` 接手，先读 AGENTS、architecture、TEST 和本报告。R1–R7 在 master；R8 留在当前分支/草稿 PR，不能当作已验收。先复核当前实现，处理 FX1、真实动作前上下文与攻击覆盖不足，再分别推进 R9/R10。不要合并前把失败改成通过；三个原版短局额度已用完，复用记录，新对局需另行授权。当前只收尾交接，没有启动正式训练、扩采、调参、降低门禁或重跑全套。
