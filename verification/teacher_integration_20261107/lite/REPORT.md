# Lite teacher host acceptance

The frozen mixed package executes through the Lite collector and independent DAgger query path. The default remains Astra pending experiment-wide role wiring and the fixed 48-game panel. No optimizer, formal corpus collection or strength experiment ran.

## Source and procedure

- Implementation: `049ff8e1359d1b38ac44d1fe3752b5b54e9f10ef`; final existing-fixture correction: `72ac52092bcca7a1884aed926f038a2827c947a5`.
- Selected package SHA-256: `6b461de4e99303321b0119a7b88babd575c2d786500b28da4cb45d3c2bdabdb3`. No strategy bytes or parameters changed.
- Committed git archives were extracted into fresh Ubuntu directories. Each check directory contains the exact command, source commit, output and exit code. `tests/build_teacher_host.sh` builds an isolated release wheel under `.runtime/teacher_host`; the shared server environment was not replaced.
- Fixed fixtures use the synthetic 1.18.8 contract from `tests/v5/helpers.py`, plus the original selected package and maintained Astra. They are not full native-rule or six-faction strength acceptance.

## Results

Fifty distinct Python checks passed across the affected suites and subsequent focused corrections; 25 Rust tests passed. The evidence preserves all failed attempts.

| Check | Observed result |
| --- | --- |
| Frozen host, full-path modules, templates/schedule/ability fields, private planning, hidden-input invariance, memory/call-count restore, descriptor checks | 10 passed in `lite_budget_fix` |
| Actual frozen collection for all formats and nonzero independent student queries | 2 passed in `lite_deadlines` |
| Score-only/full records and truncation/query regression | 4 passed in `lite_budget_fix` |
| Teacher state reuse and four-player source regression | 4 passed in `lite_deadlines` |
| Combat probability, immunity, public hypothetical forecasts, policy memory, exact coverage reasons | 22 passed in `lite_rules_regression` |
| Collection memory and raw sequence payload | 8 passed in `lite_payload_fixture` |
| Rust combat, movement, visibility and public forecast regression | 25 passed in `lite_rust` |

The query test gives the student 40 ms and makes the teacher consume 120 ms before interruption; the student must still execute successfully. A separate single combat forecast is interrupted inside Rust probability propagation at an 80 ms budget, with unchanged referee state. These assert both independent timing and interruption within a host callback.

## Preserved failures and repairs

`lite_host` exposed a bootstrap fixture whose student was eliminated; eliminated seats correctly have no external-cut bootstrap. The fixture now explicitly survives, keeps the bootstrap assertion and compares every label's candidate count to the complete pre-query student set. The intermediate `lite_survivor` and `lite_collection` attempts expose why a full legal set may legitimately contain only `end_turn`. `lite_collection` also includes a mistyped, nonexistent test module; it was not counted as run or passed.

`lite_deadlines` exposed an expired action entering Lua before its deadline check after a restore; execution now checks the deadline before calling Lua. `lite_rules_regression` exposed an existing raw-payload fixture missing the `split_rule` field that validation has inserted since commit `be0a1ca4`; the fixture now supplies the existing contract, and the byte-for-byte assertion is unchanged. No sampling, coverage or qualification gates were relaxed.

## Review and limits

Standards and specification reviews closed the long Rust callback deadline gap, descriptor/format validation gap and ineffective student-time compensation assertion. Final read-only reviews reported no remaining findings.

Lite still has the documented rules approximations. The host projects captured ability data; it does not manufacture unsupported mechanics. The fixed fixtures do not prove final 48-game coverage, throughput, BC qualification or Lite playing strength. Experiment role activation and the bounded sampling panel remain pending.
