# Scheduled validation before holdout

The bounded Ubuntu run at source `7665583` reached all three ordinary BC gates and committed a new PPO batch on each side of the restart. Its team trainer committed seven new optimizer steps in the second PPO phase. It scheduled validation 371 seconds after that phase request, leaving about 61 seconds of its 432-second internal budget. Only one of eight team validation games completed. The comparison recorded zero complete blocks and one missing block. The trainer cleared `pending_validation` and the old driver proceeded to holdout. [Original team report](team-v000003.json)

The updated manual driver checks the comparison at each due validation version before requesting final evaluation. Each scheduled block must finish with no misses or faults. Trend estimates with few scenarios may still be inconclusive. The ordinary trainer and final-panel requirements retain their existing behavior.

Ubuntu tested `d0a2d2eb895914887ce92b6a6e069486f0e4fc84` from a git archive of its `tests/` tree in `/home/tongshu/acceptance/bounded_trend_handoff_20261104`. The archive SHA256 was `96cd01426a889e1d899018f1e0bdbcd056566790a88890b8a88f2a5a88c722b0`. The two affected suites passed all nine tests. The new check also returned false against the actual three reports in the original run. [Ubuntu output](ubuntu.log)

```sh
/home/tongshu/venv/bin/python -m unittest tests.v5.test_bounded_loop_final tests.v5.test_bounded_loop_progress -v
```
