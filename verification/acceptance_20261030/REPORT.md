# Acceptance sweep — 2026-10-30

Test items from `docs/TEST.md` run in document order on the Windows reference host
(10.0.26200, x64, Python 3.12.14, source commit `a6b24ca`, working tree clean). Ubuntu
acceptance did not run: this host has no native Wesnoth install (`.runtime/` absent) and no
Ubuntu 24.04 machine, so every item that needs either is NOT RUN rather than passed.

## Item decisions

| Item | Decision | Evidence |
| --- | --- | --- |
| D1 optional external inference | deleted as obsolete | no owner exists: no `serve` command, no module, no doc outside its own item and one `architecture.md` gap line; delivery is the in-engine Lua add-on (`learning/export.py`, `learning/collector.lua`), and `learning/native_transport.py` is a training/eval session transport, not an inference protocol |
| N1 native terminal capture | NOT RUN | requires native 1.18.8; `.runtime/` absent and no game installed |
| L1 reduced full-loop run | NOT RUN | requires the runtime above; also not authorized by the operator |
| R3 adapted teacher strength | NOT RUN | requires the same runtime plus a matched schedule |
| PKG1 Ubuntu bundle | static half PASS, Ubuntu half NOT RUN | commands below |
| C1 lobby-archive curation | determinism half PASS, Ubuntu half NOT RUN | commands below |

## PKG1 — static half

| Command | Exit | Result |
| --- | --- | --- |
| `python -m learning bundle --output tmp/bundle_acceptance/WesnothLearning-training.tar.gz --created-at 2026-10-30T00:00:00Z` | 0 | 308 files, 244,807,237 B, sha256 `86a47d434bf8fdc44403f0e868f5366e8e2cdfcfabda4948acc451067c56e74a`, `source.commit a6b24ca`, `dirty false`, rules `1.18.8-training` 587 units / 438 terrains, teacher `wesnoth_default_rca` |
| `python -m learning verify-bundle <archive>` | 0 | `ok true`, 308 files, 40 directories, same sha256 |
| `python -m learning verify-bundle <archive with one byte flipped>` | 0 | `ok false`, first errors `missing required path: …/catalog-summary.json`, `…/catalog.json`, `…/coverage.json` |
| member scan of the archive | — | 348 members under `WesnothLearning/`; no `.git`, `.venv`, `__pycache__`, `runs`, `verification`, `delivery`, `data/rules/1.18.8`, `data/references`; the 54 `data/humanData_curated` members are deliberate (`learning/bundle.py:39` `DATA_PATHS`, BC labels), while raw `data/humanData` is excluded |

Not run: extraction on a clean Ubuntu 24.04 machine, `./setup.sh --preflight` on the intact and
tampered copies, `./setup.sh --device cpu`, `./train.sh --help`, the refusal without
`.runtime/environment.sh`, and the before/after tree diff.

## C1 — determinism half

| Command | Exit | Result |
| --- | --- | --- |
| `python -m unittest tests.test_replay_curate -v` | 0 | `Ran 10 tests … OK` |
| `python tmp/regen_corpus.py` (extract the 1,076 recorded sources from the four monthly tars, curate into `tmp/regen_out`) | 0 | 1,076 staged files, 0 missing members, 1,076 selected / 1,076 families, formats duel 724 / team2v2 352, `inventory.jsonl` byte-identical (2,186,965 B both sides) |
| per-file comparison against `data/replays_curated/` | 0 | 1,076 / 1,076 regenerated payloads byte-identical; 0 `curated_sha256` mismatches; 0 `payload_sha256` mismatches; 359,526 decision intents; 502,647 semantic commands; every row `status=selected` |

Hash semantics confirmed on this run: `curated_sha256` is the digest of the emitted `.gz`, and
`payload_sha256` is the digest of the decompressed payload, so the two must be checked against
different byte streams.

Not run: the same procedure on Ubuntu; replay legality, roll reproduction and observation
formation under native 1.18.8; any BC import of the corpus.

## Limits

No game was launched, no replay was replayed, no training, collection or tuning happened, and no
Ubuntu acceptance exists. PKG1 and C1 therefore stay open in `docs/TEST.md`; the results above are
Windows reference evidence only, and they authorize no convergence, strength or delivery claim.
