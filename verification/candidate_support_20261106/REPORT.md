# Candidate support on frozen public tactical states

Issue: [#228](https://github.com/t66sun/wesnothLearning/issues/228), part of [#221](https://github.com/t66sun/wesnothLearning/issues/221). Date: 2026-11-06.

## Finding

Two reproducible positions demonstrate **immediate useful-action omissions**, at different stages. Final 36-slot allocation excludes a marksman's ranged attack with 47.52% kill probability and zero expected retaliation, while retaining its melee attack with zero kill probability and 10.8 expected damage to the attacker. Separately, the eight-location proposal cap per recruit type excludes every tested two-role placement outside the public next-turn attack envelope, even though the final 36-slot cap is not full.

These are restrictions on locally valuable first choices, not a measured playing-strength ceiling or an explanation of the formal run. The omitted ranged attack returns after two other legal attacks. Retreat, leader healing, village capture and slow-first witnesses are already retained and ranked first by both tested policies. Waiting is always available; not selecting it in the night fixture is not proof of a strategic error.

Production candidates, budgets, model architecture, weights and training code are unchanged. This work constructs fixed synthetic states and performs short referee-only legality demonstrations; it collects no matches and starts no training.

## Method and local criteria

[fixtures.py](fixtures.py) declares eleven states covering six themes, including paired slow-status, day/night and hidden-information controls. They use existing frozen standard unit/terrain rules, two opposing sides and explicitly empty prior recurrent history. Coordinates are one-based Lua coordinates. Criteria in [probe.py](probe.py) are independent of model scores:

- **Combat:** for the same actor and target, higher public forecast kill probability, no greater own death probability and less expected retaliation. This is not an optimization over turn plans.
- **Recruitment:** an affordable Spearman/Mage pair on distinct connected castles outside visible enemies' public full-move attack envelope. Roles and location safety are declared fixture goals, not optimal army composition. The witness pair executes consecutively in an isolated referee instance.
- **Retreat/leader safety:** the wounded actor can reach a healing village outside that envelope. **Village timing:** the actor can enter the empty unowned village in the current turn.
- **Attack order:** a slowing attack is selectable before the fighter's melee attack. A paired state measures retaliation conditional on the target already being slowed; slow is not assumed to land certainly.
- **Day/night:** end turn is selectable while public combat forecasts differ across declared turns. Waiting is not assumed better than the enemy's possible response.

The envelope expands only `obs.enemies`, with visibility-aware full-movement reach, then marks adjacent hexes. It is a conservative public possibility set, not an opponent policy or prediction of unseen enemies. Features/forecasts use public Lua observations and legality APIs. Network inputs use an allowlist of global/opponent/spatial/candidate features and turn: referee labels, snapshots, goal predicates, audit properties and teacher outputs are excluded. No teacher query occurs.

| Mode | Definition | Isolated boundary |
| --- | --- | --- |
| Production / A | Unmodified production; diagnostic A must have exactly the same policy DTO | Current supported choices |
| B | Capture the existing pool at `Selection.select`, preserve A entries, materialize all additional unique proposals | Final slot allocation |
| C | B plus all publicly legal recruits, direct attacks and reachable moves in these fixtures | Earlier proposal restrictions |

[audit.lua](audit.lua) is injected only into an in-memory copy of the candidate module. B/C use the existing feature function and public combat forecasts. Existing actions, including detached recruit actors, retain identical features. C's additional moves receive no fabricated tactical-ranking annotations; broad-set network runs measure cost only. Rankings below use A.

Every moving fixture unit has `attacks_left=0`, so no unvalidated move-attack composition is needed. C equals the engine's complete **public legal atomic-action set** in every fixture. That comparison canonicalizes full/partial move variants by actor/destination; the candidate counts below retain variants and include end turn. This does not establish exhaustive composite actions in arbitrary states.

## Reproducible support results

| Fixture | A | B | C | Local witness in A/B/C | Interpretation |
| --- | ---: | ---: | ---: | --- | --- |
| Recruitment | 17 | 17 | 49 | 0 / 0 / 182 safe two-role position pairs | Earlier proposal omission |
| Combat slots | 37 | 43 | 43 | 0 / 1 / 1 ranged witness | Final retention omission |
| Retreat | 22 | 22 | 133 | 2 / 2 / 2 move variants | Retreat already supported |
| Leader safety | 22 | 22 | 134 | 2 / 2 / 2 move variants | Escape/healing supported |
| Village timing | 17 | 17 | 221 | 2 / 2 / 2 move variants | Immediate capture supported |
| Slow-first / slow-landed pair | 5 | 5 | 5 | Relevant attacks present | Ordering support confirmed |
| Night/day waiting pair | 3 | 3 | 3 | End turn present | Waiting is not masked |
| Hidden-information pair | 15 | 15 | 221 | Exact input equality within each mode | No unseen-input dependence |

### Final allocation omits a locally superior weapon

`combat_slots` has sixteen immobile archers/marksmen, sixteen visible adjacent targets and ten legal recruits. Its 32 direct attacks fit the probe cap exactly. B=C rules out an earlier proposal restriction for this example. Final allocation retains eight recruits and 28 attacks plus end turn. The marksman at `(9,3)` attacks the grunt at `(9,4)`:

| Weapon | In A? | Kill probability | Expected target damage | Expected own damage | Own death probability |
| --- | --- | ---: | ---: | ---: | ---: |
| 1, melee | Yes | 0 | 7.20 | 10.80 | 0 |
| 2, ranged | No; in B/C | 0.4752 | 17.1072 | 0 | 0 |

Assertions check omission and local forecast dominance. [candidate_selection.lua](../../lua/candidate_selection.lua) ranks/reserves proposals before [candidates.lua](../../lua/candidates.lua) computes combat forecasts for retained actions. The omitted weapon cannot benefit from its favorable forecast at that boundary.

A fixed-seed referee replay records availability `[false, false, true]` after zero, one and two other legal attacks. This restricts the immediate action/order choice, not permanent reachability, and does not prove that this first attack is globally optimal.

### Eight recruit positions exclude safer combinations

`recruit_positions` has 24 empty connected castles, two affordable types and exactly enough gold for one Spearman and one Mage. C contains all 48 legal `(type, castle)` pairs. A/B contain only the nearest eight positions per type; none is outside the declared attack envelope. C has 28 individual placements outside it and 182 distinct affordable role-position pairs.

The witness recruits a Spearman at `(2,2)`, then a Mage at `(2,3)`. Both execute legally, leaving zero gold. Both types already exist in A: this is a placement/combination restriction, not absent type diversity. The eight-location loop and nearest-enemy ordering in [candidates.lua](../../lua/candidates.lua) own it; raising 36 cannot fix this fixture because the final cap is not reached.

### Supported actions and frozen-model ranking

Both BC v38 and PPO v940 rank the healing-village move first for retreat and leader safety, village capture first, and the slowing attack first. These examples contradict blanket claims that retreat, primary movement or useful attack ordering are absent, and show no ranking miss for those local goals.

Conditional on slow landing, the fighter's expected retaliation falls from 16.8 to 8.4 HP while its expected inflicted damage remains 11.2 HP. These are paired visible states, not a favorable sampled RNG outcome.

At night, end turn ranks third for BC and second for PPO; both choose the Spearman's ranged attack. The melee forecast is 9.0 inflicted / 13.2 received HP at night versus 16.2 / 8.4 in the day counterpart. This distinguishes availability from scoring, but enemy responses to waiting were not evaluated, so the preference is not labeled a strategic mistake. In the two omission fixtures the witness is unavailable in A and both policies choose a recruit; adding support is not shown to make either policy select the omitted action.

## Cost

Five warmed repetitions ran in a coordinated Ubuntu window, 2026-11-06 05:08:50–05:09:34 UTC. Python 3.12.3/PyTorch 2.9.1+cpu used one intra-op/inter-op thread; OMP/MKL/OpenBLAS were each one. [Host before](host_before.txt), [host after](host_after.txt), individual wall/CPU observations and model hashes in [measured.json](measured.json) retain the actual scope.

Means below are wall milliseconds. **Decision construction includes public observation, candidate construction and DTO serialization.** A-audit/B/C additionally compute the public attack-envelope/goal diagnostics; B/C materialize added actions. These are not pure candidate timers or estimates of an optimized production replacement. Packing/forward are separate fixed-weight measurements with empty history and exclude engine work. The table uses PPO v940; BC measurements remain in the raw artifact.

| Fixture | Production decision | A-audit | B-audit | C-audit | A pack / forward | C pack / forward |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Recruitment | 3.78 | 4.43 | 4.45 | 7.68 | 0.34 / 1.13 | 0.72 / 1.41 |
| Combat slots | 12.58 | 16.17 | 17.23 | 17.42 | 0.72 / 1.31 | 0.80 / 1.35 |
| Retreat | 4.50 | 5.14 | 5.19 | 14.65 | 0.40 / 1.17 | 1.72 / 2.10 |
| Leader safety | 4.49 | 5.18 | 5.21 | 14.77 | 0.39 / 1.16 | 1.72 / 2.10 |
| Village timing | 3.81 | 4.14 | 4.17 | 22.33 | 0.34 / 1.14 | 2.77 / 2.93 |
| Slow first | 2.22 | 2.74 | 2.66 | 2.70 | 0.21 / 1.05 | 0.20 / 1.01 |
| Night waiting | 2.12 | 2.66 | 2.66 | 2.70 | 0.18 / 1.03 | 0.18 / 1.00 |
| Hidden control | 3.18 | 3.38 | 3.32 | 22.87 | 0.33 / 1.15 | 2.88 / 2.99 |

Broad movement enumeration expands 17–22 candidates to 133–221 without adding a better witness for these retreat/village goals. This supports targeted proposal/retention investigations before a blanket increase. Five repetitions on selected small states do not establish production throughput, long-game scaling or strength gains.

## Scoped follow-ups and limits

1. **Recruit placement:** compare interleaving public safety and forward proximity within the existing eight locations per type. Preserve affordable-type diversity and total work limits. The demonstrated gap is positional.
2. **Final combat retention:** compare bounded forecast-aware weapon ranking or weapon-diversity allocation before final selection, preserving primary moves and the existing work/forecast limits. The witness does not authorize increasing all caps.
3. **Supported categories:** these examples support leaving retreat, healing, village and slow-first categories unchanged. Waiting needs an opponent-response/turn objective before calling a ranking choice wrong.

These are future separate changes, not implementation/training authorization. The panel covers synthetic duel states and the existing Lite approximation scope. It does not measure natural-state omission frequency, FFA/team interactions, arbitrary composite move-attacks, hidden tactical opportunities, multi-turn optimal plans or full native semantics. Empty-history v38/v940 inference is not a strength comparison. FFA teacher coverage is separate evidence and cannot attribute duel/team PPO outcomes to these examples.

## Identities, assertions and reproduction

| Item | Identity |
| --- | --- |
| Branch base | `ad7256e838fa941d76d92bf5d56a4683f75b37cd` |
| Tested/measured diagnostic | `e242038e3bdb687ad6ffc58e832995875d58b6af` |
| Source archive SHA-256 | `3e023c41fa58ef390a52572d8a600f5dd0a55f6ba90897491e321768e440c9bb` |
| Ubuntu source | `/home/tongshu/acceptance/candidate_support_20261106_initial/source` |
| Rules SHA-256 | `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17` |
| BC v38 checkpoint SHA-256 | `05908d7f972148ccc7b39b8df0cc00435e2176861654a632de44c379b94953ab` |
| PPO v940 checkpoint SHA-256 | `e68b50e62d5a6452718f6496d7ff1bc28bc4d966975332e0fdf83cf34fde155b` |

All assertions passed in the [functional](functional.log) and [measured](measured.log) runs: A equals production; A ⊆ B ⊆ C; retained features match exactly; C equals public legal atoms; game/RNG is unchanged by queries; hidden-information differential equality; both omissions; executed recruitment pair; delayed ranged-action recovery; supported local goals; conditional combat differences. Model digests remain unchanged after inference. Exact specs and their hash are in [measured.json](measured.json). [Source checks](source_checks.txt) verify no production change and unchanged measured diagnostic code. No Windows tests ran.

Ship `git archive` of the tested commit to a fresh Ubuntu directory, then run from the extracted source:

```bash
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PWD:/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension"
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
/home/tongshu/venv/bin/python verification/candidate_support_20261106/probe.py \
  /tmp/candidate-support-new-functional.json
# Coordinate a CPU window before adding the read-only timing/model panel:
/home/tongshu/venv/bin/python verification/candidate_support_20261106/probe.py \
  /tmp/candidate-support-new-measured.json \
  --run /home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/runs/formal_30h_scratch \
  --repetitions 5
```

Outputs must be new files; existing evidence is never overwritten. No git is needed on the host. [SHA256SUMS](SHA256SUMS) identifies the report/artifacts. This diagnosis adds no production implementation acceptance item to `docs/TEST.md`.
