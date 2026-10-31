# Job-log tail repair: one bounded scan per log, then plain append

Ubuntu acceptance, 2026-11-01. Clears item 8 of `docs/blockers_temp.md`: the broker reread the whole
`<run>/<format>/jobs.jsonl` on every completed game to drop an interrupted trailing line, so N records
cost O(N) bytes per game and O(N squared) cumulative on the shared dispatch path.

## What changed

- `learning/common.py:37-66` — `TAIL_CHUNK = 1 << 20` and `repair_tail(path)`: missing and empty files
  are no-ops; a file ending in `\n` is untouched after reading one byte; otherwise the file is scanned
  backwards in `TAIL_CHUNK` chunks and truncated after the last `\n`, so the cost is the unterminated
  tail plus one chunk, never the whole log. A file with no terminator at all becomes empty. Complete
  records are never removed.
- `learning/coordinator.py:68,71-78` — `broker()` keeps `repaired=set()`; `complete()` repairs a log the
  first time that broker call writes to it and every later result is a plain append. The duplicate
  `from pathlib import Path` on the old line 7 is gone.
- `learning/sample.py:8,129-132` — `collect()` calls the same helper instead of its own whole-file
  `r+b` read; the batch-scoped append handle and the `.throughput.jsonl` write are unchanged.

## Identity

| Item | Value |
| --- | --- |
| shipped source | `git archive` of branch `fix/log-tail-repair` at `ab70eb51c732f1267e71aa791a32c304b24e2f4c`, `--prefix=src/` |
| archive sha256 | `bc22222944124794988f8cc6e5a05352f5864c3ce4591bffd9a37c00cea3fba4` |
| host tree | `~/acceptance/log_tail_repair_20261101/src` on `cpuServer` (hostname `server`, no `git`) |
| platform | Ubuntu kernel `7.0.0-38-generic`, `/home/tongshu/venv/bin/python` 3.12.3, torch 2.9.1+cpu |
| provisioned input | `data/rules/1.18.8-training/{rules.json,catalog-summary.json}`, `rules.json` sha256 `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca` |
| pre-change tree | `git archive` of `HEAD~1` (`61bbf53`), extracted to `~/acceptance/log_tail_repair_20261101/revert/pre`, only `tests/test_experiment.py` and `learning/common.py` overlaid from the shipped tree |

## Commands

`C1` — affected suite, exit 0, 5.4 s:

```
cd ~/acceptance/log_tail_repair_20261101/src
PYTHONPATH=.:vendor/arena OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy /home/tongshu/venv/bin/python -m unittest tests.test_experiment -v
```

`C2` — the other suite importing the changed call site, exit 0, 0.014 s:

```
cd ~/acceptance/log_tail_repair_20261101/src
PYTHONPATH=.:vendor/arena /home/tongshu/venv/bin/python -m unittest tests.test_worker_limit -v
```

`C3` — revert check on the pre-change tree, exit 1 as required:

```
cd ~/acceptance/log_tail_repair_20261101/revert/pre
PYTHONPATH=.:vendor/arena SDL_VIDEODRIVER=dummy /home/tongshu/venv/bin/python -m unittest \
tests.test_experiment.ExperimentTests.test_collect_repairs_the_batch_log_tail \
tests.test_experiment.ExperimentTests.test_scheduler_repairs_each_log_once \
tests.test_experiment.ExperimentTests.test_tail_repair_drops_only_the_unterminated_line -v
```

`C4` — mutation: `complete()` repaired on every result instead of once per log (the four `if log not in
repaired:` / `repaired.add(log)` lines replaced by `log.parent.mkdir(...)` + `repair_tail(log)`), exit 1:

```
cd ~/acceptance/log_tail_repair_20261101/mutate/src
PYTHONPATH=.:vendor/arena /home/tongshu/venv/bin/python -m unittest \
tests.test_experiment.ExperimentTests.test_scheduler_repairs_each_log_once
```

`C5` — mutation: `repair_tail` gives up after one chunk (`end = start` replaced by `end = 0`), exit 1:

```
cd ~/acceptance/log_tail_repair_20261101/mutate2/src
PYTHONPATH=.:vendor/arena /home/tongshu/venv/bin/python -m unittest \
tests.test_experiment.ExperimentTests.test_tail_repair_drops_only_the_unterminated_line
```

`C6` — read volume of one repair, scratch script `/tmp/count_reads.py` (not committed), `pathlib.Path.open`
wrapped to count bytes returned by `read`:

```
cd ~/acceptance/log_tail_repair_20261101/src
PYTHONPATH=.:vendor/arena /home/tongshu/venv/bin/python /tmp/count_reads.py
```

## Results

| Case | Verdict | Measured |
| --- | --- | --- |
| `test_tail_repair_drops_only_the_unterminated_line` (`C1`) | PASS | complete log unchanged; `{"id":3"` tail dropped; `TAIL_CHUNK+4096`-byte tail dropped across two backward chunks; absent path not created |
| `test_scheduler_repairs_each_log_once` (`C1`) | PASS | 3 formats, 15 appended results (`duel` 6, `team2v2` 6, `ffa4` 3), exactly one repair per log, seeded `{"id":"partial"` absent, every remaining line parses with `json.loads` |
| `test_collect_repairs_the_batch_log_tail` (`C1`) | PASS | `collect([],4,log)` calls `repair_tail` once with the batch log path and leaves `{"id":1}\n` |
| 5 pre-existing `test_experiment` methods (`C1`) | PASS | unchanged behavior: resume/isolation, round robin, retry/discard, gates, run lock |
| `tests.test_experiment` (`C1`) | PASS | `Ran 8 tests`, `OK`, exit 0 |
| `tests.test_worker_limit` (`C2`) | PASS | `Ran 1 test`, `OK`, exit 0 — the `collect`/`broker` import contract still holds |
| reverted `coordinator.py`/`sample.py` (`C3`) | PASS (fails as required) | `AttributeError: module 'learning.coordinator' has no attribute 'repair_tail'`; `AttributeError: <module 'learning.sample' ...> does not have the attribute 'repair_tail'`; the helper-only byte test still passes, as expected |
| repair on every result (`C4`) | PASS (fails as required) | `AssertionError: Lists differ:` — the recorded repair list holds 15 entries instead of the 3 log paths |
| single-chunk scan (`C5`) | PASS (fails as required) | `AssertionError: b'' != b'{"id":1}\n'` |
| repair read volume (`C6`) | PASS | 64 MiB terminated log: `bytes_read=1`, 0.000129 s; 64 MiB log plus a 1 MiB unterminated tail: `bytes_read=2097153`, 0.031 s, both ending at 67,108,860 bytes. The replaced code read all 67,108,860 bytes per result |

## Limits

- No game, no collection, no training, no convergence and no strength claim: every case drives fake
  trainers or empty job lists, and `play=fake_game` returns a synthetic result after 30 ms.
- `C6` is a scratch measurement, not a committed assertion; the repository pins bytes and repair counts,
  not read volume. `C4`/`C5` are point mutations of the shipped tree, not tracked tests.
- Not covered: concurrent writers to one log (the broker is the only writer while a run is active, and no
  test exercises a second writer), a `\r\n` tail (recognized as terminated by the byte check, untested),
  and coordinator dispatch latency over a long run, which needs a planned training run.
- `data/rules/1.18.8-training` is provisioned rather than tracked, so `C2` required copying `rules.json`
  and `catalog-summary.json` (hash above) into the extracted tree; the git archive alone cannot import
  `learning.features`.
