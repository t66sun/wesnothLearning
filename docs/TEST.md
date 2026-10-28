# Focused acceptance plan

> Language: English | [中文](TEST_zh.md)

Updated 2026-10-25. The six reproduced V1–V6 defects are repaired and their 12 focused Ubuntu checks passed; commands, identities, failures and limits are in the [repair acceptance report](../verification/refactor_repairs_20261025/REPORT.md). Completed repair items and C9 are archived there and removed below. Remaining cases retain their narrower unaccepted or unwritten scope; bounded results do not establish full acceptance or strength. P6 remains unimplemented and N1 unaccepted.

Keep only remaining acceptance work and explicitly requested prospective cases here. Reuse existing valid evidence; no full-suite rerun, new games or formal training is authorized by this plan. The SDK package-size attempt remains failed in the report; its unchanged gate is outside these six repairs.

Final budget reserve B1 is accepted by six Ubuntu checks and archived in the [startup report](../verification/final_review_lite30h_20261025/REPORT.md); the completed item is removed.

PPO rebuild R1 is accepted by 27 focused Ubuntu checks, with revert/restore evidence in the [R1 report](../verification/ppo_refactor_r1_20261027/REPORT.md). R2 is accepted by 20 focused checks plus one FFA4/2v2 update check, with revert/restore evidence in the [R2 report](../verification/ppo_refactor_r2_20261027/REPORT.md). No R1/R2 acceptance item remains. R3 is accepted by 14 focused Ubuntu checks ([report](../verification/ppo_refactor_r3_20261027/REPORT.md)); no R3 acceptance item remains. R4 is accepted by 30 focused Ubuntu checks ([report](../verification/ppo_refactor_r4_20261027/REPORT.md)); the design limit it recorded was then closed on 2026-10-28, when the roster was accepted by 37 focused checks plus a planned-floor probe over final, promotion and collection panels ([report](../verification/ppo_refactor_r4_20261029/REPORT.md)); no R4 acceptance item remains. R5 is accepted by 23 focused Ubuntu checks ([report](../verification/ppo_refactor_r5_20261027/REPORT.md)); no R5 acceptance item remains, and its prerequisite is audited: the curated corpus holds no 1.18.8 era_default standard-multiplayer replay, replays recorded under other versions are refused (`other_version`), and the five focused checks pass on Ubuntu ([audit](../verification/ppo_refactor_r5_20261029/REPORT.md)). Supplying replays or authorizing a policy opt-in is a data decision. R6 passed 37 Ubuntu contract checks and 421-row bitwise arithmetic parity; unresolved local fixture/extension checks are listed in the [R6 report](../verification/ppo_refactor_r6_20261027/REPORT.md). R7 passed 39 Ubuntu identity/wiring checks and Lua syntax ([report](../verification/ppo_refactor_r7_20261027/REPORT.md)); this does not prove stock capture capability. R8 is accepted as capability evidence by 19 focused Ubuntu checks and a controlled three-game native fixture ([rerun report](../verification/ppo_refactor_r8_20261028/RERUN.md)); R9 is accepted as capability evidence by 23 focused Ubuntu checks and one real stock teacher game ([report](../verification/ppo_refactor_r9_20261029/REPORT.md)). R10 is accepted as capability evidence by 33 focused Ubuntu checks plus a reproducible repository bundle ([report](../verification/ppo_refactor_r10_20261029/REPORT.md)), so no R10 acceptance item remains. R8b then closes R8's label limit: 33 focused Ubuntu checks and two real stock games clear the BC coverage gate with zero ambiguous events, and the intent, weapon and denominator reverts fail as expected ([report](../verification/ppo_refactor_r8b_20261030/REPORT.md)); recall, advance and the candidate budget stay open. N1 and existing numerical/package failures retain their scope and gates.

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

**Status/trigger:** P1 implemented; four scalar/import checks are reported. Full gradient/optimizer/RNG equivalence is not inferred from scalar loss alone; reuse existing small-fit evidence.

**Minimal Ubuntu procedure:** identical tiny BC/PPO inputs, model/optimizer/RNG; one logical update through frozen old/new paths. BC includes unequal windows, short last micro-batch and move/attack/recruit. Independently calculate weighted loss and correct/total counts.

**Pass:** imports/return contract, losses, gradients, updated parameters/optimizer/RNG agree with baseline within predeclared numeric tolerance. Window-equal/within-window decision-equal weighting survives micro partition; preserve CE/auxiliary/value coefficients. Accuracy uses the same legal target/mask as loss and reports per-kind/per-format numerators/denominators, not averaged batch percentages. Training/validation families are disjoint; fewer than 32 validation targets for a required kind cannot pass its gate. C2 must preserve legacy PPO behavior; new traversal/KL expectations belong to C4/C5.

**Blocker/evidence:** P1 and affected BC gates; baseline identities, deltas/counts in `C2/`. Do not repeat long overfit/top-k/capacity experiments unless a remaining quality failure gives a concrete new hypothesis.

## C3 — BC filling and bounded decoding

**Status/trigger:** P2 implemented; nine loader checks reported after the empty-read repair. Real recorded-input peak-memory/full-prefix coverage beyond those assertions is not claimed.

**Minimal Ubuntu procedure:** F1 requests more targets than initial allocation; backfill from already decoded families, keeping third outside compressed budget. Constrain retained bytes, available data and window count in separate small variants. Read the recorded long F2 2v2 once.

**Pass:** fill when admitted data permits without extra gz decode/admitting excluded family. Preserve engine/source quotas, family split and deterministic target IDs; extra windows do not inflate family count. Charge complete raw prefixes once, trim supervised targets only. Oversized first family cannot bypass limits. Independent row/byte/decode counts agree; underfill reports `gz_budget`, `retain_budget`, `insufficient_data` or `window_limit`. Invalid/missing index identity uses declared compatible raw reading or clearly fails, never serves another dataset.

**Blocker/evidence:** P2 readiness; counts/reasons and real-input peak RSS/PSS in `C3/`. The 96 MiB compressed/768 MiB estimated-retained budgets are separate from total RAM. Do not raise limits to pass.

## C4 — PPO coverage and saved-boundary recovery

**Status/trigger:** P3 implemented. V3/V5 targeted Ubuntu recovery/count/content assertions passed and are archived in the repair report. Remaining acceptance below concerns the broader replay/gradient contract beyond these tiny fixtures.

**Minimal Ubuntu procedure:** two epochs over unequal windows; compare uninterrupted execution with save/resume after one applied batch. Interrupt a second run inside a logical batch before stepping, using F3.

**Pass:** each eligible target occurs once per complete epoch without replacement; chronology holds, overlapping history does not duplicate targets. Persist rollout/model identity, epoch order and next unapplied batch. Resumed future IDs, RNG, optimizer and final weights match uninterrupted execution from the same committed boundary. Mid-batch stop discards gradients/restores pre-batch RNG including rehearsal draws; crash recovers only last atomic save. Recompute history under new weights. Reject mixed behavior/reward versions and invalid bootstrap; BC rehearsal is not on-policy exposure.

**Blocker/evidence:** P3/exact resume; ordered target IDs/state comparisons in `C4/`. New coverage/cursor assertions must fail on the old replacement sampler or omitted cursor.

## C5 — Logical-batch KL, exits and counters

**Status/trigger:** P4 implemented; logical-KL/exit evidence is reused and V3 cumulative resume counters passed targeted Ubuntu acceptance. Retain only broader numeric/gradient assertions not established by those fixtures.

**Minimal Ubuntu procedure:** fixed logical batch, micro sizes 8/32, one high-KL chunk whose isolated decision differs from weighted aggregate. Exercise completed/KL-stop/deadline exits with zero and one applied step.

**Pass:** independent window-equal mean of within-window decision means of `exp(logp-old_logp)-1-(logp-old_logp)` agrees with implementation. Weighted loss/KL/gradient and stop agree across partitions. Logical KL above .02 rejects before optimizer step and clears all batch gradients. Count committed decisions/version only after a step; distinguish inspected/unapplied work, unique IDs, effective passes, aggregate loss/KL/clip and pre/post policy identity on every exit. Zero-step means zero committed work. Exceptions remain failure. Clip .2, rewards and gates unchanged.

**Blocker/evidence:** P4; manual aggregates and before/after optimizer/parameter identities in `C5/`. Continued execution alone proves nothing about update correctness.

## C6 — Atomic checkpoints and explicit branching

**Status/trigger:** P5a implemented. V2/V4/V5 identity, BC cancellation RNG and changed-input rejection passed focused Ubuntu checks. Reuse serialization/branch evidence; the wider legacy/fork contract below is not newly claimed complete.

**Minimal Ubuntu procedure:** F3 latest/champion; fail before atomic replacement; exercise latest resume, explicit fork from older state and legacy checkpoint without epoch plan. Corrupt identity fields individually in temporary copies.

**Pass:** interrupted save leaves previous complete checkpoint readable; never mix model/optimizer/RNG/cursor from different saves. Latest resume preserves clock/plan; explicit fork records parent hash/new plan/seed/optimizer choice without editing parent. Unsupported old mid-update resume is rejected or explicitly migrated at supported complete boundary. Wrong hash/schema/rules fail before update. Internal restore does not inherit SDK package-size limits, while SDK delivery retains its own gate.

**Blocker/evidence:** affected recovery operations; lineage, failed-write result and state identities in `C6/`. No replay of live incident needed.

## C7 — Stage chain, controller and terminal truth

**Status/trigger:** Reuse the 17 Ubuntu phase checks and recorded duel reduced chain. V1 now has three-format recorded-schedule nomination and repeated-final-entry evidence; a new real three-format phase chain remains unrun and is not authorized here.

**Minimal Ubuntu procedure:** F3 drives production orchestration: BC → two PPO updates → checkpoint/readback → pending-update resume → PPO completion → nomination/freeze → final entry. Tiny routing for three formats; faults only at changed boundaries: failed BC gate, v100 metric exception, optimizer/collector failure, pending method versus new phase. Reuse F4 and existing reward-window boundary assertions.

**Pass:** failed automatic BC gate blocks PPO; explicit force preserves `effective=false`/reason. Metric exception records missing evidence/freezes adaptive changes while real opening/gate checks continue. Real training error preserves pending/failed stage, exits unsuccessfully, consumes no final holdout. Resume finishes pending original method first. Controller advances every complete 12-block window after three exist, retains latest three/remainder; restore/duplicate evidence emits no duplicate reward event. Refresh need not change coefficients. True terminal versus truncation yields correct bootstrap/absorption; missing observations stay missing, referee events stay out of policy.

**Blocker/evidence:** changed stage path; event/order/counter/clock trace in `C7/`. Reuse [phase-chain](../verification/training_repair_20261023/REPORT.md) and [window](../verification/reward_window_fix_20261024_1607/REPORT.md) checks for unchanged owners. Later, only if separately authorized, one real lite Ubuntu chain per affected format: one BC update, two PPO updates, one save/resume and final entry, games capped at three turns and one complete evaluation rotation block per invoked panel. Enumerate actual game count from the production schedule before launch; do not repeat the chain to improve its scores. Initial version 99 may exercise v100 but does not mean 100 updates. Failed BC must use explicit recorded force if continuing; reduced validation/final panels stay inconclusive, never pass the 12/30-block gates.

## C8 — Storage memory and worker shutdown

**Status/trigger:** accepted repairs; activate only for changed storage/materialization/process/queue ownership. No default eight-worker rerun.

**Minimal Ubuntu procedure:** F2 long 2v2 once through changed storage/index/metrics, checking success/error cleanup. For lifecycle changes, reuse one actual lost-worker spawn probe with existing 45-second outer timeout confined to its own process group.

**Pass:** no full-trajectory object/JSON regrouping; preserve all decisions/prefixes/precision/labels and identical payload where serialization unchanged. Assert budgets/temporary cleanup, measure transient peak RSS/PSS. Worker loss raises original failure, terminates waiting trainers, leaves zero owned children; no hidden retry or signal to unrelated processes. Global worker cap/per-format isolation remain intact.

**Blocker/evidence:** changed collector/coordinator; payload/count/resource/child-exit records in `C8/`. Reuse [5.40 GiB recorded pressure](../verification/bc_memory_repair_20261024_1321/REPORT.md) and [pool failure](../verification/bc_pool_exit_20261024/REPORT.md) within stated limits. If memory ownership invalidates pressure evidence, predeclare one bounded workload/host reserve before running it, not a worker-count matrix or universal OOM-safety claim.

## R1 — Deterministic per-strike damage and weakened statuses

**Status/trigger:** P7a implemented; 13 Rust tests and relevant interface checks passed in the recorded Ubuntu panel. Reuse bounded evidence; full new-profile readiness also requires R2/R3.

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

**Status/trigger:** Reuse unchanged P7a forecast/engine/teacher evidence. V2/V5/V6 targeted identity, export wiring and native/lite record compatibility passed Ubuntu acceptance; this does not establish the full real-game stage/forecast contract below.

**Minimal Ubuntu procedure:** reuse three R1 states (plain/slow/poison), forecast then execute in an all-visible controlled state, and one hidden-context counterexample. Hold initial state/action script fixed and vary only seed among 0/1/713; compare direct step with snapshot/restore/step. Compare legacy forecast requests `samples=1/128` if that argument is retained. Parameterize routing for three formats, then share C7's new-profile BC → two PPO updates → resume → final-entry trace; do not run a second separate chain.

**Pass assertions:**

- Forecast predicts exact HP/status/kill for matching public context; point-mass `hp_chance` sums to 1, effective samples=1, one resolver call per uncached forecast. Query does not advance state, change revision/memory or mutate any remaining noncombat RNG. Hypothetical attacker position affects relevant terrain/modifiers. Hidden-only changes cannot affect predictions/candidates/Astra; hidden combat factors may affect later execution, so equality is required only when public contexts are complete.
- Seeds/injected old hit lists cannot alter fixed-state combat. Old injection entry is absent or rejects explicitly. New snapshot round-trip preserves deterministic outcome; old stochastic snapshots fail identity checks, not silently discard RNG and resume.
- Candidate features, kill/status scores, Astra `simulate_combat` and actual resolver share the new profile; no second chance/1.10 multiplication or leftover eight-poison/half-slow assumptions. Any native consumer keeps native rules and declares that identity.
- New profile/hash, engine/snapshot identity and teacher hash propagate through jobs, manifest, data/index/cache, checkpoints, panels and export; a catalog hash/schema match alone cannot accept old dynamics. Negative temporary copies with old/missing/mixed profile fail before update. Old weights require explicit new-run initialization; old optimizer/rollout/clock cannot silently resume. Original records remain byte-identical.
- Shared C7 trace uses new-rule data/model/teacher identity through all three routes. Preserve quality/force provenance, bootstrap, controller, final selection and untouched holdout. A bounded trace remains inconclusive for strength. Record resolver-call counts and same-input forecast time, with no unmeasured speedup claim or repeat pressure matrix.

**Evidence:** `R2/` forecast/execution/public-input deltas, build/profile propagation, rejected-mismatch logs and link to the single C7 trace. If changed feature consumers affect D1, rerun its numeric slice only when implemented, not its unrelated transport matrix.

## R3 — Astra adaptation and separate strength evidence

**Status/trigger:** P7b implemented; six value-level positions checked. Full legal-board teacher query/ranking and matched strength comparison remain unrun.

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

## L1 — Post-refactor reduced full-loop run

**Status/trigger:** Original report records duel BC→PPO→resume→final fallback. No uninterrupted same-future comparison or scheduled mid-run tick; no champion-present/all-format coverage or full acceptance claim.

**Minimal Ubuntu procedure:** on the isolated source tree, freeze one lite config with the smallest format/game panel that reaches BC, at least two applied PPO updates, one stop/resume from a committed-batch checkpoint, and the final-evaluation entry. Record the exact counts, seed, manifest and checkpoint identities before launch. Poll the run status/log every 30 minutes and retain anomalies; do not raise game counts, lower gates or edit frozen evidence during the run.

**Pass:** the run reaches final evaluation; both PPO updates commit; resuming from the saved boundary reproduces the uninterrupted future exactly where identity matches; the selected checkpoint and export are recorded; every stop reason is reported rather than hidden. Any reduced-panel limitation is labelled inconclusive for strength, and a failure remains a failure.

**Evidence/blocker:** new dated `verification/<run>_<date>/REPORT.md` with commands, counts, identities, checkpoint/resume trace, final-evaluation entry and resource readings. No new collection/formal training from this item alone.

## PKG1 — Ubuntu 24.04 training bundle

**Status/trigger:** builder and static verifier implemented and locally tested on 2026-10-25: `python -m learning bundle --help` and `python -m learning verify-bundle --help` exit 0, and 16 builder/verifier plus 11 setup/train script checks pass. No archive has been built and no clean Ubuntu 24.04 machine has extracted, installed or started one; those steps are NOT RUN. Activate before the archive is handed to a machine without this checkout, and after any change to the payload list, exclusion rules, manifest, `SHA256SUMS`, `setup.sh` or `train.sh`.

**Minimal Ubuntu procedure:** on this checkout build one archive with `python -m learning bundle --output tmp/bundle_<date>/WesnothLearning-training.tar.gz --created-at <fixed ISO8601>` and record its sha256; pass `--wheel dist/<manylinux x86_64>.whl` only when a bundled Linux wheel is intended, and add `--require-wheel` to `verify-bundle` in that case. Verify with `python -m learning verify-bundle <archive>` and confirm the member list, modes and exclusions against [bundle.md](bundle.md). Copy the archive to a clean Ubuntu 24.04 x86_64 machine, extract, and run `./setup.sh --preflight` (exit 0, no writes). Flip one payload byte in a copy and confirm preflight exits non-zero. Then `./setup.sh --device cpu`, which must exit 0 and print the rules/engine identity checks; run `./train.sh --help` with the tree compared before and after; and run `./train.sh` in a copy without `.runtime/environment.sh`, which must refuse. Confirm no `runs/` directory or run log exists afterwards.

**Pass:** the recorded archive sha256 matches what verification reads, preflight accepts the intact copy and rejects the tampered one, and the archive contains no `.git`, venv, run state, validation evidence, delivery output, historical `1.18.8` package or raw replay dump. Setup exits 0 on the clean machine, writes `.runtime/environment.sh` and `.cache/setup.log`, and its identity checks agree with `rules.json`, `catalog-summary.json` and `_engine_lite`. `--help` creates nothing, and `train.sh` refuses without setup instead of starting work. Any observed failure is reported as a failure, never converted into a narrower pass.

**Evidence:** `verification/training_bundle_ubuntu24_<date>/REPORT.md` with the archive path/sha256/manifest identity, every command and exit code, the intact and tampered preflight results, identity-check output, the tree diff around `--help`, the refusal output and the setup log. Absent that report the item is NOT RUN.

**Training blocker:** this item proves installation only. It authorizes no collection, training start, convergence claim or strength claim; starting a run still requires explicit user instruction, and neither setup nor an extracted archive is that instruction.

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
