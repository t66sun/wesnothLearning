# Working rules

This repository trains a Wesnoth 1.18.8 agent: a Rust rule core (`engine_lite/`), a Python coordinator (`learning/`), shared Lua legality (`lua/`), captured inputs (`data/`), dated evidence (`verification/`), and run/delivery output (`runs/`, `delivery/`). Rules below bind every agent and human change.

## Hard rules

1. **No source file exceeds 1000 lines.** Applies to tracked `.py`, `.rs`, `.lua` and `.sh`. `git ls-files '*.py' '*.rs' '*.lua' '*.sh' | xargs wc -l | awk '$1>1000 && $2!="total"'` must print nothing. Split approaching files along their existing seams into modules of the owning package; never raise the limit. Grandfathered, and must shrink before their next substantive change: `tests/v5/test_pipeline_contract.py` (1804 lines) and `tests/smoke_training_lite_8worker.py` (1050 lines).

2. **One pull request changes one behavior.** About 1000 implementation lines, excluding tests, fixtures, documentation and byte-identical moves. It touches only the files that behavior owns, keeps restructuring separate from tuning, and states the changed behavior in the title and each commit message.

3. **No AI attribution.** Commits, pull requests, issues, review comments and generated artifacts carry the user's authorship only: no agent names, no co-author trailers, no "generated with" lines.

4. **Every behavior change carries an assertion that fails when reverted.** No silent skips, no lowered or bypassed gates, no retries that hide flakiness, no weakened evidence. A check that cannot run is reported as not run, never as passed.

5. **Never claim more acceptance than observed.** Minimal checks prove wiring only; Ubuntu is the acceptance environment and Windows the reference. Convergence, strength and full native semantics need formal training evidence. A plan or a TEST.md item never authorizes collection or training.

6. **Referee truth never reaches a policy.** Snapshots, unseen units, unexplored terrain, RNG draws and opponent weights stay inside the referee, replay audit, reward computation and differential tests; observations, candidates, teacher queries and predictions see only legal visible context.

7. **Frozen inputs and recorded evidence are read-only.** `data/`, dated `verification/` reports, run manifests and their hashes are never hand-edited, re-sorted or retro-fitted; new evidence goes to a new dated directory. Generated output (`engine_lite/target/`, `*.egg-info`, `__pycache__`, `tmp/`) is never edited.

8. **Server work happens only on explicit instruction.** Make local changes first; collection and training start only when asked.

## Layout

```text
README.md            repository entry (English); Chinese mirror docs/README_zh.md
AGENTS.md            these working rules (English only)
docs/                maintained bilingual docs: architecture, instructions, TEST, THIRD_PARTY
engine_lite/         Rust extension, native capture/freeze/audit, direct Lua host
learning/            coordinator, adapters, model, sequences, training, rewards, evaluation, export
lua/                 native deployment plus the observation/candidates/memory/reward shared by both engines
tests/               one suite per behavior family; shared fixtures in tests/v5/helpers.py
benchmarks/          engine benchmark contracts
vendor/arena/        vendored WesnothArena native v2 SDK
data/                captured inputs, provisioned rather than authored
  rules/             1.18.8-training (default, 587 units) and 1.18.8 (historical, frozen maps)
  datasets/          human and teacher data, sequence indexes
  humanData/         raw replay dumps pulled from the game install
  humanData_curated/ curated 1.18.8 replays used for BC
  opponents/         frozen reference opponent packages
  references/        third-party source excerpts, untracked
runs/<run>/          per-run manifests, per-format training state and control events
verification/        dated evidence at fixed paths; excluded from the source package
delivery/            explicitly exported model packages and manifests
tmp/                 scratch space; nothing here is evidence
```

`setup.sh` provisions the virtual environment and extension, `run.sh` forwards to `python -m learning`. `delivery/` and `verification/` keep historical runs as they were; `data/` is the only place captured inputs go, and new code lands in the module that owns the behavior rather than in a new top-level directory.

## Documentation

Maintained docs live in `docs/`; the repository root keeps only `README.md`, whose Chinese mirror is `docs/README_zh.md`. Module docs under `benchmarks/`, `engine_lite/` and `learning/` stay beside their code. Mirrors use the `_zh` suffix.

Not maintained docs: `vendor/`, `data/references/`, `verification/`, `data/rules/`, `data/humanData*`, `delivery/`, `runs/`, `tmp/`.

Read `docs/architecture.md` before architecture, parameter or status changes; maintain it and report decision conflicts. Read `docs/instructions.md` before training operations or tuning.

Ubuntu is the acceptance environment; Windows is reference. Run affected minimal checks, reuse valid evidence; collect/train only when asked. Minimal acceptance never bypasses BC/PPO gates or proves convergence or strength.

## TEST.md

Keep implemented changes awaiting acceptance, ordered toward training. Each item states status/reason, minimal Ubuntu inputs/procedure, pass criteria, evidence path and training blocker. Identify unwritten tests; share fixtures/runs.

After acceptance, archive commands, results, source/rule identities and limits in dated `verification/` reports; update architecture status/evidence and delete the entire item. Preserve original dates/hashes. Reopen only affected behavior; when empty, state no pending acceptance. Plans grant no execution authorization.

## CodeGraph

When `.codegraph/` exists, use `codegraph_explore` or `codegraph explore` before grep/code reads to locate symbols and trace callers; otherwise skip.

## Git workflow

Never commit directly to `master`; make every change, however small, on a branch. Each subagent works on its own branch and, when its task is done, opens a pull request with `gh pr create --repo t66sun/wesnothLearning --body-file`.

Make sure that every change that actually matters is committed. Every commit needs to be carried along with specific description of what is changed.

At the end of each phase the main agent collects the open pull requests, reviews and verifies them one at a time, merges each into `master`, then pushes `master` to GitHub.

## Issue tracker

Requests/specs: GitHub Issues, `t66sun/wesnothLearning`. Use `gh ... --repo t66sun/wesnothLearning` or `gh api repos/t66sun/wesnothLearning/...`; fetch comments/labels and pass multiline bodies via `--body-file`. Publishing means an issue, not a PR.

Triage labels: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`.

Keep one `wayfinder:map` with Notes, Decisions-so-far, Fog. Link children natively or by task list plus `Part of #N`; label `wayfinder:{research,prototype,grilling,task}`. Record dependencies natively or `Blocked by: #N`. Assign the first open, unassigned, unblocked child in map order to the driving developer. On resolution, comment, close, and link the finding in the map's Decisions-so-far.
