# Workflow simplification on Ubuntu

Three changes remove work from the training and evaluation path. The BC opening probe and its action diagnostics are retired. A periodic promotion loads the same 12-block Astra panel and plays the champion only if the result could update a method or overall record. Historical `combat_choice` schedules require the source pinned by #328. The three changes remove 140 net lines from `learning/`, `engine_lite/` and `lua/`.

| Removed work | Previous trigger | Current behavior |
| --- | --- | --- |
| Opening diagnostics | Four extra five-round games per qualified BC validation, plus unused per-action records | Ordinary validation retains coverage, reward metrics and policy memory |
| Ineligible champion panels | Every periodic promotion with an existing champion | Keep the matched panel for eligible contenders, saving 24 duel, 48 FFA or 96 team games per ineligible promotion |
| Combat replacement | Explicit selectors from the retired #328 design | Historical schedules are rejected by the current worker with a frozen-source error |

## Storage

Windows removed 879,771,496 file bytes (839 MiB). This includes 5,340 scratch files, four retired internal policy/support exports, and two expanded copies of old evidence. Each of the 69 files in those two copies matched its retained tar member by SHA-256.

On cpuServer the removed paths occupied 21,365,404 KiB (20.38 GiB) before deletion.

| Category | Paths | Allocated KiB |
| --- | ---: | ---: |
| Cargo build cache | 21 | 10,239,740 |
| Native build cache | 1 | 200,048 |
| Retired #322 mixed-arm intermediate shards and exports | 6 | 9,721,112 |
| Byte-matched old source extractions with tarballs retained | 4 | 753,272 |
| Revert test source copies | 2 | 427,676 |
| Scratch | 1 | 23,556 |

The #322 mixed-arm data and intermediate policies were retired. Its wall endpoints and raw score archive remain available. A resumed mixed-arm training cell would require the removed data. The three pure-Astra corpora used by #334, the #336 checkpoints, canonical evidence, rules, Astra package and native runtime remain available.

For the final source commit, a full Git archive measured 224,296,960 bytes. The archive used for this acceptance measured 9,635,840 bytes (95.7% smaller) by selecting the source, tests, and tracked inputs. The test extraction links to the existing production rule package and legacy rule inputs. Tests that consume archived fixtures can include their specific verification paths.

## Ubuntu evidence

`cpuServer` used `/home/tongshu/venv/bin/python`, the installed native Wesnoth 1.18.8 executable, and the production rules SHA-256 `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`. The baseline and new embedded Lua hosts were built with `cargo build --offline --locked --release --manifest-path engine_lite/Cargo.toml` in separate target directories. The extracted trees used the existing historical `1.18.8` and `1.18.8-training` catalogs for tests that request those identities.

| Source | Commit | Source tar SHA-256 |
| --- | --- | --- |
| Baseline | `9f4d7fc34ffc587f8387c536cc3d345f32f33d6c` | `ec878f4acdf116a48c695c654b5995b923cf2cf99015915a6e7adbc9d8e6a9fc` |
| Opening probe removal | `66054bf9ff8c45a9850afadeb77ec79f3e3c6645` | `25dd614cd34a9944b705a83cd1d8b8b6a915254571302fdedff99be97099065a` |
| All three runtime changes | `cfad8c0022193323f91c03a08d560626f4cd221f` | `74cb218fa6a49adb234a6bfc13b1dcaf3b9c07b51e37955fd787daa1b8676e73` |

Extension SHA-256 was `56dd77140411db987377d6de4ffbf562da4d0e5c76bc16d34780da67e60e5ae4` on the baseline and `3c3549abac29b940c7a32615432f35babfbd8c8e8f7d87fd8bbc442ef2265a51` after opening-probe removal. The final tree uses that same rebuilt extension, with byte-identical engine sources. The merged runtime tree was compared against the final tested commit.

The focused run passed 60 tests in 14.932 seconds. The revised assertions failed on the corresponding old behavior. The broader baseline and final runs reported the same five errors and two failures. The affected legacy fixtures cover the task identity in schedule and reward-reference stubs, an external-cut bootstrap assertion, and legacy sequence payload identity. These results establish the workflow changes and preserve the recorded limits on strength and all-format readiness. [Commands and test output](ubuntu-results.txt)

On cpuServer the final tested source and Lite module are in `/home/tongshu/acceptance/workflow-slim-20261115-6iLl4s/source` and `/home/tongshu/acceptance/workflow-slim-20261115-6iLl4s/.extension`. The module stays outside the shared virtual environment.
