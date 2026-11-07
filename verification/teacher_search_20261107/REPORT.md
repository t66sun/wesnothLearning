# Independent search teacher: delivery and native evidence

The independent teacher is delivered. The overall six-cell strength gate is **not passed**: duel and 2v2 pass both horizons; FFA passes neither. All 524 planned holdout games completed, with zero contestant faults, hard-time overruns or budget interruptions. No additional games, tuning or reselection followed the frozen holdout.

FFA 30-turn gain is below 0.10 and its interval crosses zero. FFA 100-turn gain exceeds 0.10, but its interval also crosses zero. These complete results do not establish the required FFA improvement.

## Delivered package

[Independent Lua package](../../delivery/search_teacher_20261107/selected_teacher.zip) · [portable version/configuration manifest](../../delivery/search_teacher_20261107/manifest.json).

Package SHA256: `6b461de4e99303321b0119a7b88babd575c2d786500b28da4cb45d3c2bdabdb3`.

| Format | Frozen candidate | Algorithm | Source commit |
| --- | --- | --- | --- |
| duel | `clean_fortified_pruned` | beam | `50c5035ce61be1a5becebd7a0a9ccdc01b8fe737` |
| ffa4 | `clean_fortified` | beam | `2c0c2cd10f0cbd7ec71dfac03851a18db12fc93f` |
| team2v2 | `clean_fortified_pvs` | pvs | `3b3178233ab1ea9a53a5913ec27646c181dd9bca` |

All three strategies include the corrected offensive-resistance capture. Duel retains branches after opponent-response evaluation; FFA preserves the earlier beam retention variant that won its validation comparison. Team uses PVS with a configured maximum depth of 6. The artifact audit compared all 46 per-format Lua files with their original packages after namespace relocation only, and verified the unchanged holdout design and experiment clock. [Package audit](selected_package_audit.json).

The interface remains `evaluation(cfg,data)`, `execution(cfg,data)` and `data.plan`. The package is independent; this task did not replace the active Astra teacher or start neural training.

## Formal holdout results

Scores and gains below average physical-scene means. Brackets are the paired scene-cluster bootstrap 95% interval.

| Format | Turns | Games | Scenes | Teacher score | Astra score | Gain | 95% interval | Gate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| duel | 30 | 102/102 | 30 | 0.6361 | 0.3194 | +0.317 | [+0.142, +0.483] | pass |
| duel | 100 | 90/90 | 30 | 0.6708 | 0.3292 | +0.342 | [+0.150, +0.525] | pass |
| ffa4 | 30 | 64/64 | 15 | 0.7042 | 0.6653 | +0.039 | [-0.106, +0.186] | not passed |
| ffa4 | 100 | 76/76 | 15 | 0.4667 | 0.3583 | +0.108 | [-0.133, +0.333] | not passed |
| team2v2 | 30 | 96/96 | 12 | 0.8090 | 0.1840 | +0.625 | [+0.438, +0.802] | pass |
| team2v2 | 100 | 96/96 | 12 | 0.8333 | 0.1667 | +0.667 | [+0.479, +0.833] | pass |

| Format | Turns | Natural win rate | Cap rate | Focal-seat elimination rate | Teacher mean / p95 / max ms | Astra mean ms |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| duel | 30 | 61.76% | 12.75% | 25.49% | 374.6 / 703 / 715 | 23.1 |
| duel | 100 | 66.67% | 1.11% | 32.22% | 382.0 / 704 / 714 | 23.6 |
| ffa4 | 30 | 53.12% | 3.12% | 43.75% | 361.9 / 701 / 710 | 23.0 |
| ffa4 | 100 | 50.00% | 0.00% | 50.00% | 373.2 / 702 / 710 | 22.5 |
| team2v2 | 30 | 80.21% | 2.08% | 23.96% | 625.4 / 705 / 722 | 25.9 |
| team2v2 | 100 | 83.33% | 0.00% | 18.23% | 619.6 / 705 / 727 | 26.4 |

Natural-win, cap and elimination rates are game-weighted descriptive results; they are distinct from the scene-weighted score table. In team games an eliminated focal seat can share its surviving ally’s team win. Timing summaries split by first and ordinary actions, faction-seat exposures and complete scene identities are in [holdout detail](holdout_detail.json).

Duel uses two holdout maps (`caves_of_the_basilisk`, `ruined_passage`) and 30 physical scenes per horizon. FFA uses `morituri` with 15 physical scenes per horizon; 2v2 uses `morituri` with 12. All six standard factions appear in each cell. These scene counts do not mean 30/15/12 distinct maps, and results do not establish strength on every Wesnoth map.

## Clock and execution

| Boundary | UTC |
| --- | --- |
| Exploration start | 2026-11-06T17:47:37+00:00 |
| Exploration deadline | 2026-11-06T22:47:37+00:00 |
| Validation/holdout design frozen | 2026-11-06T22:47:41+00:00 |
| Selected package frozen | 2026-11-06T23:15:39+00:00 |
| Holdout started | 2026-11-06T23:15:39+00:00 |
| Final report produced | 2026-11-07T00:51:42+00:00 |
| Maximum post-exploration deadline | 2026-11-07T02:47:37+00:00 |

Exploration lasted exactly 18000 seconds (5 hours). Validation selection took 1678.0 seconds; the post-exploration phase finished in 7445.4 seconds (2 h 4 min 5 s), within the four-hour limit. Eight workers were used. UTC timestamps above are eight hours behind Beijing time. Preparation directories `experiment` and `experiment_v1` contain no exploration clock; the timed experiment has one unchanged clock.

| Phase | Planned jobs | Completed games | Budget interrupted | Faults / overruns |
| --- | ---: | ---: | ---: | ---: |
| Five-hour exploration | 828 | 781 | 47 | 0 |
| Validation selection | 84 | 84 | 0 | 0 |
| Frozen holdout | 524 | 524 | 0 | 0 |

The last version league completed 37 of 84 games. Its 47 deadline interruptions comprise 8 in-flight games and 39 unstarted jobs; none was scored as a draw. [Panel inventory](panel_inventory.json) and [original clock](experiment_v2/clock.json).

## Candidate comparison

Twenty-nine immutable versions were registered. Thirteen early versions were excluded for native RNG query side effects; 16 remained eligible, 14 of which completed native games. `clean_fortified_deep` and `clean_fortified_reply2` were registered but unplayed. Each entry below is an exploratory gain followed by its distinct physical-scene count; a dash means no completed baseline rotation.

| Eligible candidate | Duel 30 | Duel 100 | FFA 30 | FFA 100 | Team 30 | Team 100 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `clean_beam` | +1.000 [1] | +1.000 [1] | -0.375 [1] | +0.250 [1] | +0.500 [1] | +0.250 [1] |
| `clean_diverse` | +1.000 [1] | +0.000 [1] | -0.542 [1] | -0.500 [1] | +0.500 [1] | +0.500 [1] |
| `clean_exposure` | -1.000 [1] | +0.000 [1] | -0.208 [1] | -0.750 [1] | +1.000 [1] | +0.750 [1] |
| `clean_fortified` | +0.667 [3] | +0.333 [3] | +0.139 [3] | +0.333 [3] | +0.792 [3] | +0.917 [3] |
| `clean_fortified_deep` | — | — | — | — | — | — |
| `clean_fortified_pruned` | +1.000 [1] | +1.000 [1] | -0.083 [1] | +0.500 [1] | +1.000 [1] | +1.000 [1] |
| `clean_fortified_pvs` | +0.000 [1] | +0.000 [1] | +0.250 [1] | +0.250 [1] | +1.000 [1] | +1.000 [1] |
| `clean_fortified_reply2` | — | — | — | — | — | — |
| `clean_guard` | — | — | -0.250 [1] | -0.250 [1] | — | — |
| `clean_hybrid` | +0.000 [1] | +1.000 [1] | +0.083 [1] | +0.250 [1] | +1.000 [1] | +1.000 [1] |
| `clean_pruned` | +0.000 [1] | -1.000 [1] | -0.500 [1] | -0.500 [1] | +0.375 [1] | +0.125 [1] |
| `clean_pvs` | +1.000 [1] | +1.000 [1] | — | — | +1.000 [1] | +0.500 [1] |
| `clean_pvs180` | +1.000 [1] | +1.000 [1] | — | — | +0.875 [1] | +0.500 [1] |
| `clean_reply2` | — | — | -0.333 [1] | +0.250 [1] | — | — |
| `clean_resist` | +1.000 [1] | +0.000 [1] | -0.375 [1] | +0.250 [1] | +0.500 [1] | +0.750 [1] |
| `clean_uct` | +0.000 [1] | -1.000 [1] | -0.083 [1] | +0.000 [1] | +0.625 [1] | +0.750 [1] |

`clean_fortified` qualified for version leagues after completing three scenes in every cell with positive gains. Against this champion, hybrid and fortified PVS tied both duel horizons; historical `clean_pvs` tied duel 30 and lost duel 100 (gain −1.0). FFA/team version-league rotations were incomplete at the deadline and have no complete-block gain. Full results, including excluded versions, are retained in [exploration comparison](exploration_comparison.json) and [candidate identities/configurations](candidate_inventory.json).

Validation compared the three nominated candidates in each format on the same complete one-scene rotation. It selected the smaller horizon gain first, then the mean and action time:

| Format | Candidate | 30-turn gain | 100-turn gain | Selected |
| --- | --- | ---: | ---: | --- |
| duel | `clean_beam` | -1.000 | -1.000 |  |
| duel | `clean_fortified_pruned` | +0.000 | +1.000 | yes |
| duel | `clean_pvs` | -1.000 | +1.000 |  |
| ffa4 | `clean_fortified` | -0.083 | +0.250 | yes |
| ffa4 | `clean_fortified_pvs` | -0.542 | +0.000 |  |
| ffa4 | `clean_hybrid` | -0.458 | +0.000 |  |
| team2v2 | `clean_fortified_pruned` | +0.750 | -0.250 |  |
| team2v2 | `clean_fortified_pvs` | +0.500 | +0.500 | yes |
| team2v2 | `clean_hybrid` | +0.000 | +0.000 |  |

[Matched validation](experiment_v2/selection/matched_validation.json). One validation scene per format is selection evidence, not the formal strength test. UCT and hybrid search were implemented and exercised, but neither was selected in the delivered package.

## Scope and interpretation

This experiment delivers an independent native Lua teacher using the existing `evaluation(cfg,data)`, `execution(cfg,data)` and `data.plan` interface. The active Astra teacher, student candidates, BC/PPO and DAgger are unchanged. No neural training ran.

The measured comparison uses the requested unequal decision budgets: search seats have 2 seconds per ordinary call and 20 seconds for their first call; maintained Astra keeps 1 second and 10 seconds. The search soft deadlines are 700 ms tactical and 1000 ms total planning, both measured from the same evaluation start. Reported action times include loading, evaluation and execution. These results do not establish an equal-time algorithm comparison or a traditional-search strength ceiling.

Every strength result comes from Wesnoth 1.18.8 native matches. Thirty-turn scores use the existing official adjudication, with duel/team scores divided by three. Hundred-turn scores use natural winners 1, losers 0, and capped surviving players or teams 0.5. Team results are shared. Faults and interrupted games are not ordinary draws.

The inherited pairing design uses two seats in duel, one candidate plus one Astra and two official baseline fillers in FFA, and both baseline-partner and self-team contexts in 2v2. Each physical scene has complete seat rotations: 2 duel, 4 FFA, or 8 team games per horizon. A physical scene is identified by map, starting factions, teams, rules and task settings; changing only the random seed creates no new scene. The scene inventory reports map counts separately, so multiple faction configurations on one map are not described as multiple maps.

## Selection and evidence rules

Exploration used train maps. Complete one-scene screens are exploratory, including any `passed` flag computed with the exploration reporter's one-scene floor. They are not final acceptance. Temporary league qualification requires all six cells to be nonnegative over at least three independent scenes, with a positive overall mean.

Selection uses at most the three highest ranked explored candidates per format on matched validation scenes. The order is the smaller of the 30/100-turn gains, then their mean, then lower action time. The holdout design is frozen from measured exploration throughput before validation results are inspected. The per-format choices are composed without retuning, and holdout results cannot change them.

Final acceptance requires complete planned rotations, at least 12 physical scenes in each of six cells, no faults, mean improvement at least 0.10, and a scene-cluster bootstrap 95% lower endpoint above zero. Bootstrap resampling uses 5,000 scene resamples. The mean gain and interval use complete rotation blocks. Descriptive natural-win, cap and seat-elimination rates use all valid completed games; any incompleteness is shown explicitly. In team games, elimination rate describes the focal seats, while the scored result is shared by their team.

## Implemented search and model limits

The public reader captures visible units, own state, explored terrain, visible village ownership, public time of day and legal historical memory. Search receives plain local state and a private random stream. Referee snapshots, hidden units, unexplored terrain, real RNG draws and opponent weights do not enter the policy.

Unified root ordering compares recruitment, attacks, movement and ending the turn. Beam search considers short own-action chains with opponent responses; each FFA opponent chooses according to its own utility. Optional variants add iterative PVS with transposition bounds for duel/team, sampled local UCT, and hybrid search that preserves beam strategic choices and spends remaining time refining combat. Hybrid replacement requires root coverage, visit counts and a sampled utility margin. Each actual call executes only the first selected action and then observes again. Ambush or newly revealed enemies stop the previous plan.

The local combat model covers standard strike ordering, retaliation, death, slow, poison, drain, first strike, charge, backstab, terrain defense, time of day, leadership, illumination and steadfast. Standard visible village, regeneration and adjacent allied healing are modeled. Unsupported continuations, including berserk, plague and advancement, stop deeper search and use the local estimate. This is a bounded approximate model, not a native-engine replacement. Enemy recruitment/income, unseen armies, rest healing, arbitrary ability filters and complete trait/rounding semantics are outside its fidelity claim.

Explored changes include keep-access gold value, combat caching, leader elimination, leader home and exposure values, recruit composition preference, multi-action replies, response-aware beam retention, PVS depth/root budgeting, UCT width/depth and combat-only hybrid refinement. Frozen candidate manifests preserve the exact source commit, parameters and package hash for every version, including failures and unplayed registered candidates.

## Correctness findings

The native query audit found that creating recruit templates without a fixed facing consumed cosmetic native randomness. Thirteen early candidate packages remain in the record but are excluded from final nomination through the separately frozen selector release. The original baseline, experiment clock, schedules and results were not rewritten.

Later native inspection established that `resistance_against(kind)` defaults to defensive resistance and already incorporates steadfast. Newer profiles explicitly capture offensive resistance before applying steadfast in the local defensive calculation. Response-aware beam retention also fixes a witness where immediate-gain pruning discarded the branch with the better completed reply value. Older strategy versions remain identifiable; their local models and search variants must be interpreted according to their own source.

Ubuntu model checks cover interfaces, weapon indexing, ambush interruption, search benefits over one-step greed, PVS versus exhaustive small trees, private Monte Carlo repeatability, local state immutability, public-input boundaries, scoring, seat budgets, rotations, fault classification and phase deadlines. The native audit retains the original recruit-template cases and adds separate hybrid combat cases. Actual hybrid sampling preserves battlefield state, successor unit identity and subsequent native random draws, and its public input/decision are unchanged in the hidden-information fixture. These are concrete fixture results, not a proof of all native semantics.

The consolidated 67-check run targets implementation commit `020cc38712d34f03118865bd8ea57e54443f9cc3`; the eight-case native audit targets `3611cb1af8c17f74938396dd5fb5c2394e7d5799`. Historical contestants retain their own frozen source and recorded checks. The selected-package audit identifies their model versions, including whether they contain the offensive-resistance correction and response-aware beam retention. New implementation checks are not relabelled as checks of every historical package.

Source, package and score identities are retained in the evidence index. Raw native events and replays remain available in the evidence archive and on the Ubuntu acceptance host. No historical evidence or frozen input was edited.

## Reproducible evidence

Frozen evaluator source: `2da826c1d5ac4ffe1e282fc1ad02131f9fb25f34`. Reviewed selector: `35d8f04a582fd4537d3d65945c2de44915a8bb56`. Current implementation before delivery documentation: `5d086673384d904879f8f3b729b27b4f3104eb74`.

Maintained Astra source: `dffbfe9946234a73e0af7b1bdeda3625fd9284bc5788f8e30a7f22df83b4b844`; baseline archive: `f19cf216870a82b934321225d4b6ef7f3c258d490dbdaa2d5f728d80f8c732e5`. Its source commit is `2da826c1d5ac4ffe1e282fc1ad02131f9fb25f34`.

Native executable: `33f64aa3f5ee40228bd44e357b3f4d784121d4392ff774d6c059c7defa3e5fcf`; entropy component: `f12d763303445aa437de06d0dba129dc923e3d81fd1fc82d72b8e331916480cf`; native rule capture: `c769a4d62cd95ed96028cd8931e7030883547b12ec5972f194ef9272741a9021`.

The consolidated Ubuntu run completed 67 tests in 5.872 seconds with exit code 0. [Command/source identity](final_checks_20261106T215040/identity.json), [full test output](final_checks_20261106T215040/unittest.txt), [eight-case native audit](query_audit_hybrid_v5/summary.json), [native audit source binding](query_audit_hybrid_v5/identity.json), and [reverted-fix regression evidence](review_regressions_20261106T1936.json). No Windows behavior tests ran.

The server recomputation exactly reproduced all six comparisons in `final.json`. The downloaded 252 metadata files and both archives matched their recorded hashes. [Copy verification](LOCAL_COPY.json), [metadata file hashes](SHA256SUMS.json), [archive identities](ARCHIVES.json).

The small report, selected package, configuration and summary evidence are committed. Full schedules, results, original packages and checks are in local `metadata.tar.gz`; raw events, replays, preparation failures and native audits are in local `raw_evidence.tar.gz`. Both archives are kept outside Git. Their immutable server copies are under `/home/tongshu/myDev/wesnothLearning/verification/teacher_search_20261107/export/` on `cpuServer`. Source archives remain under the sibling `sources/` directory and are excluded from the raw-evidence tarball.

Export/recomputation and artifact-audit procedures are retained as `export_evidence_20261107.py`, `archive_evidence_20261107.sh` and `selected_package_audit_20261107.sh` in the metadata archive. Existing evidence uses exclusive creation; any rerun must use a new output location.
