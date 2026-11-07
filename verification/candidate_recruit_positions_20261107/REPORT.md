# Frontline and lower-exposure recruit placements

Ubuntu `cpuServer`, 2026-11-07. [#274](https://github.com/t66sun/wesnothLearning/issues/274) · [#228 public witness](../candidate_support_20261106/REPORT.md)

The frozen `recruit_positions` decision now offers 12 distinct affordable Spearman/Mage pairs outside the declared public next-turn attack envelope. The B1 control offers zero. The test and probe execute a Spearman at `(4,2)` followed by a Mage at `(4,3)`, spending all 34 gold. Each type retains four frontline options at `(6,2)` through `(6,5)` and gains four lower-exposure options at `(4,2)` through `(4,5)`. Both pools contain 16 recruits and end turn. The before/after lists include all eight displaced recruit intents. [Red assertion](red.log) · [Retained and executed placements](timing.json)

Recruit ordering reuses the original movement threat map once per decision. Its reach calls and scanned positions remain charged to the existing budget, and the map leaves work for recruit probes. Only a completed expansion of all visible enemies can distinguish exposed castles from lower-exposure castles. On a mixed board, each affordable type alternates nearest and lower-exposure legal sites, with at most eight proposals and one probe per type and site. The original nearest order supplies any shortage. The final six-slot recruit reserve uses the interleaved order through its existing per-type passes. The candidate identity is `schema5-work-12000-v10`.

The crowded control retains a frontline and a lower-exposure choice for each type under the 37-candidate cap. Its initial assertion also expected distinct lower-exposure hexes in that pool, but the existing reserve retains `(4,2)` for both types. The corrected crowded check tests per-type choice under the original cap. The exact #228 fixture still requires a distinct pair and its successful execution. The all-exposed control keeps the nearest legal sites, the 13-visible-enemy control keeps the original order after the 12-enemy map cap, and the frozen hidden-unit and hidden-terrain changes leave the policy inputs identical in a recruit-enabled pair. [Initial crowded assertion](initial-crowded-control.log) · [Crowded responsibility check](crowded.log)

## Paired cost and real board

The B1 production timing protocol warms each arm once, then alternates v9/v10 and v10/v9 for two measurements per arm. Construction uses the generator's integer millisecond clock. Whole decision time includes observation, construction, DTO serialization and Python decoding. [Raw measurements](timing.json) · [Host window](host.txt)

| State | Candidates | Construction v9 → v10, ms | Decision v9 → v10, ms | Reach calls | Recruit probes | Charged work |
| --- | ---: | --- | --- | ---: | ---: | ---: |
| #228 recruit witness | 17 | 3, 2 → 2, 2 | 4.52, 4.21 → 4.03, 4.00 | 2 → 2 | 16 → 16 | 248 → 248 |
| Recorded turn 2, side 4 | 37 | 11, 11 → 12, 12 | 17.65, 17.57 → 17.57, 17.59 | 6 → 6 | 168 → 168 | 5,606 → 5,606 |

The recorded turn comes from `bc_right_side_20261101.json.gz` with 26 live units, all leaders alive, and 33 gold for side 4. As in B1, the probe initializes a current-profile game from the recorded board and live units with fresh observation history. All seven affordable types retain the sole candidate hex `(24,12)`, and every non-recruit candidate is identical between variants. This state measures cost with actual recruit probes and shows no support change. The two timing samples bound these states. Candidate behavior and playing strength on broader match distributions remain open for [#275](https://github.com/t66sun/wesnothLearning/issues/275).

## Source and checks

The branch is based on the accepted B1 head `433c44300e1f75b7415b07fb49703b78882fd63b`. The v9 red source contains only the new tests and probe above B1. Its required #228 assertion exits 1 with an empty pair list. The first v10 run passes 50 checks including the #228 execution, hidden, all-exposed, partial-map, work/type and B1 weapon controls. The initially overbroad crowded assertion accounts for its single failure. The corrected crowded check passes on a test-only descendant of the timed source. [First focused run](initial-crowded-control.log) · [Corrected check](crowded.log)

| Purpose | Shipped commit | Archive SHA256 | Directory under `/home/tongshu/acceptance/` |
| --- | --- | --- | --- |
| v9 red and paired control | `56e9d5bfe8d5cb82547b2d5005799a9e1d563765` | `334a950e7e92294a2873b63a931c14344c7146359f75d5c5c01564db0c484915` | `candidate_recruit_red_20261107` |
| v10 production, timing and first checks | `0c12ca360ae8a45f460bd3e1e535831a9411a113` | `601e995b941cb10314a06198fd2ea1ae869154844b1def664be9c4dbf4411310` | `candidate_recruit_green_20261107` |
| v10 crowded responsibility check | `7d3a6cfbaeef77931ecabaa19cd94fb404c76fbc` | `bad0429305dacaf59cc6f46b6794837c6cebb40e4c97e20da5e87863082d26ba` | `candidate_recruit_cap_20261107` |

Rules SHA256 `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`. Lite extension SHA256 `56dd77140411db987377d6de4ffbf562da4d0e5c76bc16d34780da67e60e5ae4`. Recorded turn fixture SHA256 `bcb11734bbf631dadf6e9b3481fb5e91e69f9bb6b26cd933ee0953c48e933bf9`. The independent exposure labels come from the immutable #228 measured witness. The check scope covers fixed Lite behavior and cost. [Exposure labels](../candidate_support_20261106/measured.json)

Ship each committed source subset with `git archive --format=tar.gz` and extract it into a fresh directory. From the v10 timing directory run the paired probe and focused checks with these inputs. Run the crowded check from the test-only descendant with the same environment and its own source root on `PYTHONPATH`.

```bash
export PYTHONPATH="$PWD:/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension:$PWD/vendor/arena"
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
python=/home/tongshu/venv/bin/python
"$python" verification/candidate_recruit_positions_20261107/probe.py \
  --baseline ../candidate_recruit_red_20261107 \
  --real-board data/datasets/diagnostic/bc_right_side_20261101.json.gz --output ../recruit-timing-new.json
"$python" -m unittest tests.v5.test_candidate_recruit_positions tests.v5.test_candidate_weapon_retention \
  tests.test_candidate_budget tests.test_lua_contracts tests.v5.test_candidate_pool_budget \
  tests.v5.test_candidate_provenance tests.v5.test_candidate_gating tests.v5.test_duel_hurt_branch \
  tests.v5.test_tactical_inputs tests.v5.test_forecast_public_context -v
"$python" -m unittest \
  tests.v5.test_candidate_recruit_positions.CandidateRecruitPositionsTests.test_front_and_low_exposure_survive_the_final_slot_cap -v
```
