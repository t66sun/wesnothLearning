# Team critic calibration and the scored horizon

Issue [#224](https://github.com/t66sun/wesnothLearning/issues/224), 2026-11-06. This diagnosis adds exact boundary fixtures and reads frozen results; production training, reward and engine code are unchanged. The owner has selected **the official 30-turn competition score** as the optimization objective. The current 60-turn continuation contract does not implement that objective.

The full team PPO census finds two independently actionable problems. Of 924 games used by completed optimizer batches, 663 (71.75%) were still running after turn 30, and 36.38% of recorded decisions occurred after that horizon. Separately, the critic develops predictions outside the possible complete-return range: among late capped games, 58.09% of decision values and 68/99 boundary bootstraps exceed the conservative support. These facts justify aligning the objective and checking critic calibration separately; they do not establish either one's causal effect on playing strength.

## Scope and evidence

- [Calibration census](calibration.json): all 231 committed team PPO batches, 924 games and 341,940 decisions; per-game identities and SHA-256 for all schedules/shards. The uncommitted pending batch is excluded. Consequently the 298/924 capped fraction (32.25%) has a different denominator from the earlier audit's 32.33% over all collected games.
- [Objective comparison](objective_alignment.json): joins those games to immutable result metadata, using the actual game end turn rather than the learner's last action turn.
- [Scalar probe](probe.py) and [objective summary](objective_alignment.py): no model update, inference rerun, simulation or input writes. Predictions are the frozen rollout-time critic values from each contemporaneous snapshot, not one checkpoint reevaluated across every historical state.
- [Exact fixtures](../../tests/v5/test_critic_horizon.py) and [Ubuntu results](contracts.log): 16 tests passed, comprising 11 new horizon/diagnostic assertions and 5 existing reward-schema assertions. [Census progress](calibration.log) records 176.1 seconds for the final scan.
- [Previous architecture audit](../ppo_architecture_audit_20261106/REPORT.md) and [formal run review](../formal_30h_scratch_20261106/REPORT.md) remain unchanged.

The probe checks policy-only train rows, one game/side per shard, frozen snapshot version, homogeneous per-game reward configuration, recorded split, complete batch decision counts, and absence of faults. All 341,940 stored step rewards exactly equal the production transition formula (maximum absolute error **0**). All natural-terminal Monte Carlo returns satisfy their realized-state bounds. This supports the arithmetic and row contract; it is not native-engine or strength acceptance.

## Current boundary semantics

The implemented contract is in [reward transitions](../../learning/rewards.py), [row writing and GAE](../../learning/data.py), [Lite end-turn handling](../../engine_lite/src/state.rs), and [operations](../../docs/instructions.md).

1. A learner-side trajectory is sorted by `(turn, decision)`. For successive own decisions, `dt = next.turn - current.turn`. GAE is `delta = r + gamma**dt * next_value - value`, followed by `A = delta + (gamma*lambda)**dt * next_A`. Defaults are `gamma=1`, `lambda=.95`. Multiple actions within one own turn have `dt=0`; an actual two-turn gap has exponent 2. The rollout's number of actions does not itself shorten this trace.
2. Natural victory is a task terminal. The final transition applies the signed terminal outcome, clears economy/control potential, and uses zero bootstrap. Exploration already earned at the endpoint is retained.
3. A live team at a training `turn_limit` is treated as externally truncated. The final transition ignores the stored terminal label, retains endpoint potential, and adds the recorded critic bootstrap. Every such row has `value_valid=False` for BC. A dead learner with a surviving teammate is still part of a live team; its bootstrap can be many own turns after its last action.
4. Lite advances to the next side/round, then stops if `turn > max_turns`, before that next side receives income/healing. The formal run's cap is 60, so a capped result has `turns=61`; this is not a played 61st turn. Reducing only `training_max_turns` to 30 would stop at that boundary sooner but would **still bootstrap** under the present row contract.
5. The current global feature includes `turn/30`. Under a fixed, known 30-turn objective, remaining time is derivable already. Adding a remaining-time feature is not a demonstrated missing requirement. Mixing different task horizons would require an explicit objective identity/context or separate policies.

The current code consistently implements continuation through a computational cap. The conflict is with the selected product objective, not evidence of a swapped `terminated`/`truncated` boolean or a broken own-turn exponent.

### Hand calculations

All numbers below are asserted directly, independent of learned convergence.

| Fixture | Inputs | Expected result |
|---|---|---|
| Same-turn trace and two-turn gap | Turns `[1,1,3]`, values `[.2,.3,.4]`, terminal `+1`, zero shaping, gamma `1`, lambda `.5` | Advantages `[.35,.25,.6]`; GAE targets `[.55,.55,1]`; MC returns `[1,1,1]` |
| Gamma and lambda use the same clock | Same inputs, gamma `.9` | Advantages `[.2455,.1455,.6]`; GAE targets `[.4455,.4455,1]`; MC `[.81,.81,1]` |
| Truncated tail uses its actual gap | Turn `3` to bootstrap turn `5`, gamma `.9`, value `.4`, bootstrap `.8`, shaping coefficients `.1` each, raw `(.2,.4,.3)`, endpoint `(.5,.6,.4)` | Step `.0391`, target `.6871`, advantage `.2871`; invariant to stored terminal label `-1/0/+1` |
| Boundary condition changes the target | Turn `60` to `61`, gamma `1`, bootstrap `-2.1`, same raw/endpoint as above | Continuation target `-2.04`; a scored draw at the **recorded 60-turn cap** would instead return `-.05` |
| Natural terminal | Terminal `+1`, same raw/endpoint, irrelevant bootstrap `-200` | Return `.95`; bootstrap ignored |
| Dead learner, live teammate | Learner last acted at turn `1`, ally still alive, bootstrap turn `11` | Team is truncated, BC outcome invalid, tail span exactly `10` |

The counterfactual uses a copied row and the actual `bootstrap_raw` endpoint for exploration. It neither mutates the shard nor treats `reward_after` at the learner's last action as the cap endpoint. It answers the boundary-condition question at **60**, not the selected 30-turn objective.

## Calibrate against observed outcomes, not against the critic itself

For natural games, `observed_mc_return` is the complete sum of recorded reward transitions. For capped games, `bootstrap_return` ends with the recorded value estimate: its residual measures consistency with that estimate, not calibration against an observed eventual outcome. GAE targets also contain critic predictions and are not independent truth, even for naturally finished games.

Bias is `mean(prediction - target)`, so negative means underprediction. MSE is `mean(error**2)`; explained variance is `1 - Var(error)/Var(target)` and is null for a constant target. Each table value below is game-weighted: every game contributes total weight one. Row-weighted counterparts are in the census; long games receive more weight there. These are descriptive moments over correlated decisions, not independent confidence intervals.

| Cohort / target | Games / decisions | Prediction mean | Target mean | Bias | MSE | Explained variance |
|---|---:|---:|---:|---:|---:|---:|
| Natural / observed MC | 626 / 167,610 | -.1970 | -.0319 | -.1651 | .3419 | .6660 |
| Natural / GAE | same | -.1970 | -.1188 | -.0782 | .1200 | .8603 |
| Capped / bootstrapped return | 298 / 174,330 | -.8156 | -1.0959 | +.2803 | .3347 | .7392 |
| Capped / GAE | same | -.8156 | -.9506 | +.1350 | .0980 | .9089 |
| Capped / hypothetical scored draw at 60 | same | -.8156 | -.0515 | -.7641 | 1.4705 | -1463.7610 |

The last row's huge negative explained variance follows from tiny target variance (`.0006053`), since all capped games would be draws under that hypothetical objective. Its MSE/bias are easier to interpret. It is neither an observed target under the legacy continuation task nor a 30-turn calibration result.

Observed natural MC targets span **[-1.09186, +1.00687]**, while natural-game predictions span **[-2.79319, +1.52629]**. Capped predictions span **[-4.14435, +1.28589]**, their bootstrapped-return targets **[-3.92854, +1.04057]**, and their GAE targets **[-3.94422, +.95379]**. Thus low TD/GAE residuals can coexist with targets outside the support of completed returns.

### Progression through the run

Each phase contains 77 batches / 308 games: early batch IDs 53–129, middle 130–206, late 207–283. Policies, opponents and realized states change, so this is not a controlled comparison on a common frozen state set.

| Phase | Natural MC bias / MSE / EV, game-weighted | Natural rows outside support | Capped rows outside support | Bootstrap mean | Bootstraps outside support |
|---|---|---:|---:|---:|---:|
| Early | -.1199 / .3734 / .6181 | 283/57,118 = .50% | 1,257/60,044 = 2.09% | -.4739 | 8/102 |
| Middle | -.1374 / .2497 / .7556 | 3,044/54,157 = 5.62% | 18,570/56,792 = 32.70% | -1.1481 | 49/97 |
| Late | -.2376 / .4040 / .6307 | 6,738/56,335 = 11.96% | 33,401/57,494 = 58.09% | -1.6942 | 68/99 |

The late natural row-weighted MC bias/MSE/EV are **-.3879 / .5829 / .4515**; the difference from game weighting confirms that long trajectories materially affect the pooled impression. Capped games are 32.25% of games but **50.98% of decisions**, so the affected data have substantial PPO exposure. The lowest recorded boundary bootstrap is **-3.91179**. Earlier reports sampled a narrower late set; these full-census phase averages are not expected to equal those samples.

### The support check respects partial observability

With `phi = .15*economy + .10*control`, economy in `[-1,1]`, control in `[0,1]`, total exploration reward at most `.10`, gamma `1`, and complete terminal outcome in `[-1,1]`, a complete realized return from state `s` lies in:

```text
[-1 - phi(s), 1 - phi(s) + .10*(1 - explored(s))]
```

That state interval must **not** be used to condemn a policy value: referee reward potential may depend on hidden state, and the legal observation can correspond to multiple such states. Taking the union over hidden states gives the conservative critic support **[-1.25, +1.25]**, used for every outlier count above. Tests explicitly distinguish these two bounds. This is a diagnostic condition, not a proposal to expose reward truth to the actor or clip all value targets. All scanned shards have reward version 0 and the formal `.15/.10/.10` coefficients; changed coefficients require recomputed support.

Observed drift below support is established. A feedback loop in which pessimistic tail bootstraps train earlier predictions downward is a plausible mechanism, supported by the target recursion and joint drift; this census does not isolate it from value-loss weighting, shared actor/critic representation, optimizer interference, state-distribution change, or sparse independent terminal targets. A universal value clamp or a critic-network replacement is not justified by these data alone.

## Alignment with the chosen official 30-turn objective

The following counterfactual holds each recorded action prefix fixed: a natural win/loss already reached by turn 30 remains that outcome; every unfinished game is counted as a draw. It is not an experiment with a newly trained 30-turn policy or a newly played official match. This mapping agrees with the present team scorer: [official_score](../../learning/evaluate.py) uses only `winning_team` and gives an unresolved team game one point, ignoring `rank_points`, unit count and economy. [Scheduled evaluation](../../learning/schedule.py) caps at 30; [Lite results](../../learning/lite_host.py) retain winner zero at that cap, and the [native team adjudicator](../../vendor/arena/teams.py) also leaves winner zero when both teams survive. The source mapping is checked; native replay equivalence is not claimed.

| Recorded team trajectories | Games |
|---|---:|
| Natural ending by turn 30 | 261 (28.25%) |
| Natural ending after turn 30, before the old cap | 365 (39.50%) |
| Reached the old 60-turn cap | 298 (32.25%) |
| Still going at the official horizon | 663 (71.75%) |

The same prefixes have **147 wins / 663 draws / 114 losses at 30**, versus **322 wins / 298 draws / 304 losses** at their recorded endings. Official own-score means would be **1.19481** versus **1.36797** under the existing team score mapping. These are different objectives, not an improvement/regression comparison. **124,409 / 341,940 decisions (36.38%)** were made after turn 30. A correct target for decisions before turn 30 must also stop at that horizon; simply discarding late rows would leave their old continuation targets wrong.

The current team scorer gives win/draw/loss **3/1/0**, whereas terminal training reward gives **+1/0/-1**. The latter is exactly one third of the own-minus-opponent official score, but is **not** an affine transform of own official points: all draws and a 50/50 win/loss policy have equal signed expectation, while expected own points are 1 and 1.5 respectively. The fixed 30-turn objective is decided. The recommended production interpretation is to maximize **the team's own official points**, shared by both teammates, rather than silently substituting score difference. Its normalized score mapping below is a proposed implementation of that choice, not an already deployed behavior. The fixture locks this distinction to the current scorer.

### Production changes supported by the evidence, kept out of this diagnosis

1. **Version the finite scored-task contract.** Freeze horizon 30, team-shared official own points, and task-terminal versus external sampling-cut semantics in new run/data/checkpoint identities. Recommend the positive affine normalization `z = 2*score/3 - 1`: win/draw/loss targets **`[+1, -1/3, -1]`**. Use `gamma=1` on the existing own-turn clock, so an earlier win does not gain an unrequested time bonus. Every teammate receives the same terminal `z`, including a learner eliminated before its teammate. Retain score difference as a separately named evaluation statistic; it must not silently become the optimization target.
2. **Make the official horizon a true task terminal.** When an unfinished scored game exhausts turn 30, apply draw `z=-1/3`, clear terminal economy/control potential, and use no critic bootstrap. A genuine external sample cut *before* task completion remains truncated and requires bootstrap; do not turn all truncations into losses or remove bootstrap universally. Preserve team survival semantics and the exact final round boundary. Keep economy/control shaping as `gamma**dt * phi(next) - phi(now)` with `phi(task_terminal)=0`. For an exact official-score objective, recommend exploration coefficient **0**: then the complete return is `z - phi(start)`, differing from normalized official points only by the starting potential. BC's `value_valid` contract must recognize a known finite scored outcome as valid; the old rule invalidates all live-team cap outcomes.
3. **Align new schedules and provenance.** Teacher, DAgger and PPO scored episodes must use the same 30-turn task contract. Coordinate with sampler issue [#223](https://github.com/t66sun/wesnothLearning/issues/223) so scenario coverage and horizon identity agree; longer diagnostic/continuation tasks need a different declared identity. Evaluation/selection remains the official 30-turn comparison owned by [#222](https://github.com/t66sun/wesnothLearning/issues/222). Passing only `--training-max-turns 30` implements none of the terminal/score changes above.
4. **Measure calibration before architecture tuning.** Add routine natural/scored-terminal MC bias, MSE, explained variance, support violations, and separately labelled external-truncation residuals, stratified by stage/turn band with both row and game weights. Recheck after the objective boundary is corrected. If out-of-support drift persists on independent observed targets, compare critic loss/representation or target stabilization in an authorized controlled experiment; do not use the current census as proof that clipping solves playing strength.

These are separable implementation/acceptance responsibilities. The first three must agree before interpreting a new training result; critic architecture experiments depend on that common target. The existing exploration reward is a bounded auxiliary objective, not potential shaping that telescopes to a constant. Retaining or annealing it would be an explicitly declared auxiliary training phase, not exact official-score optimization. The proposed zero-exploration contract is kept out of this diagnosis along with the other production changes. Its completed-return support must be recomputed for the chosen coefficients; the historical `[-1.25,+1.25]` diagnostic is not a permanent hard-coded clamp. Economy/control potential at a finite terminal cancels future endpoint potential, unlike the current capped continuation boundary.

Compatibility is strict: do not relabel frozen 60-turn rows, reinterpret old manifests, change historical checkpoints, or resume them as if the task were unchanged. The existing rows do not provide every side's exact turn-30 exploration endpoint, especially after an early learner death, so this prefix summary is insufficient to manufacture shaped 30-turn targets. An old policy may be an explicitly identified initializer for a newly declared run after compatibility checks; its critic and optimizer state are not evidence of calibration for the new target. Reward/objective versions, dataset eligibility, BC terminal targets, PPO targets and resume rejection tests must be handled together.

## Reproduction and verification

Frozen run: `/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/runs/formal_30h_scratch`.

| Identity | Value |
|---|---|
| Run manifest SHA-256 | `6de9d81858c71c41de505db2c445bae5229fa8587db7a6d3d66d2ebc3eab3c88` |
| Rules SHA-256 | `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17` |
| Rust extension SHA-256 | `56dd77140411db987377d6de4ffbf562da4d0e5c76bc16d34780da67e60e5ae4` |
| Final scalar-census commit | `4491660153e33a0446feff496251849056b1c129` |
| Census git archive SHA-256 | `4054760ef39df462d49181488f0f42ce0b7ce656f0fab93a5f6d9997c4092234` |
| Objective/fixture commit | `023eae5a5771766af559a38581e15dd5d3500444` |
| Objective git archive SHA-256 | `45d9cef946896daca4eb78129d68136127f08a68f95f2ea8fd80f2dff4d683fa` |
| Calibration output SHA-256 | `a66ca9d78c151d688400e720050c93d1d78aa291e26369b5998697a0d2d5e591` |
| Objective output SHA-256 | `b9fafe66fb5a30ef91a3292fe5b4cd3827dc09c31bce8f5fab13f229f9320fc6` |

Both sources were committed locally and shipped as `git archive` tarballs to fresh Ubuntu directories. Final census source/results are under `/home/tongshu/acceptance/issue224_20261106_v3/`; objective/fixture source/results are under `/home/tongshu/acceptance/issue224_20261106_023eae5/`. Use a fresh output path when reproducing; the tools refuse to overwrite existing output.

```bash
formal=/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source
base=/home/tongshu/acceptance/issue224_20261106_023eae5
cd "$base/source"
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$base/source:$formal/.extension"
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
/home/tongshu/venv/bin/python -m unittest tests.v5.test_critic_horizon tests.v5.test_reward_row_schema
/home/tongshu/venv/bin/python verification/team_critic_horizon_20261106/probe.py \
  "$formal/runs/formal_30h_scratch" "$fresh_output/calibration.json"
/home/tongshu/venv/bin/python verification/team_critic_horizon_20261106/objective_alignment.py \
  "$formal/runs/formal_30h_scratch" "$fresh_output/calibration.json" "$fresh_output/objective_alignment.json"
```

Final Ubuntu verification: **16 tests, 1.164 seconds, OK**. The first fixture attempt produced 12 passes and one setup error because a turn-51 row lacked its complete history prefix; [the original failure](initial_fixture_failure.log) is retained. The fixture was corrected to a complete turn-1 prefix with the same ten-turn bootstrap gap. A preliminary bound analysis was also tightened before publication: realized hidden-state support is only checked against realized MC returns; critic outlier counts use the global support. No production failure was disguised by these diagnostic corrections.

No new games, corpus collection, optimizer steps, Windows tests or native strength evaluation were run. Arithmetic correctness, the current/desired objective mismatch, and the recorded calibration defect are established; causal PPO benefit from the proposed changes remains to be measured after their separate implementation and authorization.
