# Server release — 2026-10-31

The Ubuntu acceptance host (`cpuServer`, 192.168.122.118) reported 14 GB of 15 GB memory in use
with no job of this repository running. The holders were orphaned children of runs that had ended
days earlier, not work in progress.

## What was running

| Family | Processes | Parent | Age | Resident |
| --- | --- | --- | --- | --- |
| `multiprocessing.spawn` workers | 32 | none (ppid 1) | 49–142 h | 13,891,336 KB |
| `Xvfb :99`–`:104` | 6 | none (ppid 1) | 10.8 days | ~750 KB each |

Every worker ran `/home/tongshu/venv/bin/python -c "from multiprocessing.spawn import spawn_main; …"`,
the child form of a pool that no longer has a parent, and their working directory was
`~/myDev/wesnothLearning/l1_refactor_20261025/source` — removed for two thirds of them, still present
for the rest. `pgrep -af "learning[.]train|learning[.]collect"` returned nothing, so no driver,
scheduler or agent was attached to either family; six days of accumulated CPU time across the group
was 1–2 minutes per worker, i.e. they were idle, not progressing.

The directory is the source archive named by `verification/refactor_acceptance_20261025/REPORT.md:69`
(`master` at `34cbe94`), whose log tails end in
`Experiment: stage_complete` and `resource_tracker: There appear to be 11 leaked semaphore objects`,
the abort that stranded the pool. The `Xvfb` pair came from `xvfb-run` wrappers of the same era.

## Action

`pkill -u tongshu -f "multiprocessing[-]fork"` and `pkill -u tongshu -x Xvfb`; then
`l1_refactor_20261025/source` (7.0 MB) and its empty `runs/` (4 KB) were deleted. Kept: `source.tar`
(6,318,080 B), the launch and status logs, and `status_check.sh` — the report above cites that
directory as the run's source identity, so the bytes stay available while the extracted tree does
not.

Two stale `X` locks, `/tmp/.X1024-lock` and `/tmp/.X1025-lock`, belong to the active gdm session's
`Xwayland :1024` (owner `gdm`, started 2026-10-28) and were left alone.

## Result

| Reading | Before | After |
| --- | --- | --- |
| Memory (15 GB total) | 14 GB used, 1 GB available | 0–1 GB used, 14 GB available |
| Processes of this account | 32 workers + 6 `Xvfbs` + session daemons | session daemons only |
| `/home` disk | 179 GB used, 42 GB free | 25 GB used, 197 GB free |

## Limits

This is an environment release, not an acceptance run: no game was launched, no replay replayed, no
training started. It removes the capacity blocker recorded for L1/R3/N1 — `~/myDev/wesnothLearning/
WesnothLearning/.runtime/build/wesnoth` is `Battle for Wesnoth v1.18.8 x86_64` — but those items stay
NOT RUN in `docs/TEST.md` until someone starts them. The preceding disk sweep (152 GB of run state,
caches and duplicate trees) is reported in `verification/acceptance_20261030/REPORT.md`.
