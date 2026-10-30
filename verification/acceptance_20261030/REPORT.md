# Acceptance sweep — 2026-10-30/31

Every item in `docs/TEST.md` was taken in document order on the Windows reference host
(10.0.26200, x64, Python 3.12.14, source commit `a6b24ca`, working tree clean). C1 then ran on
Ubuntu 24.04.5 LTS (8 cores, Python 3.12.3, zlib 1.3) after the operator opened the server. The
operator also dropped the training-bundle item (`PKG1`) and the clean-Ubuntu environment work that
belonged to it, so no bundle acceptance exists and none is planned.

## Item decisions

| Item | Decision | Reason / evidence |
| --- | --- | --- |
| D1 optional external inference | deleted as obsolete | no owner exists: no `serve` command, no module, no doc outside its own item and one `architecture.md` gap line; delivery is the in-engine Lua add-on (`learning/export.py`, `learning/collector.lua`), and `learning/native_transport.py` is a training/eval session transport, not an inference protocol |
| N1 native terminal capture | NOT RUN | requires native 1.18.8; `.runtime/` absent, no game installed, and no collection authorization |
| L1 reduced full-loop run | NOT RUN | same runtime requirement, plus no training authorization |
| R3 adapted teacher strength | NOT RUN | same runtime requirement plus a matched schedule |
| PKG1 Ubuntu bundle | deleted, operator decision 2026-10-31 | the operator stated the bundle no longer needs attention; the feature stays implemented and its static verification stays recorded below as reference only |
| C1 lobby-archive curation | PASS, archived, item deleted | Windows reference run plus the Ubuntu run below |

## PKG1 — reference-only record

| Command | Exit | Result |
| --- | --- | --- |
| `python -m learning bundle --output tmp/bundle_acceptance/WesnothLearning-training.tar.gz --created-at 2026-10-30T00:00:00Z` | 0 | 308 files, 244,807,237 B, sha256 `86a47d434bf8fdc44403f0e868f5366e8e2cdfcfabda4948acc451067c56e74a`, `source.commit a6b24ca`, `dirty false`, rules `1.18.8-training` 587 units / 438 terrains, teacher `wesnoth_default_rca` |
| `python -m learning verify-bundle <archive>` | 0 | `ok true`, 308 files, 40 directories, same sha256 |
| `python -m learning verify-bundle <archive with one byte flipped>` | 0 | `ok false`, first errors `missing required path: …/catalog-summary.json`, `…/catalog.json`, `…/coverage.json` |
| member scan of the archive | — | 348 members under `WesnothLearning/`; no `.git`, `.venv`, `__pycache__`, `runs`, `verification`, `delivery`, `data/rules/1.18.8`, `data/references`; the 54 `data/humanData_curated` members are deliberate (`learning/bundle.py:39` `DATA_PATHS`, BC labels), while raw `data/humanData` is excluded |

On Ubuntu the same archive gave `./setup.sh --preflight` exit 0 (`preflight: bundle checksums
verified`, `ok (10 required paths present)`) with the tree fingerprint
`98da9337e049ece5c583e811ab4382701660b2a8fc938c8e1509fbeda7e7c548` unchanged (308 files, 40
directories), exit 1 on the tampered copy (`learning/adapters.py: FAILED`), `./train.sh --help`
exit 0, and `./train.sh` without `.runtime/environment.sh` exit 1 with
`train.sh: .runtime/environment.sh is missing; run ./setup.sh first`. The full
`./setup.sh --device cpu --skip-system-deps --jobs 2` reached `identity: rules
source_hash=c08f8a08d6fb802d units=587 terrains=438 engine=lite-0.2` and was stopped by operator
decision during the Wesnoth build. These runs are reference results; PKG1 is dropped and nothing
here claims installed-bundle acceptance.

## C1 — accepted

Defects found by the Ubuntu run, both fixed before acceptance:

1. Every text output was written without an explicit newline, so the Windows reference emitted
   CRLF (`inventory.jsonl` 2,186,965 B) while Ubuntu emitted LF (2,185,889 B).
   `learning/replay_curate.py` now passes `newline='\n'` to its four text writers and
   `lineterminator='\n'` to the CSV writer.
2. `curated_sha256` follows the gzip container, whose bytes depend on the zlib build (1.3.2 on the
   Windows reference, 1.3 on Ubuntu), so cross-platform regeneration legitimately disagrees on that
   field alone while every payload matches.

The new assertion `tests/test_replay_curate.py::ReplayCurateTests.test_generated_text_outputs_use_lf_on_every_platform`
fails (`FAILED (failures=1)`) when those newline arguments are removed on Windows and passes with
them; the archive-layout and provenance assertions fail when their guards are reverted, as recorded
in `verification/replay_archive_20261029/REPORT.md` and
`verification/replay_corpus_audit_20261030/REPORT.md`.

| Host | Command | Exit | Result |
| --- | --- | --- | --- |
| Windows reference | `python -m unittest tests.test_replay_curate -v` | 0 | `Ran 11 tests … OK` |
| Windows reference | `python tmp/regen_corpus.py` (1,076 recorded sources extracted from the four monthly tars, curated into `tmp/regen_out`) | 0 | 1,076 staged, 0 missing, 1,076 selected / 1,076 families, duel 724 / team2v2 352, `inventory.jsonl` byte-identical (2,185,889 B both sides), 0 payload and 0 container digest mismatches, 359,526 decision intents |
| Ubuntu 24.04 | `python3 -m unittest tests.test_replay_curate -v` on the same sources (`replay_curate.py` sha256 `70f241680cba1121166dbbc4b289f4ac7da902ad3d430ad2dd7a473ee9000d3f`, test file `e59ba7c01515fadc881084346755e8032a3016fc0283d93ae53afea19a9fe1d8`) | 0 | `Ran 11 tests … OK` |
| Ubuntu 24.04 | `python3 verification/acceptance_20261030/regen_corpus.py $root/c1/src $root/c1/stage $root/c1/out` | 0 | `recorded sources: 1076`, `staged: 1076 missing: 0`, `fields differing besides curated_sha256: none`, `decision intents: 359526`, `shipped container mismatches: 0`, `regenerated payload mismatches: 0`, `selected_formats {'team2v2': 352, 'duel': 724}`, `RESULT: PASS` |

Hash semantics: `curated_sha256` is the digest of the emitted `.gz` bytes, `payload_sha256` the
digest of its decompressed payload. The shipped corpus is verified field by field against the
regeneration except `curated_sha256`, which is verified against the shipped file itself
(1,076 / 1,076 in both directions).

## Limits

No game was launched, no replay was replayed under native 1.18.8, no training or collection
happened, and no BC import of the corpus was attempted: `learning/human.py:compatibility` still
stops every curated game at `missing_native_initial_state` (the lobby archive carries no
`[replay_start]`) and the corpus mixes nine engine versions. Nothing here claims convergence,
playing strength or delivery readiness. The Ubuntu host kept no artifacts: the acceptance directory
and the four replay tars (8.1 GB) were removed after the run.
