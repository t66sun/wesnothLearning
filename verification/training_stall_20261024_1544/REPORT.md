# PPO learning-progress review — 2026-10-24

Scope: the user clarified that training is running; assess slow improvement and
whether reward tuning is justified. All server operations were read-only.
No reward command, optimizer step, extra game, source deployment, restart or
checkpoint edit was performed. The initial evidence directory name uses "stall"
but the investigation concerns learning quality, not a process hang.

Run/source: `runs/v5_lite_resume_20261024_1420` under
`/home/tongshu/myDev/wesnothLearning/validation_memory_repair_20261024_1321`.
Rule SHA: `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`.
Code examined locally is master `3510d33`; Ubuntu hashes for control.py, train.py,
rewards.py and experiment.py match the run's frozen manifest. Existing 18:50:52
update / 22:30 total deadlines remain intact.

## Observed progress and limits

At the 15:52:59 snapshot, history and the read-only SQLite sequence index give:

| Format | Version | Completed PPO batches since recovery | Optimizer steps since recovery | Planned steps from indexed own-turn counts |
| --- | ---: | ---: | ---: | ---: |
| duel | 261 | 49 | 175 | 380 |
| ffa4 | 107 | 19 | 73 | 296 |
| team2v2 | 57 | 7 | 32 | 196 |

The plan estimate uses the actual training partition, ceil(own turns / 8)
windows, 4 windows per CPU step and 4 epochs. It is an index-based estimate,
not a full trajectory replay. No trajectories were decoded for this check.
The corresponding step fractions are about 46%, 25% and 16%. They do not measure
what fraction of decisions was visited, nor prove that more steps would improve
strength. PPO intentionally limits policy movement.

In the separately captured state a few minutes earlier, 42/47 duel, 18/18 FF4
and 7/7 team2v2 completed PPO batches ended through the KL branch. The median is
4 optimizer steps per batch. That branch compares a single <=32-decision chunk
to .02, stops the entire update and discards any partial gradients. Investigate
this local KL criterion / actual step size before increasing update pressure;
do not remove the protection or assume raising its threshold improves learning.

An additional logging limitation: the KL return omits decisions_seen,
effective_dataset_passes and sequence_windows. Therefore the unchanged FF4/2v2
exposure counters do not mean no samples were trained. Optimizer steps are real
and advancing. BC imitation accuracy is also only recalculated in the BC branch,
so recruit/move/attack accuracies are historical BC results during PPO.

## Strength evidence is noisy and incomplete

Duel's current 6-game trend panels at v220/230/240/250 have policy-control score
differences +2.0 / -1.5 / 0 / -1.5. Their maps, seeds and faction cycles vary;
this is not a matched before/after test or evidence of steady convergence.

FF4 v90 has normalized rank scores .417 vs Astra .625 on 4 games. Its v100
12-block promotion panel (48 games) gives .420 vs .583, difference -.163 with
95% block-bootstrap interval [-.309, -.035]. It remains below Astra there.
These are rank scores, not win percentages, and the panels differ.

Team2v2 has no post-recovery validation panel at the initial snapshot (v57,
next validation v60). Last old v50 difference is -1.125 on a single 8-game
rotation block. Its last BC attack accuracy was 12/85 = 14.1%, recruit accuracy
15/29 = 51.7%, and overall BC eligibility remains false; forced-PPO provenance
is preserved. Only seven new PPO batches cannot establish a strong trend.
The previous attack weakness is a separate learning-base concern, not evidence
that increasing exploration would fix it.

## Reward findings

All three actual configs remain reward_version 0: economy .15, control .10,
explore .10, entropy .01, BC auxiliary .10, mode adaptive. No control events or
metrics errors were present. Duel's last v250 validation shaping RMS is .00959
versus terminal RMS .07259; FF4 v100 is .00761 versus .08085. This establishes
that shaping has not overwhelmed the terminal reward in those diagnostics;
it does not prove the optimal scale or justify increasing every coefficient.

**Confirmed defect:** `RewardController._decision` drains new 12-block windows
only while `len(self.windows) < 3`. Once there are three, it never replaces them.
Captured duel state had 55 pending complete blocks, and the later real Ubuntu
reproduction has 58 through v260. The real function leaves all 58 pending and
its three windows unchanged. No constructor or control API was invoked in that
probe: it builds an in-memory object from captured state, so disk/live state is
unchanged. The assertion intentionally fails with this exact symptom.

FF4 has one completed window plus 8 pending blocks; 2v2 has zero windows and
2 pending blocks. Their lack of automatic changes is not the same three-window
bug yet. The established 50-batch / 64-new-game trigger, two comparable 12-block
windows and all-strata criteria also make adaptive changes infrequent.

An offline refresh simulation consumes 48 of duel's captured 55 blocks and
keeps the newest three windows. Current existing rules still recommend no
coefficient change: low_explore=false, low_control=false, safe=false, and the
three windows do not all satisfy met_explore. The stale-window defect is real,
but fixing it alone is not evidence that rewards will change or strength rise.

## Recommendation and next minimal checks

Do not increase reward coefficients in the running experiment based on the
present panels. First fix the rolling-window defect in local source, with the
captured >=3-windows plus >=12-new-blocks assertion; verify that <=3 retained
windows refresh while incomplete blocks remain. A source change still needs a
controlled deployment to the frozen run, not an in-place hot edit.

Then isolate whether the chunk-level KL stop is unnecessarily sensitive, using
an existing frozen trajectory/checkpoint off the training process. Compare
initial policy-log-probability agreement and policy movement across fixed
chunks; only then decide between step-size or aggregate-KL changes. Preserve
on-policy provenance and the trust-region constraint. No such optimization
experiment was run in this investigation.

Reward coefficients can use the existing batch-boundary control queue with
versioned application and rollback. Choose a single field only after a repeatable
behavior deficit and a comparable validation panel support it. Current data do
not identify a justified field/value; especially do not increase exploration
just because a strength score is flat. Reuse the next scheduled v60 2v2
validation rather than launching extra games now.

## Evidence / reproduction

- `quality-snapshot.ubuntu.txt`: read-only current/parent states, comparisons,
  reward diagnostics/configs and no new errors; bounded memory snapshot.
- `*_state.json`, `*_control.json`: raw captured state/controller inputs.
- `utilization.ubuntu.txt`: read-only index-based plan and update counts.
- `analysis-repro.local.txt`: local real-function stale-window assertion fails;
  first direct-file invocation lacked the module path (`analysis.local.txt`).
- `window-refresh.local.txt`: offline window simulation and unchanged decision.
- `controller-repro.ubuntu.txt`: real frozen Ubuntu function reproduces the
  stale-window defect, expected exit 1; source hashes match the manifest.

Local command: `.venv/Scripts/python.exe -m verification.training_stall_20261024_1544.analyze_quality`
Ubuntu command: `.venv/bin/python -u - < controller_repro.py` from the isolated
source root, with payload supplied through SSH. No existing acceptance suite,
live-game test or pressure replay was rerun. The defect is diagnosed, not fixed.
