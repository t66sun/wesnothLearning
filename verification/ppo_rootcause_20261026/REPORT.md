# PPO root-cause diagnosis of `v5_lite30h_20261025` — read-only evidence

Date: 2026-10-26. Author: repository owner. Status: **diagnosis only** — no training, no runtime change, no new corpus, no native game.

## Scope

Answer these questions for the completed 30-hour lite run, from the frozen run data only:

1. Does the behaviour policy reproduce the recorded probabilities? (input contract: prefix, candidate order, mask, action index, memory commit, logp, value)
2. Does the PPO update see the batch that was collected, and how much work does it actually do?
3. Are the evaluation panels independent, and what does the promotion/final gate really measure?
4. Are the reward, potential shaping, truncation bootstrap and GAE implemented as documented?
5. Does the policy actually change with PPO, and in which direction?
6. Which stock 1.18.8 RCA decisions are observable at all, for the Astra replacement plan?

Out of scope: reward/optimizer tuning, full test-suite reruns, strength matches, any modification of the frozen run, the rule package, corpora, manifests, checkpoints or historical reports.

## Identity

| Item | Value |
| --- | --- |
| Run | `runs/v5_lite30h_20261025` under `/home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source` |
| Declared frozen commit | `822082d654cd19a6474aa36f837137c1ec7cb83c` |
| Run completion | 2026-10-26 16:35:34 Asia/Shanghai, all three trainers exit 0 |
| Engine (all formats, all jobs) | `lite-0.2`, `deterministic-expected_damage_v1`, `expected_damage_v1` |
| Selected checkpoints | duel `1f619c27…` (v400), ffa4 `e1148429…` (v100), team2v2 `aff0675b…` (v100) |

`git` is not on the server's non-login `PATH`, so the commit id cannot be re-verified there. Identity was instead established by content hash of every module the probes import. Local `master` (`6fdd15f`) versus the frozen tree:

| Module | sha256 (first 8) | Match |
| --- | --- | --- |
| `learning/ppo.py` | `00628cbf` | identical |
| `learning/data.py` | `7f0cfd9f` | identical |
| `learning/experiment.py` | `c9dde288` | identical |
| `learning/sequences.py` | `718a5944` | identical |
| `learning/updates.py` | `db190b91` | identical |
| `learning/lite_policy.py` | `ff196ef5` | identical |
| `learning/lite_host.py` | `74d21b72` | identical |
| `learning/maps.py` | `e50618ef` | identical |
| `learning/schedule.py` | `d27f1b09` | identical |
| `learning/evaluate.py` | `58b5284b` | identical |
| `learning/rewards.py` | `edb87062` | identical |
| `learning/export.py` | `6ff093a3` | identical |
| `learning/manifest.py` | `9224744d` | identical |
| `learning/model.py` | — | CRLF-only difference (`diff -q --strip-trailing-cr` clean) |
| `learning/native_rpc.lua` | — | CRLF-only difference |

So the update, evaluation and reward code under test is byte-identical to the frozen run's code. No result below mixes another run's data: every probe reads `runs/v5_lite30h_20261025/<format>/…` only.

## Environment and resource caps

| Item | Value |
| --- | --- |
| Host | `cpuServer` (`tongshu@192.168.122.118`), existing venv `/home/tongshu/venv/bin/python`, PyTorch 2.9.1 |
| Isolation | new directory `/home/tongshu/myDev/wesnothLearning/diag_ppo_20261026/`; originals read-only |
| Threads | `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1` |
| Batch under test | `duel` version 99, `rollout-00099-duel-g0..3.jsonl.gz`, 421 rows (291 train / 130 validation), 4 games |
| Caps | `--games 4`, `--limit 400`, `WL_MAXFILES=24`, at most 64 rows per forward, 32 rows per microbatch |
| Wall time | whole suite 65.97 s; no GPU; no process left behind |
| Writes | only `diag_ppo_20261026/out/*.log`; the run tree was opened read-only |

## Commands

All eleven probes were re-run in one controlled pass (`verification/ppo_rootcause_20261026/run_all.sh`, uploaded verbatim) with `WL_SOURCE=<frozen tree>`, `WL_RUN=<frozen tree>/runs/v5_lite30h_20261025`. Every step printed its own exit code:

```text
a_accounting rc=0
c_replay rc=0
c_grad rc=0
d_batch rc=0
e_gradpath rc=0
f_final rc=0
g_independence rc=0
g_trend rc=0
h_reward rc=0
i_drift rc=0
j_prefix rc=0
```

Invocation form:

```sh
ssh cpuServer 'cd /home/tongshu/myDev/wesnothLearning/training_lite30h_20261025/source && \
  WL_SOURCE=$PWD WL_RUN=$PWD/runs/v5_lite30h_20261025 OMP_NUM_THREADS=1 \
  /home/tongshu/venv/bin/python /home/tongshu/myDev/wesnothLearning/diag_ppo_20261026/<script>.py <args>'
```

Per-probe logs: `/home/tongshu/myDev/wesnothLearning/diag_ppo_20261026/out/<name>.log`.

| Probe | Script (this directory) | Purpose |
| --- | --- | --- |
| a_accounting | `a_accounting.py` | per-format history, counters, BC gate, selection |
| c_replay / c_grad | `c_parity.py` | zero-step replay parity, then per-term gradient decomposition |
| d_batch | `d_batch.py` | batched vs single-row forward equality |
| e_gradpath | `e_gradpath.py` | inference vs differentiable context path, train vs eval mode |
| f_final | `f_final_panel.py` | distinct scenarios behind the 30 final blocks |
| g_independence / g_trend | `g_independence.py` | split independence; validation series |
| h_reward | `h_reward.py` | reward, potential shaping, GAE, truncation oracle |
| i_drift | `i_drift.py` | policy drift across checkpoints on one frozen batch |
| j_prefix | `j_prefix.py` | full-prefix parity for **all** 421 rows |

## Results

### 1. Behaviour reproduction is exact (`c_replay`, `d_batch`, `e_gradpath`, `j_prefix`)

- All 421 rows, histories attached through `learning/sequences.py attach_histories`, model loaded from `<run>/duel/policies/v000099-sample/model.pt`: max `|logp − recorded|` **1.1e-05**, mean ≈5e-07; every history-length bucket 0…18 own turns stays ≤1.077e-05.
- Batching does not perturb logits: batched vs single-row max 3.815e-06; value max 5.96e-08; every ratio mean exactly 1.0000, clip fraction 0.000.
- The differentiable `Policy.context` path and the inference path agree to 0.000e+00 in all four combinations of `train()/eval()` × grad/no-grad; decision-time entropy ≈0.446.
- `learning/model.py` contains no dropout or batch norm, so the mode switch cannot move the forward pass.

**Conclusion:** candidate order, action mask, action index, per-turn memory commit, `log_probability` and `value` are all correct. "The PPO update feeds the model the wrong inputs" is **ruled out**.

### 2. The frozen batch loses 31 % before the update (`c_replay`)

`learning/updates.py prepare()` does `records=[r for r in records if r['split']=='train']` after `attach_histories`. On duel v99 that drops **130 of 421 rows (30.9 %)**, whole games at a time, after the batch identity was already committed. The surviving 291 rows form 6 windows, 2 steps per epoch, 8 planned steps per batch. Results still report `planned_targets` computed from windows, so the loss is invisible in the metrics except as a lower `decisions_seen`.

The cause is that `learning/data.py split()` partitions on `game_family`, and `learning/maps.py decorate()` builds the family from `(format, map digest, seed, factions, teams)` — the seed is inside the family, so the split decision is per *run*, not per *scenario* (see 4).

### 3. Update shape: few steps, KL stop discards the rest (`a_accounting`)

| Format | versions | BC batches | PPO batches | PPO optimizer steps | steps/batch | decisions/batch | exits |
| --- | --- | --- | --- | --- | --- | --- | --- |
| duel | 470 | 40 (1728 steps) | 430 | 1659 | 3.86 (min 1, max 8) | 617 | `kl_stop` 387, `completed` 43 |
| ffa4 | 213 | 80 (3916 steps) | 133 | 480 | 3.61 | 726 | `kl_stop` 133, `completed` 0 |
| team2v2 | 136 | 50 | 86 | 523 | 6.08 | 1638 | `kl_stop` 86, `completed` 0 |

`learning/ppo.py` measures the approximate KL *before* `optimizer.step()` and, when `kl > 0.02`, restores the RNG state and returns `kl_stop` **out of the epoch loop**. Windows that were planned but not visited are never revisited: `finish_train` clears `pending_train` and increments the version. So of roughly 8 planned optimizer steps per duel batch, 3.86 commit and the rest are dropped on the floor. Observed batch KL in the last duel batches is 0.02112 / 0.02101 — the gate fires by a hair, which is exactly the regime where the remainder is most useful.

Zero-update KL stops do not occur (0 of 430), so the "batch abandoned without any learning" state is not present.

### 4. Scenarios cross the train/validation split (`g_independence`)

48 games per format sampled from the teacher shards (`WL_MAXFILES=24`):

| Format | families spanning both splits | physical scenarios on both splits |
| --- | --- | --- |
| duel | 0 / 48 | **5 of 6** |
| ffa4 | 0 / 48 | **7 of 9** |
| team2v2 | 0 / 48 | **4 of 9** |

The split never leaks a *family*, but a physical scenario (same map, same factions, same opening) appears on both sides whenever the seed changes. Because lite uses `expected_damage_v1` and no combat RNG, a scenario with the same factions and the same deterministic opening is close to the same game, so "validation" is not a scenario holdout. `learning/maps.py decorate()` puts `seed` into the hashed family; `learning/data.py split()` hashes that family string; `validate_record` rejects rows whose `split` disagrees with `split(game_family)`.

### 5. The final gate counts 3–6 deterministic games 5–10 times (`f_final_panel`)

Reading only `<format>/jobs.jsonl`, label prefix `final`:

| Format | jobs | nominal blocks | distinct job signatures | multiplicity | distinct per-block scores |
| --- | --- | --- | --- | --- | --- |
| duel | 60 | 30 | **2** | 15 / 15 | 3 values, period 6 |
| ffa4 | 120 | 30 | **1** | 30 | 3 values, period 3 |
| team2v2 | 240 | 30 | **1** (3 with factions) | 10 / 10 / 10 | 3 values, period 3 |

Mechanism, from code: `learning/maps.py decorate()` selects `SPLITS[format]['holdout'][index % len(names)]` (duel has 2 holdout maps, ffa4 and team2v2 have 1 each) and `learning/schedule.py factions(block,players)` cycles with period 3 at 2 and 4 players. The joint period is `lcm(3, #holdout maps)` = 6 (duel) / 3 (ffa4, team2v2). `learning/evaluate.py comparisons()` then bootstraps over `blocks` (30) while `min_blocks=30` is satisfied purely by repetition. With one deterministic scenario repeated 10 times, the residual variance the interval sees is the variance of 3 games, divided by √30.

`selection.json` records the consequence: duel kept champion v400 because "astra nomination did not pass"; ffa4 kept v100 because the "astra nomination panel incomplete"; team2v2 kept v100 because "astra nomination did not pass". The three "latest" versions 470 / 213 / 136 were never selected.

### 6. No version ever beats the panel opponent (`g_trend`)

`difference = policy − control`, from `<format>/validation/v*.json`:

- duel, 47 points v10…v470: **never positive**; non-promotion points are `blocks 3`, differences −1.0…−3.0; v330/v360/v380 "inconclusive"; promotion points (12 blocks) −3.0/−2.0/−1.0/−2.0.
- ffa4, 21 points: v10 +0.125 and v20 +0.042 "passed" (single block), then flat/negative; promotion v100 −0.3194, v200 −0.2361.
- team2v2, 13 points: negative everywhere; the best promotion point is v100 −0.6250, which is why v100 is the selected 2v2 checkpoint.

So `status=passed` on the trend panel is one deterministic game, and the 12-block promotion panel is 4 distinct duel / 3 distinct ffa4-and-2v2 games.

### 7. The policy does move; the direction is not strength (`i_drift`)

Full-distribution KL over all finite logits, 291 usable rows of duel v99, reference v10 (entropy 0.9402):

| Checkpoint | entropy | KL(v10 ‖ vN) | decisions with changed argmax |
| --- | --- | --- | --- |
| v100 | 0.4338 | 3.0627 | 27.84 % |
| v200 | 0.7132 | 2.3908 | 31.96 % |
| v300 | 1.0063 | 2.3945 | 34.71 % |
| v400 | 1.3167 | 1.7336 | 32.99 % |
| v470 | 1.3277 | 1.7474 | 33.68 % |

PPO changes roughly a third of the decisions and pushes entropy up from 0.43 to 1.33 while no panel improves. "PPO is not updating" is **ruled out**; "the update optimises something other than the measured objective" stands.

### 8. Gradients are coherent, and the rehearsal term points at the opponent (`c_grad`)

Same 194-decision batch (`duel` v99), per-term decomposition:

| Term | loss | grad norm | cos with policy term |
| --- | --- | --- | --- |
| policy (clipped surrogate) | +0.000830 | 10.44 | — |
| value (0.5 MSE) | +0.306248 | 2.09 | −0.0202 |
| entropy (−0.01 H) | −0.004171 | 0.066 | −0.0821 |
| rehearsal (0.10 CE) | +0.040574 | 2.457 | **+0.1006** |

No pair of terms is collinear, the PG term dominates, clip fraction is 0.0, weighted entropy 0.417, value MSE 0.612, `|old logp|` mean 0.447 (max 4.41), advantages mean −0.1954 / std 1.1655. The rehearsal pool is the Astra teacher shard, and the evaluation control is also Astra, so the update carries a permanent 10 % pull toward the policy it is scored against — small in norm, aligned rather than opposed.

### 9. Reward, shaping, truncation and GAE match the design (`h_reward`)

4 games / 421 rows / 0 truncated rows. The shortest `(game_id, side)` sequence (36 rows, turns 1–5, terminal +1.0) was recomputed by hand: per-decision potential shaping, own-turn `turns` deltas, GAE λ=0.95 with γ=1, terminal drop of the next potential and the truncated-bootstrap branch all match `learning/rewards.py transition_reward` + `learning/data.py advantages` exactly. **Reward wiring is ruled out as a defect.**

Two property notes, not defects:

- the row field `reward` is the *game's* terminal reward stamped on every row; `advantages` reads it only at the terminal row, and `grep -rn "\['reward'\]" learning/*.py` finds exactly one consumer (`learning/data.py:236`), so it is a misleading name with no current arithmetic consequence;
- with γ=1 the potential terms telescope, so the dense economy/control shaping sums to `Φ_end − Φ_start` over an episode and the only durable signal is the ±1 terminal plus the exploration bonus (measured 0.15→0.574 of its 1.0 bound, i.e. ≈0.042 total at coefficient 0.10). That is policy-invariant shaping by construction — correct, and also the reason credit assignment rests almost entirely on the terminal outcome.

### 10. The BC gate measures in-distribution imitation, not play (`a_accounting`)

`bc_gate.json` for duel: action coverage 0.9903 (30750/31050), recruit 0.9899 (4900/4950), move 0.9967, attack 0.9748; imitation accuracy 0.99193, cross-entropy 0.02731. team2v2: coverage 0.9893, recruit 1.0000, imitation 0.8663, attack 0.7925 (126/159), recruit accuracy 0.9302 (**40/43**). ffa4: coverage 0.9762, attack 0.9305, imitation 0.9127, recruit 0.7563.

These are accuracies on teacher-generated states. The same policy loses every validation panel (section 6), because play visits its own state distribution. The gate therefore cannot see the failure it is trusted to bound — it is a corpus-fit check, and reporting it as evidence of playable policy quality overstates it.

### 11. Stock 1.18.8 RCA observability (`installed data`, static)

From `.runtime/install/share/wesnoth/data`:

- `vendor/arena/match.py` runs `bot == 'baseline'` as `--controller <side>:ai` with **no** `--ai-config` — the built-in default RCA — while contestants get `--ai-config <side>:~add-ons/arena_runtime/side<side>.cfg`.
- `core/macros/ai_candidate_actions.cfg` declares 19 default candidate actions: 9 `engine=lua` with `location="ai/lua/ca_*.lua"`, and 11 `engine=cpp` including `AI_CA_COMBAT` (`ai_default_rca::combat_phase`) and `AI_CA_RECRUITMENT` (`default_recruitment::recruitment`). **Attacks and recruitment are C++**, so no Lua `location=` wrapper can observe them; only 9 of 19 candidate actions are wrappable.
- The stock stage is a fixed-priority list (`AI_CA_*_SCORE` 200000…1000), not a sampled distribution.
- A side addon *can* observe every side's actions through game events: `core/macros/deprecated-utils.cfg:164` uses `name=moveto,recruit,recall,attack,post advance,side turn` with `[filter] side=…`, and `core/macros/side-utils.cfg:61` uses `name=recruit` with `$unit.type`. So event-based capture does not depend on the side being driven by our Lua controller — only on an addon being loaded in the game.
- `learning/native_rpc.lua teacher()` requires `~add-ons/gpt6astra/lua/<strategy>.lua` and returns `probe.plan`, i.e. a native host still calls Astra for teacher queries.

No native game was played in this run: all 2562 duel / 1568 ffa4 / 1328 team2v2 jobs carry `engine lite-0.2` and `native_timings: []`.

## Reuse

Reused without rerun: the frozen run's own outputs (`state.json`, `history`, `jobs.jsonl`, `validation/`, `selection.json`, `bc_gate.json`, checkpoint files) and the export identity in `verification/lite_export_20261026/REPORT.md`; the static call-site anchors of `verification/ppo_static_review_20261026/REPORT.md`; the 10.15 V1–V6 repair acceptance for KL traversal, counter settlement, BC cancellation RNG, final nomination and reward rolling window. Those repairs are treated as in force; nothing here re-asserts them as broken.

New checks were added only where they discriminate between competing hypotheses: batch accounting, split independence, panel multiplicity, reward oracle, drift, gradient decomposition, stock-RCA capture surface.

## Failure

Probe-side errors, all fixed before the reported runs; they did not affect frozen data:

1. `rowpack.unpack_line` returns `(row, bytes)` → first run died with `AttributeError: 'tuple' object has no attribute 'get'`.
2. Per-term backward through one graph → `RuntimeError: Trying to backward through the graph a second time`; each term is now re-forwarded.
3. Unioning per-term gradients → `RuntimeError: The size of tensor a (731249) must match the size of tensor b (268913)`; zero-filled union added.
4. The first gradient probe printed `ratio mean 28.30`; that was a weighting bug in the statistics block, refuted by `clip fraction 0.0000` and by `d_batch`/`e_gradpath` (ratio exactly 1.0000). Recorded so the number is never cited.
5. The first `i_drift` draft printed `|logp − recorded| mean 1.6226` and `entropy 2340`: it compared *other* checkpoints against v99's recorded logp and had a wrong entropy expression. Rewritten to full-distribution KL plus argmax agreement.
6. An early `grep` for `learning/collector.py` returned nothing because that file does not exist; the Lua collector is `learning/native_rpc.lua`'s sibling `lua/collector.lua` path referenced from `vendor/arena/match.py`.

## Gate

No gate was changed, relaxed or reinterpreted. BC gates, PPO KL limit 0.02, promotion, champion and final acceptance all stand as frozen. This report claims no strength, no convergence and no acceptance: it establishes which mechanisms are defective, correct, or still unknown.

## Limits

- Only `duel` version 99 (4 games, 421 rows) was fully instrumented; `ffa4` and `team2v2` were checked at the accounting/panel level only.
- Parity, drift and gradient results are CPU float32 with batch size ≤64; a different `micro`/`sequence_count` would change only numerics, not contract.
- The panel multiplicity analysis relies on identical `map`/`factions`/`rotations`/`turns` in `jobs.jsonl`, because per-job seeds are not persisted there; identical scores plus identical structure is strong but not a stored-seed proof.
- No native game was run, so the stock-RCA capture route (event-based) is supported by shipped data content, not yet by an executed scenario.
- Nothing here shows how much strength the proposed rebuild would recover; that requires the separately authorised training run.
