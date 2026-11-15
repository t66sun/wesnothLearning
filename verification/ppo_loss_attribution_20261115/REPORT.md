# PPO loss attribution on frozen proposals

Ubuntu cpuServer, 2026-11-15. [#357](https://github.com/t66sun/wesnothLearning/issues/357) · [#352](https://github.com/t66sun/wesnothLearning/issues/352) · [Frozen #356 replay](../ppo_diag_capture_20261115/optimizer-probe.json)

## Decision

The entropy term reduced the margin of actions with positive complete-return credit on Weldyn Channel in all 18 matched-KL proposal comparisons across the three PPO histories. On Fallenstar Lake only 11 of 18 comparisons pointed in that direction and the mean margin effect reversed. Removing entropy changed the pooled positive-action log-probability by just +0.00000036. Critic and actor effects reversed across histories or layouts. Removing historical-action rehearsal worsened the pooled margin while improving the signed return projection. The archive supports local interference and leaves the choice of a production loss change unresolved. The negative projection survives zeroing all current loss gradients at the first boundary. No term is nominated for a score trial.

## Functional effect

A positive omission effect means the reported measure increased when that loss was omitted. The margin is the chosen action logit minus the strongest legal alternative. Positive credit means the archived complete-return advantage at λ=1 exceeded zero using the stored behavior value as baseline. The signed projection uses all sampled rows, including negative-credit rows. A label reflects the observed continuation from the archived game. Paired alternatives at the same decision were not played.

Each aggregate gives equal weight to the three PPO histories, two maps, six proposals and available games within each map. Positive-only measures average within games with at least one positive label. Log-probability, margin, and projection differences below are multiplied by 1,000. The 36 proposal-by-map contrasts reuse the same sets of holdback games.

| Loss omitted | Raw margin | Matched-KL margin | Matched-KL positive log-probability | Matched-KL signed projection | Positive margin folds | Positive margin comparisons |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| actor | +0.350 | +0.151 | +0.2175 | −0.0237 | 3/6 | 22/36 |
| critic | +0.070 | +0.042 | −0.0141 | −0.0013 | 3/6 | 19/36 |
| entropy | +0.182 | +0.153 | +0.0004 | −0.0031 | 4/6 | 29/36 |
| rehearsal | −0.339 | −0.183 | +0.0267 | +0.1677 | 2/6 | 10/36 |

Full proposals averaged **−1.829** in margin, **−1.647** in positive log-probability and **−1.605** in signed projection on the same scale. The largest favorable fold was actor omission in PPO 202611082 on Weldyn, at +5.071 margin units. The same omission was −4.241 in PPO 202611083 on Fallenstar. Rehearsal omission reversed the aggregate direction between margin and projection. Its largest favorable signed projection was on Weldyn in PPO 202611083 while the margin on that fold declined.

| PPO history | Holdback map | Positive-credit coverage | Full raw positive log-probability | Omit actor, margin | Omit critic, margin | Omit entropy, margin | Omit rehearsal, margin |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 202611081 | Fallenstar Lake | 8/58 in 3/8 games | −10.948 | −1.041 | −0.077 | −0.100 | +0.571 |
| 202611081 | Weldyn Channel | 12/59 in 2/8 games | −1.509 | +0.645 | +0.591 | +0.305 | −1.704 |
| 202611082 | Fallenstar Lake | 28/60 in 6/8 games | +0.319 | +0.632 | −0.359 | +0.072 | −0.628 |
| 202611082 | Weldyn Channel | 14/59 in 6/8 games | +2.000 | +5.071 | −0.367 | +0.263 | −0.709 |
| 202611083 | Fallenstar Lake | 8/61 in 3/8 games | +0.547 | −4.241 | +0.137 | −0.087 | +2.859 |
| 202611083 | Weldyn Channel | 7/58 in 2/8 games | −0.289 | −0.163 | +0.329 | +0.467 | −1.487 |

Average entropy-omission margin at equal KL was +0.345 on Weldyn Channel and −0.038 on Fallenstar Lake. The corresponding changes in positive log-probability were +0.040 and −0.040, respectively. The held-back PPO cohort covered 48 games and 355 decisions with at least two legal candidates. Of these, 77 decisions in 22 games met the positive-credit definition.

## Weighted gradient by parameter group

Each cell gives the median L2 norm and the median cosine against the actor for that group over 18 PPO probes. The scorer and local candidate encoder form the policy-only group. The value MLP forms the value-only group. All other parameters are shared. A cosine is undefined if either norm is zero.

| Group | Clipped actor | Critic × 0.5 | Entropy × −0.01 | Rehearsal CE × 0.1 |
| --- | ---: | ---: | ---: | ---: |
| shared | 1.035 / +1.000 | 1.586 / −0.006 | 0.027 / +0.141 | 0.195 / −0.097 |
| policy | 3.944 / +1.000 | 0.000 / — | 0.047 / −0.009 | 0.565 / +0.007 |
| value | 0.000 / — | 0.501 / — | 0.000 / — | 0.000 / — |

The shared critic gradient has the largest median norm. Its actor cosine ranges from −0.418 to +0.211. Removing it moves the positive margin in both directions. A critic change can alter the proposal through the shared trunk and the global gradient clipping, even though its direct policy-head gradient is zero.

## First-step control for inherited Adam moments

The control zeroed every current loss gradient at the exact first #356 boundary, kept the production gradient-presence mask and reused the archived Adam state. It recomputed each proposal and evaluated the same holdback inputs. v38 with empty Adam produced exactly zero weight displacement and policy KL. On the PPO checkpoints the raw moment-only KL was 79.9%, 96.4% and 103.4% of the corresponding full KL.

| PPO history | Holdback map | Full positive log-probability | Moments-only positive log-probability | Full signed projection | Moments-only signed projection |
| --- | --- | ---: | ---: | ---: | ---: |
| 202611081 | Fallenstar Lake | −9.146 | −10.131 | −2.553 | −2.682 |
| 202611081 | Weldyn Channel | −0.348 | −1.648 | −0.234 | −0.753 |
| 202611082 | Fallenstar Lake | +1.866 | +0.864 | −1.077 | −0.929 |
| 202611082 | Weldyn Channel | +2.359 | +2.667 | +0.815 | +1.116 |
| 202611083 | Fallenstar Lake | +4.276 | +0.165 | −3.436 | −3.738 |
| 202611083 | Weldyn Channel | −0.220 | −0.229 | −1.341 | −0.013 |

The table uses equal KL and the same ×1,000 scale. Positive log-probability moved in the same direction in all six history-by-map folds. Signed projection was negative in five of six folds with either proposal. The signed projection averaged **−1.304** for the full first step and **−1.166** for moments alone. The archived Adam state can already produce the negative direction. This control covers the exact first boundary per history. It cannot assign the stored moments to specific past losses. [First-step control](moments.json)

## Inputs and controls

The audit used the #356 The Freelands inputs, checkpoint weights and Adam state, and the exact epoch-zero window order at seed 2026111756. Each probe starts independently from the frozen checkpoint. Step zero reproduces the first production boundary. Later batches replay the frozen order and rehearsal RNG from that same starting checkpoint. No proposal is carried forward to the next batch. At each probe, the production update hook stopped before the first optimizer step and supplied the actual globally clipped gradient. The decomposition matched that gradient with a maximum absolute error of `1.66e−7`. The zero-weight control produced identical tensors in all 24 proposals.

| Checkpoint | Epoch-zero batch indices (zero-based) | Distinct inspected PPO targets | Mean raw post-proposal forward KL |
| --- | --- | ---: | ---: |
| v38 | 0, 1, 2, 3, 4, 5 | 1,343 | 0.005968 |
| 202611081 | 0, 1, 2, 3, 4, 6 | 1,485 | 0.0002020 |
| 202611082 | 0, 1, 2, 3, 4, 5 | 1,649 | 0.0001399 |
| 202611083 | 0, 1, 2, 3, 4, 6 | 1,536 | 0.0001566 |

The actor used the production 0.8–1.2 ratio clip and standardized λ=0.95 advantages. The critic used the production squared value error and entropy was computed over the legal mask. Each auxiliary sample matched the original per-window weighting and the shared 0.5 gradient-norm cap. Adam used `1e−4`, with checkpoint moments for PPO and empty state for v38. The 1,024 replacement rehearsal rows came from the #322 shards frozen in #356. All 6,013 sampled rehearsal visits were original Lite policy rows and the sampler excluded zero rows. The original #306 rehearsal rows are unavailable. This result bounds the replay with the known replacement pool.

The two frozen holdbacks used eight chronological probes per game with forced moves omitted. All proposals use identical recurrent prefixes and masks. Equal-KL comparisons shrink whichever weight displacement has the larger holdback KL to the smaller raw value. The maximum relative match gap was 0.95%. Both raw and matched comparisons are in the result. The initial audit launch exposed a missing legacy import in the Git archive before any probe ran. The same script completed after the archive included that dependency.

## Evidence and replay

The Ubuntu attribution took 411.187 seconds. The first-step control took 80.265 seconds. Both analyses played zero new games and committed zero optimizer updates. Checkpoint and trajectory digests were verified against the existing freeze. Only dated diagnostic evidence was added.

- Frozen replay SHA-256 `36b2cdbb84b1df705d677a2a1dbeca343d7f92b39b7f5ea837454d0939bffad2`. Capture archive SHA-256 `8a21da31be20c4c087aa78d35baa51c06049420a393f63fa18c55cfa72163e3a`. Pinned production `ppo.py` SHA-256 `bd5c45bd60342f0bfab2b0f845e253cdfc272442bd4358a6b311b1c3bec3d752`. [Frozen inputs and runtime](../ppo_diag_capture_20261115/optimizer-probe.json)
- Attribution Git archive commit `0284928f94b31d94a9cc2e46a49f7016d1f298cf` and tar SHA-256 `35fa515526dc6c5d11f36b80825b306169fafc0ba53891bdc49d7ef4142fd12d`. Output SHA-256 `17baf012be74f6b53022b8becda5b1a2001e246a25e55b8c69a5569749d45331` before gzip and `ccc9708d21b1a41828afc777ed90447c49ef47619597c2a792d77e3c551d151b` on disk. [Script](audit.py) · [Per-proposal results](loss-attribution.json.gz)
- Moments Git archive commit `b6ae407f34d3d44a998cb45b6ca04225f3dfe1f0` and tar SHA-256 `63de7da36f3bef4f96ba7ce22d8e5e00e3348f48d6d1dbc52293db9b7e6c8b8a`. Output SHA-256 `325de4fe5f2cee47c15a4dd8e9a0fec79ad15424878e8f0939b01ad61828aca0`. [Script](moments.py) · [First-step scores](moments.json)

```bash
set -eu -o pipefail
base=/home/tongshu/acceptance
source="$base/ppo306_20261108_Miwoyq/source"
extension=/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension
python=/home/tongshu/venv/bin/python
audit=/home/tongshu/acceptance/ppo-loss-attribution-20261115-sSult2
freeze="$base/ppo-capture-review-20261115-QJUU4Z/optimizer-probe.json"
out=$(mktemp -d "$base/ppo-loss-recount-XXXXXX")
export WESNOTH_RULES_DIR="$base/filters_compiled_20261103/data/rules/1.18.8-combat-filtered"
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export PYTHONPATH="$source:$extension:$audit/verification/ppo_diag_capture_20261115:$audit/verification/ppo_diagnosis_20261115"
cd "$source"
"$python" -u "$audit/verification/ppo_loss_attribution_20261115/audit.py" "$freeze" "$out/loss-attribution.json"
"$python" -u "$audit/verification/ppo_loss_attribution_20261115/moments.py" "$freeze" "$out/loss-attribution.json" "$out/moments.json"
```
