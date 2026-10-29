# Rewards and online control: follow-up test scope and wiring contract

> Language: English | [中文](REWARD_TEST_SCOPE_zh.md)

The per-item list from the original implementation phase is kept below. Pass records live in the dated `verification/` reports; [docs/TEST.md](../docs/TEST.md) holds only acceptance work that is still open.

## Wiring contract

- `RewardConfig` frozen fields are `economy/control/explore/mode/entropy/bc_aux/gamma/gae_lambda/reward_version/reward_formula_id`. The terminal weight is fixed at 1 and offers no adjustable entry.
- `lua/rewards.lua.capture(obs,memory,true)` only puts referee economic quantities into the returned `reward_raw`. The returned `economy/control` are current potentials and `explored` is the cumulative normalized area after deducting the initial visible area. Only the next snapshot minus the current one is one interval's exploration delta. Never merge these referee labels into public value inputs, global, spatial or candidates.
- Capture the initial snapshot before each side's first action, and a snapshot after every action and at the end; a normal terminal zeroes potentials but keeps the last exploration delta, while truncation keeps the matching final raw/value/turn bootstrap.
- Lua defaults to uniform exploration-area weights with whole-game `explored<=1`; it is zero without fog. Shroud being off still checks actual fog visibility. Complex or one-way sharing rules are provided by the host via `shared_exploration_scope/shared_exploration_members/shared_ledger` and never widen sharing automatically. By default the shared domain is generated from allies where both sides enable share_view or share_maps. At runtime `initialize_all()` is called once after initial units and vision are established and before any action, excluding every side's initial visible area. The ledger lives in a uniquely named global of the game Lua kernel, shared by LearningSupport and different exported policy addons; only the scope this side may see enters its memory and the global ledger is never passed to the actor. Each game process/host reuse reinitializes; `reset()` may clear the ledger.
- Map control defaults to four movement-cost fingerprint clusters on legal terrain, bounded multi-source shortest paths, and enemy history decaying exponentially per turn. With more than four movement fingerprints the nearest of the four is used, an explicit reward-computation approximation. Cells with no units/unknown are neutral. The total strategic weight is a referee-normalized scalar; hidden strategic positions must never reach the actor.
- `RewardController(run_dir,format_name,state=checkpoint_state,config=initial_dict)` is per format. `boundary(batch,metrics)` is called only after the previous collection and update have fully finished, and its return value is frozen for every job/game of the next batch. `state_dict()` enters the existing checkpoint and never replaces budget, optimizer or RNG state.
- The CLI calls `queue_control(run_dir,format_name,changes)` where fields are limited to `economy/control/explore/mode/entropy/bc_aux`. `mode=fixed` may pause automatic control. `show_control` returns the effective config, pending commands, event sequence and last error. Pending commands are written atomically per format and share the append-only `control/events.jsonl` on application; events carry the full old/new, source, reason, batch, sequence, command ID, checksum and previous checksum, and the command ID prevents duplicate application during crash recovery.
- `scheduled` mode is built with `schedule=[{'batch':50,'changes':{'explore':0.09}}]`; the schedule cursor enters controller state. Manual changes during a run and scheduled changes still go through the same pending/event path.

## Automatic-control evidence format

`learning/reward_metrics.py` implements the evidence chain from real trajectories to the controller. Sampling results are saved as `reward_diagnostics=summarize_game(records,result,job)`; `build_control_metrics(validation_jobs,validation_results,teacher_evidence,comparison)` aligns the policy side's metrics in full rotation blocks against a real Astra reference and returns the metrics below. The reference must be the validation partition and exactly match format, engine, rules, map name and SHA, faction and teammate context, with at least four independent game_families per stratum. Training maps and holdout cannot substitute, and missing records go into `excluded_evidence` instead of producing a tunable complete block.

Turn 5/10 metrics take that side's last committed decision's real reward_after/raw in that turn; a missing turn is not interpolated. Leader survival prefers the referee's final survivors list and otherwise the turn-10 public own-leader HP; loss uses HP decrements from consecutive legal own-unit snapshots (a death confirmed by a complete entity snapshot counts its remaining HP), divided by the max-HP capacity of the unique own units seen; with an incomplete entity list the loss is missing and deaths are not guessed. It is an explicit HP-loss metric, not unknown-enemy or gold/material loss. It is compared only against Astra records with the same definition.

Reference sampling should create an independent `phase=reward_reference` job from the teacher job skeleton, switch to validation maps, cover the same factions and teammate contexts, enable only Astra collection, save diagnostics and stay out of the BC teacher shard pool. Validation policy jobs must also enable training log capture on policy_sides to obtain raw signals. Both native and lite samplers should hook summarize_game. The builder returns `new_games=0`; PPO collection keeps supplying the incremental fault-free trajectory count separately so the same game is never counted twice.

`boundary`'s `metrics` are increments since the last commit, not re-accumulated statistics:

```json
{
  "partition": "validation",
  "new_games": 64,
  "faulted_games": 0,
  "shaping_rms": 0.03,
  "terminal_rms": 0.4,
  "validation_blocks": [{
    "id": "duel-v100-map1-block0",
    "complete": true,
    "faults": [],
    "fixed_score": 0.2,
    "native_score": null,
    "strata": [{
      "map": "Hamlets",
      "faction": "Loyalists",
      "coverage5": 0.3,
      "coverage10": 0.5,
      "astra_coverage5": 0.4,
      "astra_coverage10": 0.6,
      "control": 0.3,
      "astra_control": 0.5,
      "leader_survival": 1.0,
      "astra_leader_survival": 1.0,
      "loss": 0.1,
      "astra_loss": 0.2
    }]
  }]
}
```

When `new_games` includes faults they are deducted through `faulted_games`; if upstream already reports a fault-free count, `faulted_games` should be zero. Rotation block IDs are globally unique, accepted only when complete, and de-duplicated by ID. Every window needs at least 12 complete blocks and is checked every 50 batches with at least 64 new fault-free games; exploration/control adjustments need two comparable windows and a mature exploration decrease needs three. A strength regression requires three windows forming two consecutive drops while control metrics rise consecutively; six games cannot trigger a rollback. Native scores are never synthesized without native evidence. Final test/holdout/final partitions are never tunable.

## Follow-up checks that must be covered

| Scope | Inputs and criteria |
| --- | --- |
| Terminal | duel win/draw/loss +1/0/-1; shared teammate payoff in 2v2; FFA ties, all-draw, differing point scales, zero mean and max absolute value 1 or all zero |
| Economy | potential unchanged when equal gold becomes healthy troops; injured/healed/dead/upgraded/negative gold; team average rather than sum; bounded result |
| Potentials and GAE | multiple actions in one turn are not discounted twice; differing own-turn spans; normal terminals zero potentials; truncated raw/value bootstrap with the same version; last action's exploration delta kept; faulted games excluded |
| Exploration | all sides' initial/shared initial area deducted; round trips and re-revealed fog not double counted; ally sharing versus not; shroud off with fog on; zero by default without fog; whole-game positive reward capped at the frozen explore coefficient |
| Legal map control | score and actor inputs unchanged when hidden enemy position/HP changes but legal observations do not; only last-seen age changes; re-visible legal cells forget absent old enemies; unknown terrain builds no graph; fixed denominator; same-cell strategic weight takes max, not a sum |
| Graph budget/cache | at most four cost graphs; multi-source distances match hand-computed small maps; same-view reuse within a turn; correct invalidation on terrain, visible own movement/HP, legal enemy appearance/disappearance, turn decay and normalization changes; cache never grows per candidate |
| Native RNG | enemy history uses a detached clone; repeated capture changes no combat RNG, unit/map state or policy legal candidates |
| Automatic evidence | batch 49/50, game 63/64, block 11/12 boundaries; faults/missing/duplicate blocks; map/faction Astra alignment; two-window thresholds; exploration three-window decrease; hold without evidence; each automatic weight change ≤10% and within range |
| Real evidence collection | native/lite sampler diagnostic wiring; real turn 5/10 raw sampling; leader loss and unit deaths; healing and recruiting not masking HP loss; 128-entity truncation not faking deaths; missing evidence kept without a complete 10-turn trajectory; at least 4 independent Astra game families; same map name with different SHA, different engine/rules, faction or teammate context must not be mixed; BC data pools exclude reward references |
| Rollback | fixed opponents and native separated; control rising while scores drop for two consecutive windows; small-panel noise does not trigger; only control rolls back, unrelated items such as economy/entropy untouched |
| Manual control | errors on out-of-range, NaN, unknown fields and empty commands; fixed mode pauses automatic control; manual entropy/BC auxiliary never confused with reward weights; unchanged within a batch, effective for a new batch/game |
| Files/resume | atomic pending replacement; concurrent queues across three formats; global event sequence and hash chain; crash points before and after application; appended-but-uncleared pending not applied twice; lagging checkpoint cursor replayable; ahead cursor/corrupt checksum errors; resume resets no statistics/budget |
| PPO isolation | same batch freezes policy, reward and engine rule versions; new rewards cannot reuse old advantage/bootstrap; BC action labels may be reused; a hot change in one format does not affect the other two |

## Reporting requirements and current gaps

Every report gives format, engine, rules/RNG, reward formula and config version, model version, map/faction, game_family/seed, input summary, expected and actual, status (pass/fail/not_run/blocked) and the evidence path. Performance additionally records control-graph construction/search/cache-hit timings and peak memory. Behavior is reported per map/faction as first leave-keep, turn 5/10 exploration and village/strategic control, leader survival, casualties and formal win/draw/loss; shaping totals never substitute for strength.

Still to be confirmed with a shared native and lite host: the initial snapshot moment, the post-last-action snapshot, shared ledger lifetime and complex one-way sharing, unit-clone history retention, whole-map scalar referee permissions, the fixed strategic-set policy after map terrain changes, and whether the control evidence collector is wired in the full rotation-block format above. The Python/Lua control algorithms use the same bounded exponential influence form; movement clustering and terrain strategic labels still need consistency and migration audits on the real rule table. Without enough Astra strata/complete rotation evidence, adaptive must stay at its initial values rather than use uncalibrated proxy metrics.
