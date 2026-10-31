# Curator accepts both checkup forms — 2026-10-31

Scope: the replay curator recognises a multiplayer sync record (`[mp_checkup]`, recorded as a
standalone dependent command) as well as the single-player inline `[checkup]`, so a multiplayer
autosave cut mid-action is classified as an earlier save instead of a divergent branch. Change in
`learning/replay_curate.py`: `CHECKUPS = {'checkup', 'mp_checkup'}` (line 45) replaces the literal
`'checkup'` in the intent digest (line 236) and in the empty-trailing-sync test (line 237). The
assertion is `tests/test_replay_curate.py::ReplayCurateTests::
test_incomplete_last_mp_checkup_is_a_prefix_but_different_rolls_are_not`.

Activated items: none. No `docs/TEST.md` item was open for this curator behavior; the blocker this
closes lived in `docs/blockers_temp.md` as item 1.

Excluded, with reasons:

- No maintained documentation change. `replay_curate` is described by its user-visible fields
  (curation over local saves and lobby archives, controller hand-overs), not by which sync tag it
  strips, and `grep -n "checkup"` over `README.md`, `docs/architecture*.md`,
  `docs/instructions*.md`, `docs/TEST*.md` and `docs/README_zh.md` returns nothing before or after
  the change.
- No corpus regeneration. `data/humanData_curated/` and `data/replays_curated/` cannot change: the
  full-history digest still includes the sync payload, so `history_sha256`, `commands`,
  `semantic_commands`, selection and every output column are untouched. Proven below by comparing
  pre-change and post-change output over the 1,076-game `tmp/regen_src` corpus.

## Identity

- Source under test: `git archive` of commit `388ce35` (`Accept the multiplayer checkup form in
  replay curation`), archive sha256 `125ec97d6f12eb680fd760a8d9849e7907ed1eed28c8a88494d30061cb75adb7`.
  The suite is pure Python and needs no extension build, catalog, model or seed.
- Windows reference: `Windows-11-10.0.26200-SP0`, Python 3.12.14 (MSC v.1944 64 bit), `.venv`.
- Ubuntu acceptance: `Linux 7.0.0-38-generic x86_64`, Python 3.12.3 (Aug 31 2026, GCC 13.3.0),
  `/home/tongshu/venv/bin/python`, extracted at
  `/home/tongshu/myDev/wesnothLearning/curator_mp_20261031` (fresh extraction, no data symlinks
  needed).
- Corpus for the invariance run: `tmp/regen_src` (1,076 games) on Windows; scratch trees, not
  evidence.

## Commands

Ubuntu acceptance, from the extraction directory:

```bash
/home/tongshu/venv/bin/python -m unittest tests.test_replay_curate -v
```

Windows reference, from the repository root:

```bash
.venv/Scripts/python.exe -m unittest tests.test_replay_curate -v
```

Reverted-module check (Windows): the test file from the fix commit placed beside the pre-change
module (`54f50f4`) in a scratch worktree, then

```bash
.venv/Scripts/python.exe -m unittest tests.test_replay_curate.ReplayCurateTests.\
test_incomplete_last_mp_checkup_is_a_prefix_but_different_rolls_are_not -v
```

Invariance, pre-change and post-change, same source and origin:

```bash
.venv/Scripts/python.exe learning/replay_curate.py --source tmp/regen_src --output "$TEMP/curator_base_out" --origin regen   # module from 54f50f4
.venv/Scripts/python.exe learning/replay_curate.py --source tmp/regen_src --output "$TEMP/curator_mp_out"   --origin regen   # module from 388ce35
cmp "$TEMP/curator_base_out/inventory.jsonl" "$TEMP/curator_mp_out/inventory.jsonl"
cmp "$TEMP/curator_base_out/games.jsonl"     "$TEMP/curator_mp_out/games.jsonl"
```

## Results

| Case | Verdict | Assertion / counts | Artifact |
|---|---|---|---|
| Reverted module, new test | FAIL (expected) | `_partial_last` False at `tests/test_replay_curate.py:100`; the fixture's autosave stays a third selected family with no `earlier_save` | `unittest_windows_reverted.txt` |
| Windows reference, whole module | PASS | `Ran 12 tests in 0.136s`, `OK`, exit 0, new test name present | `unittest_windows.txt` |
| Ubuntu acceptance, whole module | PASS | `Ran 12 tests in 0.016s`, `OK`, exit 0, new test name present | `unittest_ubuntu.txt` |
| Pre-change vs post-change curation, `tmp/regen_src` | PASS | `cmp` exit 0 for `inventory.jsonl` and `games.jsonl`; `summary.json` differs only in its recorded `output` path | in-session, see Reuse |
| Re-curation against the older `tmp/regen_out` reference | PASS modulo line endings | 1,076 rows carry identical parsed content in both files; raw `cmp` exits 1 at byte 2017 because the reference was written before the generated-text LF rule and holds 1,076 CRLF line ends. After normalising the reference to LF both files are byte-identical (2,185,889 bytes each) | in-session, see Reuse |
| Line-count rule | PASS | only the two grandfathered files exceed 1,000 lines (`tests/smoke_training_lite_8worker.py` 1050, `tests/v5/test_pipeline_contract.py` 1748) | in-session |
| `grep -n "checkup"` over `README.md`, `docs/architecture*.md`, `docs/instructions*.md`, `docs/TEST*.md`, `docs/README_zh.md` | PASS (no match) | no maintained doc names the tag, so no doc sentence described the old single-tag behavior | — |

The new test asserts five things after the fix, and the reverted module breaks the first: the
autosave's `_partial_last` is True, `selected_replays` is 2 (not 3), `source_statuses['earlier_save']`
is 1, `branched_families` is 1, and the autosave's inventory note carries
`last_command_checkup_incomplete`. The existing inline-`checkup` test is unchanged and still passes,
so both forms are covered by one mechanism.

## Reuse

The curation-invariance result replaces a regenerated corpus for this change: `inventory.jsonl` and
`games.jsonl` are byte-identical between the pre-change and post-change curator over all 1,076
games, so no tracked curated output needs rewriting and the earlier curate acceptance still stands.
The `tmp/regen_out` comparison is recorded because the raw file pair differs by line endings only;
that difference predates this change and belongs to the LF-on-every-platform behavior, not to the
checkup tags. `tmp/regen_src` and `tmp/regen_out` are scratch trees and may disappear; the
pre-change/post-change comparison in this report is the reusable statement.

## Failure

None. No silent skip, no bypassed gate, no retry. `unittest_windows_reverted.txt` is a deliberate
red run: it is the proof that the new assertion fails when the `mp_checkup` handling is removed.

## Resources

Windows module run 0.14 s; Ubuntu module run 0.02 s; each curation pass over 1,076 games about 52 s
single-process. The remote extraction directory is scratch and can be deleted.

## Gate

Ready: the curator blocker is closed and `fix/curator-mp-checkup` carries the code, this evidence and
the blocker-note update. No training or collection was authorized or performed.

## Limits

- No staged save ends on an empty `[mp_checkup][/mp_checkup]` block: a scan of `tmp/curate_src`,
  `tmp/regen_src` and `data/humanData` found 3,192 `mp_checkup` blocks in exactly two games (four
  file copies) and none empty. The shape the new test pins is therefore constructed, not observed;
  a save that omits the sync command entirely was already covered by plain prefix matching, and the
  two affected games are unaffected by the change because they have no sibling saves.
- The corpus-invariance comparison ran on Windows only. Ubuntu accepted the unit suite, not a
  curation pass, because curation reads the same pure-Python path and no platform-dependent output
  is involved beyond the already-tested LF rule.
- The generated curator README keeps its Chinese sentence naming `checkup` alone; rewording it would
  change curated README bytes and force a corpus rewrite, which this change deliberately avoids.
- Nothing here says anything about BC quality, convergence or playing strength.
