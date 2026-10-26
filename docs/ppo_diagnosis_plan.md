# PPO diagnosis and stock AI replacement plan

> Language: English | [中文](ppo_diagnosis_plan_zh.md)

2026-10-26. **Initial static review complete; the investigations, implementation and acceptance below are NOT RUN.** This review reads current source, downloaded manifests/summaries and existing evidence only. No SSH, model inference, optimizer execution, collection or training. Reproducible observations are in the [static report](../verification/ppo_static_review_20261026/REPORT.md).

The user has decided to replace every active Astra role with Wesnoth **1.18.8 stock default RCA AI** in future work. This supersedes the previous Astra-only teacher decision for future runs; the implementation still uses Astra. Preserve causal separation between diagnosing the old PPO run and replacing its teacher. Changing teacher, engine and randomness together cannot establish which change improved PPO. Request/decision tracking: [#48](https://github.com/t66sun/wesnothLearning/issues/48).

## 1. Define the observed problem

The completed `v5_lite30h_20261025` run froze source `822082d654cd19a6474aa36f837137c1ec7cb83c`, CPU, eight shared workers and deterministic lite. All complete BC gates passed without forced PPO. These final differences are format scores, **not accuracy or win rate**.

| Format | Latest / selected version | Final difference | Original result | Overall / recruit accuracy recorded at BC gate |
| --- | --- | ---: | --- | --- |
| Duel | 470 / 400 | -1.75 | not_passed | 99.19% / 240 of 248 = 96.77% |
| FFA4 | 213 / 100 | +0.01389 | inconclusive | 91.27% / 90 of 119 = 75.63% |
| 2v2 | 136 / 100 | -1.625 | not_passed | 86.63% / 40 of 43 = 93.02% |

BC accuracy measures imitation on a bounded teacher validation sample. It is neither final post-PPO accuracy nor evidence of good teacher strategy or winning play. Final evaluation uses selected: latest Duel/2v2 failed Astra nomination; latest FFA4 nomination was incomplete. This table alone establishes neither continuous PPO regression, the method of every v100 checkpoint, nor native strength.

## 2. Five prioritized leads

### H1: Few distinct scenarios, possible split leakage and dependent evaluation blocks

**Observed:** `schedule.factions` cycles six factions by `block * players`; evaluation maps also cycle. Lite starts with fixed leaders, positions and attributes, and deterministic expected-damage combat. Its Rust core consumes no random stream from seed. Nevertheless, `game_family` hashes seed and its hash modulo five assigns train/validation. Final block scores repeat exactly every six blocks in Duel and every three in FFA4/2v2, across all 30 blocks.

**Hypothesis:** physically identical scenarios or teacher trajectories may receive different family/split identities through seed alone, inflating BC validation. Repeated evaluation trajectories may also be bootstrapped as independent blocks. Training could memorize a small map/faction/seat set.

**Limit:** equal scores do not prove equal trajectories. Student sampling, opponent weights, budgets and execution order may differ. Prove equivalence before changing grouping or statistics.

**Discriminator:** cross-split matches of normalized legal input and teacher action sequences, or final blocks matching in initial scenario and stepwise trajectory. Different trajectories with equal scores refute the duplicate-trajectory claim, while limited scenario coverage can remain.

### H2: Little committed learning per rollout, or excessive policy movement in one update

**Observed:** earlier progress observations include KL stops after few optimizer steps; the full current run's PPO distribution has not been recomputed in this review. `ppo.update` checks KL before each logical optimizer batch with limit 0.02, on that batch rather than maximum drift over the rollout. Clipped policy loss, 0.5 value MSE, entropy and BC rehearsal all affect shared parameters. BC→PPO retains Adam state and changes learning rate to 1e-4.

**Hypotheses:** behavior probabilities may already disagree with zero-update replay; alternatively one committed update, including value/BC gradients or inherited Adam state, may cause large drift noticed on the next batch. Policy clipping does not constrain all other loss components.

**Discriminator:** zero-step mismatch means fixing the input/memory/probability contract first. Zero-step agreement followed by large drift on a fixed probe after one step directs attention to gradients/updates. Normal coverage and controlled KL weaken this lead. A protective KL stop is not itself a defect; do not raise the limit to conceal it.

### H3: Reward, value and temporal credit may provide weak or incorrect signals

**Observed:** gamma=1, GAE lambda=0.95, no repeated discount within one own turn. Economy/control use potential differences, true terminal states zero next potentials, and turn-limit truncation retains legal bootstrap. Advantages are decision-normalized; optimization weights eight-own-turn windows equally and decisions equally within each window.

**Hypotheses:** truncation, long trajectories, value error or sparse terminal rewards destabilize advantages; action chains and window weighting may dilute important recruit/attack choices. Differing normalization/optimization units are a choice to measure, not a proven bug.

**Discriminator:** failed hand oracle, missing trajectory tails, incorrect terminal/truncation, systematic critic error or advantage/weight concentration on irrelevant actions. With gamma=1, potential terms telescope on true terminal trajectories; small local shaping values alone do not make them useless. GAE, critic learning and truncation require separate examination.

### H4: Teacher defects, BC generalization and candidate restrictions may compound

**Observed:** four-player Astra recruits with fixed type weights, own-count penalties and a few visible resistance heuristics. BC rehearsal continues its labels during PPO; the same teacher is fixed opponent, 2v2 partner and adaptive-reward reference. Candidate generation is independent of teacher answers but limited to 20,000 work, 128 actions and up to eight recruit locations per type. The 2v2 BC recruit gate's 93.02% uses only 43 validation decisions.

**Hypotheses:** high imitation reproduces poor recruiting; student-state mistakes persist while rehearsal restrains departure; or a useful legal action is pruned. The user's observation supports replacing the teacher but does not establish it as the only PPO cause.

**Discriminator:** separate absent good candidates, wrong choices among present candidates and poor teacher choices. Split unit type versus location, faction/map/seat/phase/partner context. Do not label deterministic-lite tactics using unexamined stochastic-native assumptions.

### H5: Selection and evaluation domains can obscure the actual learning trend

**Observed:** selected differs from latest; latest FFA4 has incomplete nomination. Full promotion runs every 100 versions, while smaller trend panels rotate layouts. `selection_key` can retain a negative-scoring champion: best among considered candidates does not mean beating the fixed opponent. Final evaluation here is lite Astra; native deployment has different combat semantics.

**Hypotheses:** some perceived stagnation compares different checkpoints/layouts/engines; genuine regression on matched panels is also possible.

**Discriminator:** align checkpoint method/version, control and complete layout before judging trend. Distinguish actual matched-panel regression from a retained earlier selected model. Keep final holdout read-only and outside tuning or reselection.

## 3. Investigation sequence and stopping rules

All proposed tools/assertions/dynamic work below are **unwritten or NOT RUN**, never passing tests. Work locally first, then authorized minimal Ubuntu checks in a new isolated directory when needed. Do not overwrite old runs, rules, manifests, reports or checkpoints. Freeze identities, resource caps and expectations before executing each step.

### S0: Trace diagnosis inputs through committed learning to final selection

1. Record source/extension/catalog/feature/candidate/teacher/combat/RNG/reward identities and model/optimizer hashes. Reuse local manifest/summary/selection first. Request a separate bounded server read only for necessary missing originals.
2. Per format/method/version, inventory collected, eligible/faulted/truncated games, teacher/DAgger/human sources, split/family counts, planned/inspected/committed targets/windows, optimizer steps, KL/deadline exits and elapsed phases.
3. Separate settled history from cumulative `pending_train.cursor`; do not sum successive saves of the same cursor. Reconcile actual optimizer updates and counters, rather than versions or wall time. PPO also filters validation families: count actual exclusions, not an assumed exact 20% per batch.
4. Identify last complete BC, first PPO, promotions, last/best/selected and their methods. Reuse existing comparable validation/champion panels; do not supplement holdout.
5. Produce `inventory.json`, `exposure.csv`, `checkpoint_lineage.csv` and a missing-originals list. Missing evidence stays unknown.

**Exit:** each collection can be traced to committed learning and selection. Identity/counter gaps block numerical attribution for that format. Start with Duel's clear negative result and smaller trajectories; use 2v2 for team/recruit-specific confirmation, FFA4 only when a four-player distinction matters.

### S1: Measure real diversity and split overlap — H1

1. Inspect all existing schedule/index metadata for map, factions, seats/teams, partner/opponent weight identities, max turns, fog/sharing and map hashes; count combinations and repeats.
2. Define two diagnostic fingerprints without editing original family IDs: initial scenario/rules/controllers, and legal observation→ordered candidates→teacher intent/actual execution→memory writes. Exclude only identity-only fields. Preserve consequential sampling/AI state, unit correspondences and work/time budgets. Document any consistent actor/target ID renaming.
3. Initially decode at most six suspicious teacher-family pairs per format, prioritizing cross-split same-map/faction/role pairs; retain complete prefixes and report the first difference. Check whether seed alone changes split for equivalent scenarios. No collision in a small sample does not prove corpus independence; after one confirmed collision, extend only the affected cluster's index audit.
4. Compare one existing final block pair per format at offsets 6/3/3, including all seat rotations/team contexts, with no new games. Missing local trajectories are pending evidence, not equality inferred from scores.
5. If confirmed, report effective scenario clusters and separate cluster-aware diagnostic statistics. With very few clusters report descriptive fixed-scenario results and insufficient intervals. Preserve original 30-block results, minimum-block gates and historical labels.
6. Only after a collision, design a new corpus/schema split grouping physically equivalent scenarios/trajectories without train/validation/holdout overlap; retain old data. Add a same-scenario/different-seed counterexample assertion. Expanding maps/games requires its own frozen proposal.

**Output/stop:** `scenario_coverage.csv`, `duplicate_pairs.json`, normalization/first differences. Do not implement dedup from equal scores alone. Confirmed leakage limits the old BC accuracy claim; the original gates must be passed again on new data before new eligibility is claimed.

### S2: Zero-update behavior replay before optimizer diagnosis — H2 prerequisite

1. Select one frozen PPO batch with its actual behavior weights, complete legal prefixes, ordered candidates, choices and old log probabilities/values. Selected weights cannot substitute for behavior weights. If originals are absent choose another complete batch; otherwise report blocked evidence.
2. Initially use one Duel batch and at most 48 early/middle/late targets covering recruit/move/attack/end-turn, turn boundaries and history beyond eight turns. Keep full raw prefixes.
3. Compare actual `FrozenPolicies.choose` single-row/cached inference with training `model.batch`: weight hash, candidate masks/index, float32 tensors, executed intent, exactly-once memory commit, resets and sampling/greedy mode.
4. Without parameter updates, record chosen logp/value deltas, ratios, distribution KL only if full old distributions exist, actual sampled approximate KL, tensor differences and first divergence. Do not invent exact KL from a chosen-action probability. Begin with the existing 1e-5 output-difference gate and ratios near one; record rare-probability sensitivity separately. Tolerance changes need justification rather than fitting failure.
5. Bisect raw row→prefix→batch→context→logits→probability on mismatch. Stop optimizer attribution until zero-step replay agrees.

**Output:** `replay_parity.json` and a minimal complete-prefix counterexample. Any fix needs a revert-failing assertion; existing replay tests retain their original scope and cannot substitute for this real batch check.

### S3: Two-step offline update diagnosis — H2

1. Copy S2 model/Adam/RNG/data/window order and BC sample plan to disposable diagnostic state. Never write back. On a fixed probe, measure zero/pre/post-step and next-batch KL, ratio quantiles, clip fraction, entropy, choice changes and value explained variance.
2. Measure PG/value/BC/entropy gradient norms and pairwise cosines by shared encoder/GRU/actor/value head, total preclip norm, clip factor and actual parameter movement. Record advantage/return distributions and component losses; loss magnitude is not gradient influence.
3. First allow at most **two committed steps** of the complete objective. If drift reproduces, choose at most two single-factor controls based on gradients: e.g. remove value gradients, remove BC gradients, or compare inherited/fresh Adam specifically at BC→PPO entry. Each arm has at most two steps and identical probes/windows/RNG. No full factorial grid, production changes or reused diagnostic models for training.
4. Distinguish post-step whole-probe drift, a harder next batch and rare-action estimate sensitivity. Keep the KL gate; rejected steps remain rejected. Record planned versus committed counts.
5. Propose a minimal intervention only after identifying the cause: contract fix first; gradient/Adam behavior in its own PR; a tuning hypothesis gets one variable after diagnosis. Do not simultaneously change LR, reward, network and sampling scale.

**Exit:** first divergent step and dominant factor, or an explicit failure to reproduce on that frozen batch. Two steps prove only local mechanics. Cross-check one existing 2v2 batch only if needed; do not automatically run a three-format matrix.

### S4: Reward/bootstrap/GAE/window-weight audit — H3

1. Reuse existing reward/GAE assertions and fill actual gaps. Hand-compute two tiny sequences: multiple same-turn decisions→next own turn→true win/loss; and turn-limit truncation with explicit bootstrap value/potential. Include necessary draw, centered FFA rank and own-leader-eliminated/team-still-alive boundary variants.
2. Compare terminal/economy/control/explore terms, delta turns, TD residual, GAE and return; verify telescoping, new exploration only, true terminal absorption and retained truncation. Referee truth may calculate rewards but never enters actor/teacher inputs or value bootstrap.
3. Audit complete game/side sequences in the same S2 batch for missing middle/tails and whole-family exclusions. Measure trajectory lengths, terminal/truncation rates, reward RMS, advantage signs/outliers and value error by phase/action. Do not compute GAE on sampled target suffixes.
4. Report each target's actual optimization weight `1 / (batch windows * decisions in its window)` against decision normalization and committed exposure; quantify long chains/games, terminal/recruit weighting, window coverage and rejection position.
5. Inspect recorded controller versions, references, complete windows and control events; verify the existing rolling-window repair rather than reopening it without a counterexample. RCA must not reuse Astra calibration. No coefficient changes or new end-turn penalty here.

**Exit:** oracle mismatch/missing tails leads to a narrow counterexample fix. Weak signals with correct computation remain learning hypotheses. The new native terminal path requires existing [TEST N1](TEST.md); lite evidence cannot close it.

### S5: Recruit/action error decomposition and comparable learning trend — H4/H5

1. Use the user's observed replay or existing failures, at most 12 legal contexts: six recruit, three move, three attack/end-turn; report absent classes rather than collecting games. Capture map/faction/partner, gold/castle connectivity, time, visible enemies, army mix, candidates and execution.
2. Split recruit availability, unit type, location and subsequent deployment. Preserve teacher intent versus execution. Check whether a proposed good action is legal and survives the work/128 cap. Never insert teacher answers into actor candidates to manufacture coverage.
3. Explain errors using hand-checkable local rules. Future RCA advice is a same-native-context reference, not an infallible oracle. Separate copied teacher mistakes, student mistakes and unrepresentable teacher intent. Remaining moves alone do not make a defensive end-turn wrong.
4. Stratify existing BC accuracy/coverage by faction/map/phase/source/real scenario cluster; report denominators and cluster counts, especially the 43 2v2 recruit targets. Do not describe this as 93% strength.
5. Compare last BC/PPO/selected only on existing matched panels and preserve selection reasons. Missing comparability becomes a proposed minimal validation pairing, not holdout tuning or retrospective reselection.

**Output:** at most 12 counterexample cards, stratified errors and checkpoint ledger. Fix candidates/supervision only when a concrete counterexample warrants it; do not keep patching Astra recruiting in this work.

## 4. Replace every active Astra role with stock RCA

### R0: Establish capabilities before changing names

`lite_host` rejects baseline; `experiment.execute` substitutes Astra for lite baseline. Teacher scheduling, manifest, validators/sampling, native collection/DAgger and reward references also hardcode Astra. `engine=native` alone still queries `gpt6astra/lua/*.lua` and retains Astra in fixed opponents.

Stock baseline runs default RCA inside native Wesnoth, including native candidate actions. The collector wraps Lua `ai.move/attack/recruit` calls: **coverage of default C++ RCA execution is unproven**. There is no accepted read-only next-action RCA query interface.

1. Trace versioned 1.18.8 default AI configuration, C++/Lua candidate actions and recruiting, identifying actual parameters and collection interfaces. Adapt the boundary rather than writing an approximate replacement strategy.
2. Recommended first route: run actual native RCA and establish complete action collection plus read-only queries. This changes throughput and combat randomness from lite; a string rename cannot run native RCA inside lite.
3. Retaining lite sampling requires separate proof of reusable original candidate actions, equivalent legal visible contexts, rules/identity and decisions. Otherwise mark unsupported; no hidden Astra or custom-strategy fallback. This plan does not authorize a large C++ engine port.
4. Use a distinct teacher identity such as `wesnoth_default_rca`, freezing executable/version/build, default configuration, available implementation/build hashes, rules/fog/sharing/parameters/RNG. `teacher_profile=native` does not prove stock RCA. Native startup seed does not promise deterministic whole-game replay: preserve actual replay/RNG audit evidence inside the referee, never as teacher inputs.

**Capability gate:** promise complete BC/DAgger replacement only after actual native actions can be captured and a legal read-only query works. Opponent-only replacement is partial. Missing DAgger capability blocks that chain; never fabricate end-turn labels or mix Astra back in.

### R1: Replacement inventory

| Responsibility | Current owner | Target and assertion |
| --- | --- | --- |
| Teacher/fixed opponent freeze, manifest/config | `learning/manifest.py`, `teachers/`, `experiment.py` | New active external teacher/fixed AI is stock RCA; remove lite baseline→Astra substitution; reject Astra and bind real implementation identity |
| BC games, 2v2 partner, opening probe | `schedule.py`, `sample.py`, `collector.lua` | Actual RCA controller; capture pre-action legal context, intent and outcome for recruit/move/attack/end-turn; missing capture cannot pass |
| DAgger/PPO BC rehearsal | `native_rpc.lua`, `collector.lua`, `lite_host.py`, `experiment.py` | Read-only RCA advice on student states; no mutation of game/RNG/AI internal state/student memory; no old Astra original/DAgger targets in the new active pool |
| Rollout fixed opponent, FFA filler, 2v2 partner | `schedule.py`, `experiment.py` | Replace every external Astra role; preserve same-format student/history/current self-play roles; no inherited Astra training-state pools |
| Reward references/calibration | `reward_metrics.py`, `control.py`, `experiment.py` | Same-layout RCA references with actual identity; old `astra_*` names/cache cannot masquerade as RCA; preserve thresholds/formula/coefficients |
| Trend/promotion/champion/final/reporting | `evaluate.py`, `schedule.py`, `experiment.py`, `report.py` | RCA fixed control, separate 2v2 partner/self-team contexts; preserve student champion comparison, completeness, budgets, fallback and selected-hash gates |
| Samples/pools/checkpoints/export/bundle/docs | `data.py`, `sequences.py`, `checkpoints.py`, `export.py`, bundle/docs | Propagate actual new teacher identity; distinguish RCA from native/lite Astra; new manifests have no active Astra dependency; retain historically accurate reading of old artifacts |

“Every” means future active roles and dependencies, **not deletion or relabeling of historical Astra evidence**. Preserve old packages, runs, installs and audit compatibility. Future initialization from old weights needs an explicit user choice and lineage, not a same-source resume. New defaults must not load old Astra corpora/optimizer/RNG/opponent pools.

### R2: Minimal checks before any formal training

1. Share one minimal legal fixture covering native recruitment, movement, attack and end-turn; staged setup is acceptable. Local reference first, isolated Ubuntu next. Verify real RCA execution, not a mocked baseline name.
2. Assert pre-action obs/candidates, actual intent/outcome for every target; preserve partial moves and move→attack identity. Unmatched intents remain diagnostic, never fake `choice=0` end-turn. Original candidate-coverage gates must pass or block explicitly.
3. Perturb hidden enemies/unexplored terrain while holding visible context constant; check teacher independence from hidden truth. Check game, available AI state, RNG and student memory before/after queries. Missing read-only/information guarantees block capability; do not send full referee snapshots into the policy.
4. Assert actual RCA resolution at teacher/DAgger/fixed-opponent/partner/reference/evaluation entry points; reject Astra samples, false native identities and stale reference caches. Combine active dependency scans with call validation; historical folders may retain Astra strings.
5. Complete existing N1 for affected native terminal/truncation paths. Reuse unrelated budget/selection/export-identity/PPO-count/cancellation evidence; reopen affected contracts only. New behavior assertions must fail on revert.
6. Action/query wiring is not full-board tactics or strength. Short games, three-format phase chains and any training duration/scale require later explicit instructions. Do not promise lite's 30-hour throughput on native.

## 5. Order, deliverables and completion

Order: **S0 → S1 → S2 → S3**, with S4 sharing the frozen batch and contract defects fixed first; S5 explains recorded behavior. R0 static interface investigation can be prepared alongside, but actual migration follows preservation of the old run's causal evidence. Do not defer PPO checks until migration, or change the whole system before diagnosis.

One narrow PR per proven behavior: counterexample→failing assertion→minimal fix→local→affected Ubuntu acceptance→report and bilingual architecture/TEST update. Split RCA work by actual dependencies: capability investigation, execution boundary, teacher collection/query, remaining role wiring. Do not start with a generic plugin framework. Unimplemented diagnosis stays here; implemented pending acceptance enters TEST.

Every new evidence stage records source/input/model/optimizer/rules/teacher hashes, commands/exits, caps/counts/resources, first divergence, PASS/FAIL/NOT RUN/REUSED, original reused paths and limits. Stop and report missing evidence instead of repeatedly running unchanged checks.

Root-cause diagnosis requires a reproducible counterexample, first incorrect step or ineffective learning mechanism, ruled-out alternatives, one-variable intervention/control, revert-failing assertion and relevant minimal Ubuntu evidence. Correlation supports a hypothesis, not a unique proven cause. Full Astra replacement requires acceptance of all R1 active roles/identities. Resumed training, strength improvement and convergence remain separate outcomes.

Not run this turn: server evidence retrieval, trajectory deduplication, zero-step replay, gradient ablations, new GAE oracle, native RCA capability probes, new games, training or strength panels.
