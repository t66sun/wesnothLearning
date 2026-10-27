# R4 scenario evidence in every verdict — 2026-10-27

Issue #58, parent #48. Implementation `a05533f874cd9e28763bfef3469ad4869864d135`, based on `81b2ae7` (R3 merged).

## Result and actual limitation

The run config, frozen in the manifest, declares distinct-scenario floors: trend 3, promotion/final/BC gate 12. Validation rejects lower floors. Schedules enumerate existing map/faction scenarios explicitly and mark repetitions without increasing block/game counts. Complete rotation blocks with the same physical scenario form one bootstrap cluster; estimates and confidence intervals average scenario means, so unequal repetition does not weight one scenario as many independent samples. `min_blocks` and the positive lower-interval pass condition remain required.

Panel artifacts report `distinct_scenarios` and `min_distinct`; insufficient design propagates through aggregate status, model selection and the final Markdown report. Cached nomination identity includes the floor. Unmeasured legacy panels cannot nominate a candidate; historical files remain untouched. BC gate reports actual scenario coverage in the rows used for its verdict, `scope=initialisation_only`, and `insufficient_design` below its floor. It cannot reuse a previous effective flag to claim completion with insufficient current evidence. Existing imitation, coverage, corpus and opening gates remain required.

**Current design cannot pass the new floor.** Without adding maps or changing faction coverage, final schedules have duel 6 / FFA4 3 / team2v2 3 distinct scenarios, over the unchanged 60/120/240 games per control. The existing corpus likewise cannot justify the BC floor. These are `insufficient_design`, not strength passes. Widening coverage or changing a floor needs a separate data/design decision; this phase does neither. An insufficient BC verdict cannot complete the automatic BC gate; existing explicitly forced phase behavior is unchanged. No new formal run is launched.

## Local reference

- Repeated-scenario assertion failed first: old comparison returned `passed` instead of `insufficient_design`.
- BC artifact assertion, after correcting an incomplete synthetic input, failed on missing `distinct_scenarios`.
- Initial four new checks plus four validation-cadence checks: 8 PASS (0.768 s).
- Final seven design checks plus cadence: 11 PASS (0.981 s). Additional old-effective-state regression: 1 PASS (1.715 s).
- Schedule/selection/nomination/budget checks initially exposed expected changed repetition semantics and incomplete positive fixtures. Selection fixtures now explicitly carry their scenario count; nomination's old string-valued board fixture is replaced by a valid board, and its positive path supplies twelve physical terrain variants. No original cache, seat-rotation, checkpoint, deadline or candidate-score assertion was removed. Final affected group: 19 PASS (8.704 s).

The nomination string-board mismatch predates R4: `learning/maps.py` is unchanged from the R1 identity implementation and requires terrain/starts. Fixture corrections do not relax a runtime validator. The schedule test's repeated-board verdict now requires insufficiency; the new independent 12-scenario test retains the positive-pass assertion.

## Ubuntu isolated acceptance

Directory `/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r4_20261027_a05533f`; shared dependencies and read-only frozen data reused. Python 3.12.3, torch 2.9.1+cpu; rule SHA-256 `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`. [Environment](ubuntu/environment.log).

Source-only archive: 2,109,440 bytes, SHA-256 `b1e8439ab9e941530f07e795241a2234dabc536f5419f214e8c0e5b3f6fb2f89`; includes baseline evaluate/experiment modules for deliberate reverts, excludes data/runs/dependencies.

```powershell
scp tmp/refactor_r4_20261027/source.tar cpuServer:/tmp/wesnoth-r4-a05533f.tar
scp verification/ppo_refactor_r4_20261027/run_ubuntu.sh cpuServer:/tmp/wesnoth-r4-a05533f.sh
ssh cpuServer "bash /tmp/wesnoth-r4-a05533f.sh b1e8439ab9e941530f07e795241a2234dabc536f5419f214e8c0e5b3f6fb2f89"
```

[Script](run_ubuntu.sh) runs `python -m unittest tests.v5.test_evaluation_design tests.test_validation_cadence tests.test_schedule tests.v5.test_selection tests.v5.test_final_nomination tests.v5.test_final_budget -v`. Standard-library unittest preserves the planned assertions; pytest remains unavailable.

| Check | Observed | Evidence |
| --- | --- | --- |
| All affected design/schedule/cadence/selection/nomination/budget checks | 30 PASS, 2.833 s | [targeted](ubuntu/targeted.log) |
| Baseline comparison restored; repeated-scenario assertion | Expected FAIL (`passed` versus `insufficient_design`) | [reverted](ubuntu/reverted.log) |
| Baseline BC artifact writer restored; scenario-gate assertion | Expected failure on missing `distinct_scenarios` | [gate reverted](ubuntu/gate_reverted.log) |
| Fixed modules restored; both assertions | 2 PASS | [restored](ubuntu/restored.log) |
| Source identity before/after probes | Identical | [before](ubuntu/source_before.sha256), [after](ubuntu/source_after.sha256), [status](ubuntu/status.log) |

## Not run / not accepted

No actual game, collection, corpus rewrite, optimizer training, full suite, convergence or strength run. Recorded collector replies prove selection wiring only. Rust/Lua semantics and N1 were not reopened. Earlier R1–R3 acceptance is reused where unchanged. R5–R10, the three native capability fixtures, teacher tactical strength and existing numerical/package failures remain open under their original gates.
