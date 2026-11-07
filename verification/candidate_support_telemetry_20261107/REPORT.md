# Lite proposal support and affected-action counts

Ubuntu `cpuServer`, 2026-11-07. [#275 prerequisite](https://github.com/t66sun/wesnothLearning/issues/275) · [B-only actor initializer](../candidate_actor_transfer_20261107/REPORT.md)

The Lite host keeps the actual proposal pool inside Lua through the existing teacher query and returns a match boolean for the teacher's unchanged intent. The collector uses its existing exact intent matching on the final candidates, then aggregates `coverage.teacher_support` by source, action kind and stage. BC teacher decisions distinguish `not_proposed`, `truncated` and `retained`. Queried DAgger decisions split retained intents into `selected` and `retained_not_selected`. Historical #227 BC job results recorded only final-set coverage, leaving their proposal stage unknown. [Historical protocol](../duel_ppo_acceptance_20261107/REPORT.md)

`coverage.candidate_use` contains the learner decision count plus offered and selected counts for `weapon_replacement` and `low_exposure_recruit`. An offered count means the decision had at least one such candidate. Selected counts use the policy's candidate index. The weapon tag marks an actual B1 slot replacement. The recruit tag marks a retained offer from B2's lower-exposure lane. It measures use of that lane, with novelty relative to v9 outside the measure. The collector removes both decision metadata fields before inference and row packing. The current gates continue to use the existing final-match and imitation metrics.

On the frozen boards, four legal fixed plans at the existing teacher query boundary produce one proposed-but-truncated attack, one retained-but-unselected attack, one unproposed recruit, and one retained selected recruit. The test checks the unchanged returned plans, the exact final matches, the aggregate stages, and offered/selected counts. Reverting the change leaves the proposal match absent and fails that assertion. The first implementation also returned extra values to direct Lua callers and two affected checks failed. The final host explicitly requests the extra results and keeps two results for existing direct callers. All 29 focused checks passed, including source/row provenance, hidden context and both existing weapon and recruit regressions. [Red](red.log) · [Initial Lua interface error](initial-interface.log) · [Final checks](green.log)

| Purpose | Shipped commit | Archive SHA256 | Fresh directory under `/home/tongshu/acceptance/` |
| --- | --- | --- | --- |
| Proposal match red | `2afcfbf862de599b03e31dad98395d67e6be6e3b` | `13c50b5711a4546d8ebcd70eeacb86de0614c4aa23a81164b5c245857982c6ce` | `candidate_support_telemetry_red_20261107` |
| Initial instrumentation | `7f327782fbfa1137d150da28ee74a8b80907a5c5c1` | `4461b274aaed32bd710b586ca17f9b9a1ea258bc8b30019eac0e82742a817426` | `candidate_support_telemetry_green_20261107` |
| Final B-only execution source | `e3213830f6fe4f37a259b491a534d61c765ee83d` | `bc8a99ded1bf50cb5c065a46718d56120dd8ea0d279497769b7cf1b15e3e697d` | `candidate_support_telemetry_final_20261107` |

Use `/home/tongshu/acceptance/candidate_support_telemetry_final_20261107/.extension/_engine_lite.so` with SHA256 `fdecbe2ee0aa10aee2d631dc14df2db713b957de6d4280f43db5804cac22a9d3`. The release build used the committed source archive and a fresh target directory. Engine `lite-0.2`, RNG `splitmix64-rejection-v1`, combat `probabilistic_combat_v6`, candidate `schema5-work-12000-v10`. Rules SHA256 `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`. This evidence covers preparation and fixture behavior. Formal collection, qualification, timing and strength evidence remain for the common experiment. [Release build](build.log) · [Imported extension identity](identity.txt)

```bash
python=/home/tongshu/venv/bin/python
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1
export CARGO_TARGET_DIR="$PWD/.cargo-build" PYO3_PYTHON="$python"
"$HOME/.cargo/bin/cargo" build --locked --offline --release -j 4 --manifest-path engine_lite/Cargo.toml
mkdir .extension
cp "$CARGO_TARGET_DIR/release/lib_engine_lite.so" .extension/_engine_lite.so
export PYTHONPATH="$PWD:$PWD/.extension:$PWD/vendor/arena"
"$python" -m unittest tests.v5.test_coverage_reasons tests.v5.test_candidate_provenance \
  tests.v5.test_candidate_weapon_retention tests.v5.test_candidate_recruit_positions \
  tests.v5.test_forecast_public_context tests.v5.test_lite_score_policy tests.v5.test_tactical_inputs -v
```
