## Documentation and training

Read `docs/architecture.md` before architecture, parameter or status changes; maintain it and report decision conflicts. Read `docs/instructions.md` before training operations or tuning. Keep `docs/` limited to these and `TEST.md`.

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
