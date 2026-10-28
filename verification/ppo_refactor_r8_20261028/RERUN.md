# R8 stock capture: controlled noninterference and real pre-action contexts — rerun 2026-10-28

Issue #64, parent #48. Implementation `45e7146a376f8f1088c3303b94e28746f31092ef`, based on the review branch head `a8ce506`. The earlier attempt in this directory ([REPORT.md](REPORT.md)) failed FX1 and matched only part of FX2; this report supersedes its result and leaves that record untouched.

## Result

The three FX gates now have observed answers on a controlled native run: FX1 passes, FX2 accounts for every watched engine event with no unmatched event, and FX3 records that no per-turn or per-decision query hook exists.

Two defects were fixed.

* **FX1 was uncomparable, not nondeterministic behaviour.** Native `--rng-seed` only calls `srand` (`src/game.cpp` command-line option); the default randomness instance that the stock AI's `std::shuffle`/`do_randomness` and the unit constructor's default facing draw from is seeded from `boost::random_device`. This build's `libboost_random` imports `open` and `__read_chk` and reads `/dev/urandom`, so [deterministic_entropy.c](deterministic_entropy.c) interposes those calls (plus `getrandom`/`getentropy`) with a fixed xorshift stream and is loaded with `LD_PRELOAD` for all three runs. Production randomness is untouched.
* **FX2 was a wrong decision boundary.** A stock decision can execute several engine events: one recruitment decision places a whole batch of units, and a chosen move may end in an attack. The observer candidate action scores zero, so the candidate loop evaluates it before the engine picks its next action; publishing one public context per evaluation makes each context precede the action it labels. The previous post-action/derived-context design is gone: inside WML event handlers the Lua global `ai` does not exist, so `candidates.lua` cannot run there (`attempt to index a nil value (global 'ai')`). The labeler now folds every event that shares a context into that one decision — a move plus its strike becomes one `move_attack` label and the rest of a recruit batch is counted as `merged` and kept on the row as `extra_actions`. A context is superseded by the next `CONTEXT` and retired by `INVALIDATE` on side turn or turn refresh, so no stale context can label a later action. `AFTER` patches the row with the memory write of the decision's last event.

## Local reference

`tests/v5/test_native_capture.py` replaces the derived-context fixtures with decision-boundary ones: context precedes the action, a guard event retires an unused context, a recruit burst is one decision, a move and its attack share one decision, a stale context cannot label a later action, hidden/ambiguous actions stay unlabelled. `learning/stock_rca.py` stores the matched candidate itself as the label, so `validate_record` can compare every field of the executed intent.

## Ubuntu isolated acceptance

Directory `/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r8b_20261028`; existing read-only data reused. Python 3.12.3, torch 2.9.1+cpu; Wesnoth 1.18.8 runtime SHA-256 `33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf`; rule SHA-256 `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`; entropy shim SHA-256 `c5b31dd29138ee747f20033e66642255bc6eae79e72c85baf9e5b4899ffccd09`. [Environment](rerun/logs/environment.log).

Source-only archive: 7,547,904 bytes; SHA-256 `e3b942c647aad69f0529cd67310ee5c69435aca368ee1f3df3c9e7777bd359a3`.

```powershell
scp tmp/r8b/source.tar cpuServer:/tmp/wesnoth-r8b-45e7146.tar
scp verification/ppo_refactor_r8_20261028/rerun_ubuntu.sh cpuServer:/tmp/wesnoth-r8b-45e7146.sh
ssh cpuServer "bash /tmp/wesnoth-r8b-45e7146.sh e3b942c647aad69f0529cd67310ee5c69435aca368ee1f3df3c9e7777bd359a3"
scp verification/ppo_refactor_r8_20261028/revert_ubuntu.sh cpuServer:/tmp/wesnoth-r8b-revert.sh
ssh cpuServer "bash /tmp/wesnoth-r8b-revert.sh"
```

| Check | Observed | Evidence |
| --- | --- | --- |
| Targeted capture, teacher-identity and reward-row checks | 19 PASS, 1.507 s | [targeted](rerun/logs/targeted.log) |
| FX1 — capture-off twice, then capture-on, all with frozen entropy | Engine-event streams byte-identical: `7f5a38852981e9f6db257510e0c43e6d853a579647949d986578a17b8eaa4bb5` for off, off-repeat and on; stable `RESULT` keys equal | [probe](rerun/fixture/probe.json), [native](rerun/logs/native.log) |
| FX2 — per-kind accounting | recruit 11 events → 2 matched, 9 merged, 0 unmatched; moveto 8 → 1 matched, 2 ambiguous, 5 merged, 0 unmatched; attack 5 → 3 matched, 2 ambiguous, 0 unmatched; recall/advance 0 events. 16 contexts, 2 invalidated, 10 labels, 6 exact | [probe](rerun/fixture/probe.json) |
| FX3 — takeover surface | `takeover='unsupported_with_stock_rca'`; 2 capability probes, 6 hook probes, no callable `teacher_turn`/`play_turn`/`take_turn` | [probe](rerun/fixture/probe.json) |
| Decision folding reverted; two named tests | Expected FAIL: `test_recruit_burst_is_one_engine_decision` (error) and `test_move_and_attack_share_one_decision` (failure) | [reverted](rerun/logs/fold_reverted.log) |
| Observer context emission reverted; probe | Expected FAIL: `AssertionError: ('recruit', {'matched': 0, 'unmatched': 11, ...})` | [reverted](rerun/logs/observer_reverted.log) |
| Both files restored; targeted checks repeated | 19 PASS | [restored](rerun/logs/restored.log) |
| Source before/after | Identical | [before](rerun/logs/source_before.sha256), [after](rerun/logs/source_after.sha256), [status](rerun/logs/status.log) |

## Limits

Capability evidence only: one duel scenario, five-turn cap, three native games, and the games ended early by leader death (turn 2), so recruit/recall/advance coverage beyond the observed events is not demonstrated. `recall` and `advance` have zero events; they are reported as unobserved, not as covered. Two `moveto` and two `attack` events are ambiguous and are excluded from exact-match accuracy. `capture_sha256` is a hash of the capture sources, not a proof of semantic completeness. No corpus, BC gate, PPO batch, formal training or strength measurement was run; R9 and R10 remain unimplemented, and the R4 scenario-design and R5 qualified-rehearsal prerequisites are unchanged.
