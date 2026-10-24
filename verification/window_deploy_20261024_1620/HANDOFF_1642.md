# Deployment handoff — 2026-10-24 16:42 Asia/Shanghai

The detailed selection, deployment and immutable source lineage remain in
[REPORT.md](REPORT.md). The later `progress-handoff.ubuntu.txt` snapshot at
**16:41:14** confirms actual saved PPO progress in all three formats:

| Format | Selected start | Latest observed | Optimizer steps |
| --- | ---: | ---: | --- |
| duel | v100 | v105 | 1780 → 1795 |
| ffa4 | v100 | v103 | 1820 → 1828 |
| team2v2 | v60 | v61 | 746 → 756 |

All stage=PPO, error=null, with new complete eligible rollouts. The active
wrapper PID/PGID remains **202233** in
`/home/tongshu/myDev/wesnothLearning/validation_window_fix_20261024_1630/runs/v5_lite_windowfix_20261024_1630`.
Group PSS 6.94 GiB; host MemAvailable 7042 MiB, swap 174 MiB. The parent manifest
and stopped latest-checkpoint hashes are unchanged. The prior process group
was confirmed stopped; the replacement runs independently of SSH.

Accepted repaired controller SHA is frozen in the active manifest. This is a
real deployment, not just a merged local fix. Reward coefficients remain at
version 0 at this observation; subsequent automatic adjustments must use the
existing versioned boundary mechanism. No manual tuning or eligibility change.

PPO update cutoff: **2026-10-24 20:05:52**. Total deadline:
**2026-10-25 00:00 Asia/Shanghai**. The wrapper will request final evaluation
once PPO completes, using that existing remaining budget. That future phase and
final-panel completion are not yet claimed. Do not start a duplicate or resume
one of the preserved parent experiments.
