# Unified acceptance of PPO retention and efficiency research

Research issues [#225](https://github.com/t66sun/wesnothLearning/issues/225) and
[#226](https://github.com/t66sun/wesnothLearning/issues/226) meet their diagnostic
acceptance criteria. Their proposed production changes remain unimplemented.

## Retention

[PR #237](https://github.com/t66sun/wesnothLearning/pull/237) at
`74dd5c7e2e372ee31a42cc67b38ae3274b7861a0` contains the research, raw results and
architecture clarification. Its probe and tests are byte-identical to the
Ubuntu-executed source `7432fae8be520c96fe04b474bd1bf5627307dfab`.

Three analytical loss tests and six existing control-source tests pass. Both
format probes finish; all four source/exclusion comparisons match the original
logs, weights remain unchanged and the anchor receives no gradients. The report
defines a qualified self-policy origin, legal state/history boundary, fixed
anchor identity, concrete loss and independent behavior/strength criteria.
[Commands, input identities, results and limits](../bc_retention_20261106/REPORT.md).

## Efficiency

[PR #238](https://github.com/t66sun/wesnothLearning/pull/238), exact head
`f2ea02a4ec4492ef16545de593b11c72c8569083`, was independently sent as a Git archive
and extracted into
`/home/tongshu/acceptance/ppo_efficiency_review_20261106_f2ea02a/source`.

From that fresh source, with the existing frozen inputs and environment specified
in its report, the independent checks were:

```bash
python=/home/tongshu/venv/bin/python
run=/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/runs/formal_30h_scratch
scripts=verification/ppo_efficiency_20261106
"$python" -m unittest discover -s "$scripts" -p test_diagnostic.py -v
"$python" "$scripts/census.py" "$run" ../census_recomputed.json
cmp ../census_recomputed.json "$scripts/census.json"
sha256sum ../census_recomputed.json
(cd "$scripts" && sha256sum -c SHA256SUMS)
```

Both accounting tests pass; the recomputed census is byte-identical, SHA-256
`4aa1bdb3bbe18b0c7b0e85a008f12998c8ca7e9d2809458c456639b6d35a9f33`.
All 14 recorded artifact hashes verify. Separate arithmetic checks reproduce
the six preparation/epoch table rows, validate step/visit sum identities and
check all six before/after policy replay error bounds and stop-KL reconstruction
errors against the stated limits. [Independent review output](efficiency_review.log).
The original twelve timing passes were not repeated: the measured code is
unchanged, and this review does not introduce a new timing claim.

## Scope and decision

Both archived source trees satisfy the source-size rule except the unchanged,
documented grandfathered files: `tests/v5/test_pipeline_contract.py` (1504 lines)
and `tests/smoke_training_lite_8worker.py` (1050). The changed diagnostic source
files remain below 1000 lines. Neither PR modifies production `learning/`,
`lua/`, `engine_lite/`, historical evidence, captured inputs, or `AGENTS.md`.

The accepted result is a fixed-BC retention proposal plus reproducible cost and
update accounting, not repaired training. The next loss change can compare
frozen BC probabilities with existing hard-action replay while keeping control
isolation. A separate narrow data-path change can eliminate the discarded
rollout pre-read without truncating full PPO trajectories. Filtering rehearsal
sources earlier changes reader quotas and needs its own explicit data contract;
neither a larger KL threshold nor a blanket DAgger removal follows from this work.

No new games, collection, formal training or strength claims were added. The
official 30-turn objective implementation remains #235; training comparisons
remain a later, explicitly authorized step under #227.
