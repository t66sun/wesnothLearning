# Recovery handoff — 2026-10-24 14:34 Asia/Shanghai

The original migration/identity/clock record is [REPORT.md](REPORT.md).
The earlier partial-progress snapshots stay unchanged. The later
`optimizer-check.ubuntu.txt` records the actual checkpoint check at **14:33:55**:

| Format | Recovered checkpoint | Current checkpoint | Optimizer steps, recovered → current | Stage / error |
| --- | ---: | ---: | --- | --- |
| duel | 212 | 219 | 2173 → 2198 | PPO / null |
| ffa4 | 88 | 91 | 1772 → 1786 | PPO / null |
| team2v2 | 50 | 51 | 695 → 698 | PPO / null |

All three have now committed real optimizer progress after recovery. The four
recollected team2v2 games completed; its old on-disk failed stage was replaced by
new successful PPO state. The wrapper is still running and no new per-format
errors.log exists. `progress-handoff.ubuntu.txt` preserves the intervening
snapshot, including original checkpoint hashes still unchanged, process group
PSS 6.67 GiB and host MemAvailable 7400 MiB at 14:30:38; swap stayed 174 MiB.

Active run remains `runs/v5_lite_resume_20261024_1420` under the isolated
`validation_memory_repair_20261024_1321` source root. The detached wrapper is
PID/PGID 200356, initial coordinator 200357. Update cutoff is **18:50:52**;
total deadline is **2026-10-24 22:30 Asia/Shanghai**. The existing independent
phase API will request final evaluation after PPO completion, without another
budget extension. That future transition and final panel are not claimed passed.
No whole acceptance or pressure suite was rerun. Schema, optimizer/RNG restoration
and actual saved progress are the minimal recovery checks; frozen parent inputs
and true BC eligibility remain preserved.

The initial operational commit is `ecf2664`. Automatic approval review rejected
GitHub publication because the operational records include server paths and
checkpoint hashes without explicit permission for that transfer. No push or PR
creation executed; publication is pending the user's separate confirmation.
This does not block the authorized server continuation.
