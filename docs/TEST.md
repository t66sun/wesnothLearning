# Focused acceptance plan

> Language: English | [中文](TEST_zh.md)

Updated 2026-10-24. This user-requested replacement clears the former checklist and designs acceptance for the [refactor plan, chapter 10](architecture.md). **It authorizes no implementation, test execution, SSH, collection or training.** P1–P7 remain planned. New assertions described below are unwritten unless identified as existing evidence. N1 is implemented but unaccepted. No new runtime result is claimed.

For this planning request, planned cases are included explicitly. When an owning change is implemented, add its commit and real test entry point, retain its pending scope; after acceptance archive evidence and delete the item. Reopen only affected behavior.

## Boundaries and shared inputs

- Ubuntu accepts; Windows provides reference only. Work in an isolated directory/temporary run. Frozen inputs, manifests, evidence and installed models remain read-only.
- Activate only cases whose owner/dependency changed. Every changed behavior needs an assertion that fails when reverted. Missing fixtures/tests/runtime mean NOT RUN, never a skipped pass.
- Reuse accepted checks rather than duplicate them. No full faction/rules/worker/seed matrix, new corpus, long convergence run, tuning, or repeat of the accepted 100-position fit/eight-worker pressure test merely because code moved.
- D1/N1 block their optional delivery/native paths only. A small chain proves wiring, not quality, promotion, convergence or strength; production gates remain intact.

Prepare these once as separate derived fixtures with parent hashes, without editing historical evidence:

| Fixture | Smallest input | Shared by |
| --- | --- | --- |
| F1: synthetic sequences | Two admitted families with unequal windows; third excluded by byte budget; distinct game/side/format IDs; one teacher choice `-1` | C1–C5 |
| F2: recorded sequences | Existing teacher/on-policy data and matching behavior weights in `verification/model_strength_20261024_2120/`; short continuous slices per format with complete legal prefixes and 128 candidates | C1–C3/D1; full long 2v2 only for C3/C8 |
| F3: state/schedule | Two tiny complete checkpoints with different weights, optimizer/RNG/cursor; recorded collector/panel replies | C4–C7/C9 |
| F4: terminal | Existing lite early-terminal and budget-truncation counterexamples | C7/N1 |
| F5: deterministic combat | Tiny hand-calculated combat/status states; six public tactical positions; new-profile F3 state/schedule | R1–R3/C7; no new corpus, no old stochastic returns relabelled |

Default volume: seed 20261024; F1 learner windows of 17/41 targets, at most two epochs/four optimizer steps per comparison branch; compare the same logical batch at micro sizes 8/32. C3 may reuse further windows up to 256 requested targets to expose backfill. F2 parity uses at most eight supervised targets per format across two own turns, preserving full raw prefixes. All three formats share a tiny routing/parsing case; detailed fault injection uses team2v2. Add another seed/format only for an unresolved format-dependent failure. Proposed IDs below are specifications, not runnable test names.

R1–R3 are activated by P7 only. Unchanged C1–C9 reuse their evidence; refresh rule-dependent features/fixtures and the affected C1/C6/C7/C9 paths, not the entire suite. F2 old public contexts may be recomputed, but old transitions/teacher labels/log-probabilities/returns cannot become new-rule BC/PPO inputs. Keep old numerical extraction parity tied to its original rules.

## C1 — Public inputs, routing and recurrent memory

**Status/trigger:** existing semantics accepted; new composite assertion unwritten. Activate for changed learner, loader or adapter boundaries (P1/P2/P3/P6).

**Minimal Ubuntu procedure:** F1 plus short F2; interleave sides, cross own-turn boundary, eliminate a teammate, query/bootstrap between action and confirmation. Compare changed shared replay to independent reference before/after one parameter update.

**Pass:** poison hidden referee fields while holding legal public view fixed: features/predictions/teacher request remain equal. Diagnostic/terminal rows never enter policy inputs. Format/model routing survives elimination; game/side memories stay separate. Only confirmed committed action writes at the existing first-write point; query/bootstrap/no-op/duplicate confirmation cannot duplicate a write. Outputs **and gradients** match reference, with cache invalidation after weight changes. Choice `-1` stays history only; prefix/candidate order and indices survive loading.

**Blocker/evidence:** affected BC/PPO paths; public-field audit, input IDs and numeric deltas in `C1/`. Reuse unchanged [state/replay evidence](../verification/bc_rootcause_20261023_2318/REPORT.md).

## C2 — Learner extraction, BC objective and accuracy

**Status/trigger:** P1 parity harness unwritten; existing movement/small-fit results reusable. Mechanical extraction must preserve old sampling/stopping behavior.

**Minimal Ubuntu procedure:** identical tiny BC/PPO inputs, model/optimizer/RNG; one logical update through frozen old/new paths. BC includes unequal windows, short last micro-batch and move/attack/recruit. Independently calculate weighted loss and correct/total counts.

**Pass:** imports/return contract, losses, gradients, updated parameters/optimizer/RNG agree with baseline within predeclared numeric tolerance. Window-equal/within-window decision-equal weighting survives micro partition; preserve CE/auxiliary/value coefficients. Accuracy uses the same legal target/mask as loss and reports per-kind/per-format numerators/denominators, not averaged batch percentages. Training/validation families are disjoint; fewer than 32 validation targets for a required kind cannot pass its gate. C2 must preserve legacy PPO behavior; new traversal/KL expectations belong to C4/C5.

**Blocker/evidence:** P1 and affected BC gates; baseline identities, deltas/counts in `C2/`. Do not repeat long overfit/top-k/capacity experiments unless a remaining quality failure gives a concrete new hypothesis.

## C3 — BC filling and bounded decoding

**Status/trigger:** P2 unimplemented; budget/backfill assertions unwritten.

**Minimal Ubuntu procedure:** F1 requests more targets than initial allocation; backfill from already decoded families, keeping third outside compressed budget. Constrain retained bytes, available data and window count in separate small variants. Read the recorded long F2 2v2 once.

**Pass:** fill when admitted data permits without extra gz decode/admitting excluded family. Preserve engine/source quotas, family split and deterministic target IDs; extra windows do not inflate family count. Charge complete raw prefixes once, trim supervised targets only. Oversized first family cannot bypass limits. Independent row/byte/decode counts agree; underfill reports `gz_budget`, `retain_budget`, `insufficient_data` or `window_limit`. Invalid/missing index identity uses declared compatible raw reading or clearly fails, never serves another dataset.

**Blocker/evidence:** P2 readiness; counts/reasons and real-input peak RSS/PSS in `C3/`. The 96 MiB compressed/768 MiB estimated-retained budgets are separate from total RAM. Do not raise limits to pass.

## C4 — PPO coverage and saved-boundary recovery

**Status/trigger:** P3 unimplemented; epoch-plan/cursor assertions unwritten and required in the same change.

**Minimal Ubuntu procedure:** two epochs over unequal windows; compare uninterrupted execution with save/resume after one applied batch. Interrupt a second run inside a logical batch before stepping, using F3.

**Pass:** each eligible target occurs once per complete epoch without replacement; chronology holds, overlapping history does not duplicate targets. Persist rollout/model identity, epoch order and next unapplied batch. Resumed future IDs, RNG, optimizer and final weights match uninterrupted execution from the same committed boundary. Mid-batch stop discards gradients/restores pre-batch RNG including rehearsal draws; crash recovers only last atomic save. Recompute history under new weights. Reject mixed behavior/reward versions and invalid bootstrap; BC rehearsal is not on-policy exposure.

**Blocker/evidence:** P3/exact resume; ordered target IDs/state comparisons in `C4/`. New coverage/cursor assertions must fail on the old replacement sampler or omitted cursor.

## C5 — Logical-batch KL, exits and counters

**Status/trigger:** P4 unimplemented; aggregate/exit assertions unwritten, separate from P3.

**Minimal Ubuntu procedure:** fixed logical batch, micro sizes 8/32, one high-KL chunk whose isolated decision differs from weighted aggregate. Exercise completed/KL-stop/deadline exits with zero and one applied step.

**Pass:** independent window-equal mean of within-window decision means of `exp(logp-old_logp)-1-(logp-old_logp)` agrees with implementation. Weighted loss/KL/gradient and stop agree across partitions. Logical KL above .02 rejects before optimizer step and clears all batch gradients. Count committed decisions/version only after a step; distinguish inspected/unapplied work, unique IDs, effective passes, aggregate loss/KL/clip and pre/post policy identity on every exit. Zero-step means zero committed work. Exceptions remain failure. Clip .2, rewards and gates unchanged.

**Blocker/evidence:** P4; manual aggregates and before/after optimizer/parameter identities in `C5/`. Continued execution alone proves nothing about update correctness.

## C6 — Atomic checkpoints and explicit branching

**Status/trigger:** P5a planned; reuse hash checks, add operation/cursor assertions where absent.

**Minimal Ubuntu procedure:** F3 latest/champion; fail before atomic replacement; exercise latest resume, explicit fork from older state and legacy checkpoint without epoch plan. Corrupt identity fields individually in temporary copies.

**Pass:** interrupted save leaves previous complete checkpoint readable; never mix model/optimizer/RNG/cursor from different saves. Latest resume preserves clock/plan; explicit fork records parent hash/new plan/seed/optimizer choice without editing parent. Unsupported old mid-update resume is rejected or explicitly migrated at supported complete boundary. Wrong hash/schema/rules fail before update. Internal restore does not inherit SDK package-size limits, while SDK delivery retains its own gate.

**Blocker/evidence:** affected recovery operations; lineage, failed-write result and state identities in `C6/`. No replay of live incident needed.

## C7 — Stage chain, controller and terminal truth

**Status/trigger:** phase/controller checks accepted; new combined trace unwritten, activate after affected orchestration changes only.

**Minimal Ubuntu procedure:** F3 drives production orchestration: BC → two PPO updates → checkpoint/readback → pending-update resume → PPO completion → nomination/freeze → final entry. Tiny routing for three formats; faults only at changed boundaries: failed BC gate, v100 metric exception, optimizer/collector failure, pending method versus new phase. Reuse F4 and existing reward-window boundary assertions.

**Pass:** failed automatic BC gate blocks PPO; explicit force preserves `effective=false`/reason. Metric exception records missing evidence/freezes adaptive changes while real opening/gate checks continue. Real training error preserves pending/failed stage, exits unsuccessfully, consumes no final holdout. Resume finishes pending original method first. Controller advances every complete 12-block window after three exist, retains latest three/remainder; restore/duplicate evidence emits no duplicate reward event. Refresh need not change coefficients. True terminal versus truncation yields correct bootstrap/absorption; missing observations stay missing, referee events stay out of policy.

**Blocker/evidence:** changed stage path; event/order/counter/clock trace in `C7/`. Reuse [phase-chain](../verification/training_repair_20261023/REPORT.md) and [window](../verification/reward_window_fix_20261024_1607/REPORT.md) checks for unchanged owners. Later, only if separately authorized, one real lite Ubuntu chain per affected format: one BC update, two PPO updates, one save/resume and final entry, games capped at three turns and one complete evaluation rotation block per invoked panel. Enumerate actual game count from the production schedule before launch; do not repeat the chain to improve its scores. Initial version 99 may exercise v100 but does not mean 100 updates. Failed BC must use explicit recorded force if continuing; reduced validation/final panels stay inconclusive, never pass the 12/30-block gates.

## C8 — Storage memory and worker shutdown

**Status/trigger:** accepted repairs; activate only for changed storage/materialization/process/queue ownership. No default eight-worker rerun.

**Minimal Ubuntu procedure:** F2 long 2v2 once through changed storage/index/metrics, checking success/error cleanup. For lifecycle changes, reuse one actual lost-worker spawn probe with existing 45-second outer timeout confined to its own process group.

**Pass:** no full-trajectory object/JSON regrouping; preserve all decisions/prefixes/precision/labels and identical payload where serialization unchanged. Assert budgets/temporary cleanup, measure transient peak RSS/PSS. Worker loss raises original failure, terminates waiting trainers, leaves zero owned children; no hidden retry or signal to unrelated processes. Global worker cap/per-format isolation remain intact.

**Blocker/evidence:** changed collector/coordinator; payload/count/resource/child-exit records in `C8/`. Reuse [5.40 GiB recorded pressure](../verification/bc_memory_repair_20261024_1321/REPORT.md) and [pool failure](../verification/bc_pool_exit_20261024/REPORT.md) within stated limits. If memory ownership invalidates pressure evidence, predeclare one bounded workload/host reserve before running it, not a worker-count matrix or universal OOM-safety claim.

## C9 — Final selection and untouched holdout

**Status/trigger:** P5b planned; nomination assertions unwritten; reuse existing underfilled-promotion rejection.

**Minimal Ubuntu procedure:** recorded collector with champion, eligible latest off-cycle candidate and underfilled candidate. Let eligible candidate win, then remove a required block/exhaust nomination time. Restore checkpoint across repeated final entry.

**Pass:** match model/source/rule/schedule before reusing validation. Keep required 12 complete blocks; incomplete candidate cannot promote. Insufficient nomination time keeps declared champion/fallback with reason. Save completed validation bookkeeping before selected checkpoint. Freeze one selected hash before untouched 30-block holdout; holdout never chooses candidates or feeds training/reference. File/hash/`selected_kind` agree, including fallback. Resume cannot relabel pending as complete or duplicate completed evaluation. Reduced panel remains inconclusive.

**Blocker/evidence:** P5b/final selection; schedule, actual block counts, selection reason and freeze-before-holdout trace in `C9/`. One block never stands in for 12/30 real blocks.

## R1 — Deterministic per-strike damage and weakened statuses

**Status/trigger:** P7a unimplemented; new Rust table/status assertions unwritten. Blocks new deterministic-rule collection/training, not use of the frozen old engine.

**Minimal Ubuntu procedure:** one small table through the real resolver, plus three short status/order scripts. No game corpus or probabilistic confidence sampling. Use an independent integer formula oracle rather than invoking the production helper for the expected value.

| Input/sequence | Required result |
| --- | --- |
| Resolved damage 10, original hit chance 60% | Each eligible strike deals `ceil(10*.6*1.1)=7`; retain multiple strikes, no collapsed attack |
| Damage/chance boundaries | Zero base damage or 0% chance gives zero damage; 0% applies no hit effects; 10 at 100% gives 11; 1 at 1% gives 1, exposing upward-rounding bias |
| Slowed striker, damage 10, chance 60% | First `ceil(10*.75)=8`, then `ceil(8*.6*1.1)=6`; not old half damage, not single final rounding |
| Terrain/special/modifier cases | One resistance/time modifier and magical/marksman/chance-reducer representative each produce the hand-calculated `D,p`; apply chance/uplift once, for both attack and retaliation |
| Firststrike/death/drain | Preserve order/strike count; killed unit cannot retaliate; drain uses capped actual HP loss; newly applied slow changes subsequent retaliation |
| Poison 10 HP, no rest/healing | Own-turn ticks give 4 then 1 HP, no lethal poison; other sides' turns do not tick it; repeated poison does not stack |
| Status controls | Immunity/cure/suppression/rest precedence unchanged except poison 6; slow retains doubled terrain movement cost/lifetime without an additional half-budget penalty |

**Pass:** all exact integer/state assertions hold; inspect the new runtime to confirm old `Random`, combat/recruit RNG placeholders and hit injection have been removed/explicitly retired, not bypassed only in the test. Connected poison/slow apply without a second roll; retain eligibility of zero-damage on-hit weapons. One focused kill follow-up covers XP/plague/feeding wiring without a special-by-special matrix. Reverting new formula/slow/poison constants must fail the relevant assertions.

**Evidence:** `verification/acceptance_<date>/R1/`, oracle table, state traces, engine/profile/source IDs. Native stochastic outcome distributions are not the oracle for these intentional changes.

## R2 — Exact public forecast, identity isolation and stage chain

**Status/trigger:** P7a unimplemented; forecast/provenance assertions unwritten. Blocks new-profile training/export wiring.

**Minimal Ubuntu procedure:** reuse three R1 states (plain/slow/poison), forecast then execute in an all-visible controlled state, and one hidden-context counterexample. Hold initial state/action script fixed and vary only seed among 0/1/713; compare direct step with snapshot/restore/step. Compare legacy forecast requests `samples=1/128` if that argument is retained. Parameterize routing for three formats, then share C7's new-profile BC → two PPO updates → resume → final-entry trace; do not run a second separate chain.

**Pass assertions:**

- Forecast predicts exact HP/status/kill for matching public context; point-mass `hp_chance` sums to 1, effective samples=1, one resolver call per uncached forecast. Query does not advance state, change revision/memory or mutate any remaining noncombat RNG. Hypothetical attacker position affects relevant terrain/modifiers. Hidden-only changes cannot affect predictions/candidates/Astra; hidden combat factors may affect later execution, so equality is required only when public contexts are complete.
- Seeds/injected old hit lists cannot alter fixed-state combat. Old injection entry is absent or rejects explicitly. New snapshot round-trip preserves deterministic outcome; old stochastic snapshots fail identity checks, not silently discard RNG and resume.
- Candidate features, kill/status scores, Astra `simulate_combat` and actual resolver share the new profile; no second chance/1.10 multiplication or leftover eight-poison/half-slow assumptions. Any native consumer keeps native rules and declares that identity.
- New profile/hash, engine/snapshot identity and teacher hash propagate through jobs, manifest, data/index/cache, checkpoints, panels and export; a catalog hash/schema match alone cannot accept old dynamics. Negative temporary copies with old/missing/mixed profile fail before update. Old weights require explicit new-run initialization; old optimizer/rollout/clock cannot silently resume. Original records remain byte-identical.
- Shared C7 trace uses new-rule data/model/teacher identity through all three routes. Preserve quality/force provenance, bootstrap, controller, final selection and untouched holdout. A bounded trace remains inconclusive for strength. Record resolver-call counts and same-input forecast time, with no unmeasured speedup claim or repeat pressure matrix.

**Evidence:** `R2/` forecast/execution/public-input deltas, build/profile propagation, rejected-mismatch logs and link to the single C7 trace. If changed feature consumers affect D1, rerun its numeric slice only when implemented, not its unrelated transport matrix.

## R3 — Astra adaptation and separate strength evidence

**Status/trigger:** P7b unimplemented; six-position tactical fixture and matched comparison harness unwritten. Blocks adapted-teacher readiness; minimal pass does not prove preserved playing strength.

**Minimal Ubuntu procedure:** six public positions with independently specified admissible best actions/rankings: (1) deterministic lethal versus nonlethal, (2) firststrike/retaliation survival, (3) two weapons with different original hit chances, (4) slow value including movement restriction, (5) poison tick worth 6, (6) poison immunity/near cure making a normal attack preferable. Each has two meaningful alternatives, fixed budget and deterministic tie-break. Ensure the source-dependent heuristic change has at least one counterexample failing the old teacher. Reuse three-format route checks and C1 query/commit isolation.

**Pass:** teacher queries remain public/read-only/legal, no execution/RNG/memory leak. Predictions and ranking reflect the exact new damage/slow/poison contract; no automatic increase of teacher budget or unrelated recruitment/team-logic rewrite. Record teacher source/config/parent hash plus profile. Preserve the frozen original package; archive a new derived version. Report tactical assertions separately from strength.

**Strength, only with separate game authorization:** compare frozen unadapted versus adapted Astra under the **same new rules** and fixed paired initial maps/factions/roles, using one complete existing rotation block per format as a bounded smoke (predeclare actual games and turn cap). Reuse new-profile C7 games where roles/schedule match; truncated/underfilled results remain inconclusive. This detects obvious tactical/runtime deterioration, not statistical non-regression. Claiming maintained/improved strength requires the unchanged complete 12-block validation/champion contract on a frozen hold-out validation schedule; do not tune on that panel. If it is inconclusive or fails, retain that status and revise hypotheses rather than add seeds until a win. Formal final/native strength keeps its separate 30-block gate; deterministic-lite versus native or old-rule historical scores cannot establish parity.

**Evidence/blocker:** `R3/` six decisions/rankings, budgets, teacher/profile identities and separately labelled tactical/smoke/full-validation result. Minimal readiness can permit explicitly authorized new-rule training, but architecture must continue to mark teacher strength unverified until full matching evidence exists. No new collection starts from this written plan.

## D1 — Optional external inference

**Status/trigger:** P6 unimplemented; transport prototype/tests unwritten; blocks external delivery only.

**Minimal Ubuntu procedure:** prove one request/response/confirmed commit in ordinary stock Wesnoth 1.18.8 add-on first; assume neither LuaSocket nor judge RPC. Then F2, three formats/two own turns/128 candidates/interleaved sides/reset. Inject stale identity/index, duplicate commit, bootstrap with pending action and process exit. Separately authorized final runtime check executes one short native legal-action/clean-exit scenario.

**Pass:** logits/value within 1e-5 of reference; deterministic choice matches, near ties investigated. Check game/side/model/rule/feature/request/candidate identity and zero-to-one-based index conversion exactly once. No hidden wire fields. Commit once, bootstrap preserves pending action, reset isolates games. Failed/stale response cannot execute or silently substitute policy. One persistent process/model load per game closes cleanly. Save/reconnect reconstructs version-bound legal memory or is explicitly unsupported. Record package size and cold/warm/round-trip times; no invented speed or SDK claim.

**Evidence:** `D1/` protocol/numeric/runtime artifacts. Windows packaging/strength remain separate.

## N1 — Optional native terminal capture (former T6)

**Status/trigger:** implemented, unaccepted; fixed scenario helper unwritten. Blocks new native terminal path only, not lite.

**Minimal Ubuntu procedure/pass:** one fixed native 1.18.8 early-elimination/endgame scenario capped at five turns plus existing truncation counterexample. Actual initial/eliminated/terminal events preserve surviving side/real own HP; T5/T10 absorption only for real terminal. Failure/truncation cannot invent terminal. Missing events mean missing evidence, not zero-valued success. Diagnostic rows enter neither actor/BC/PPO shards nor memory writes. Save raw events/command/identities in `N1/`; no native rules/performance matrix.

## Execution order and report

1. Identify changed owners, activated cases, reused evidence and missing fixtures. Predeclare maximum rows/windows/steps/games and numeric tolerances. Implement only needed assertions/helpers; record real test commands before running.
   For P7, run R1 → R2 → R3 tactical checks, sharing C7; authorize any real-game smoke/strength panel separately. Archive new rules' evidence separately from old stochastic acceptance.
2. Affected local deterministic checks, then relevant Ubuntu checks. C4/C5/C6 share a recovery trace; C7/C9 share recorded orchestration. Actual processes/games run only when activated and authorized. Use short slices rather than full records unless C3/C8 needs them.
3. Stop once affected checks pass. After a fix rerun failed cases/changed dependencies only. No new collection/formal training without instruction.

One dated `verification/acceptance_<date>/REPORT.md`, with artifact subdirectories only when used:

```text
Scope: behavior/commit; activated C*/R*/D*/N*; exclusions and reasons
Identity: source/extension build, Ubuntu/Python/torch, catalog/combat-profile/teacher/schema,
          input/model/optimizer hashes, seed/plan/cursor when relevant
Commands: executable, cwd, arguments, exit code, duration
Results: case | PASS / FAIL / NOT RUN / REUSED | assertion/counts | artifact
Reuse: original report + relevant identity match; reuse is not a new run
Failure: first differing input/step, expected/actual, reproduction
Resources: rows/windows/families/decodes/steps/children; peak RSS/PSS if relevant
Gate: ready for named next phase / blocked; reduced panels inconclusive
Limits: unwritten tests, missing inputs/runtime, unproved quality/strength
```

No credentials in evidence. Failure, missing required observation, silent skip or identity mismatch blocks affected acceptance. Documentation-only changes run document/link/diff checks only. This plan has no runtime result.
