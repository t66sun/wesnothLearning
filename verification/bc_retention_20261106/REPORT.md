# Frozen BC retention: diagnosis and a bounded implementation direction

Research for [#225](https://github.com/t66sun/wesnothLearning/issues/225).
The implementation remains historical hard-action rehearsal. This investigation
defines what a BC retention mechanism would preserve and measures its proposed
signal on frozen inputs; it does not enable that mechanism in PPO.

## Finding and interpretation

The current auxiliary loss is `0.1 * CE(current_logits, historical_action)`.
Its reference is the distribution that generated the sampled policy actions,
not necessarily the BC endpoint. In expectation, hard-action replay from a
policy mixture minimizes its cross-entropy with the current policy. That can
stabilize recent behavior, but it has no explicit fixed BC reference.

This is an intentional source boundary, not a reason to remove the filter.
[`finish_train`](../../learning/experiment.py) passes the evaluation-control
identity into [`BCSampler`](../../learning/data.py), which excludes matching
teacher implementation or label-source hashes. The formal run supplies no
human replacement: all 902 duel and 231 team PPO batches report policy-only
rehearsal. Original teacher and DAgger rows are still read before exclusion.
[Original census and exact loss path](../ppo_architecture_audit_20261106/REPORT.md#3-rehearsal-preserves-historical-policy-labels-not-the-bc-teacher),
[`ppo.update`](../../learning/ppo.py).

The quantity to preserve is the **BC endpoint's conditional action distribution
over the retained legal candidates, given legal visible observations and raw
history**. This covers recruitment, movement, attack and ending a turn within
the current representation. It does not preserve omitted candidates, solve a
weak BC policy, or establish that copying BC increases strength.

## Frozen-input method

`probe.py` loads the existing `last_bc.pt` per format as a frozen anchor and
does not construct an optimizer. It loads the selected and latest complete
checkpoints, plus the policy exports that actually generated the first and
last complete PPO batches. The run is
`/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/runs/formal_30h_scratch`.

- Behavioral diagnostics use at most 512 teacher-validation rows per format,
  selected with the existing bounded reader and seed 20261017. Teacher choices
  are not targets for the comparison or any gradient. The metrics compare
  policy distributions, including KL, total variation, top-choice agreement,
  probability of the BC choice, action kinds and the through/after-30-turn split.
- Each early/late training cohort uses 128 evenly spaced decisions from the
  original policy batch. A separate 64-row gradient sample uses advantages
  normalized on the **full** original batch. This is a diagnostic sample mean,
  not the production equal-window optimizer objective.
- Rehearsal reconstructs the original bounded pool at that version: train-only,
  2048-row limit, seed `20261017 + policy_version`, no later rollout shards.
  `BCSampler` applies the existing control exclusions, then the probe uses the
  same 64 sampled policy states for hard-action CE and frozen-BC distribution KL.
  This isolates the auxiliary target, rather than comparing different states.
- Each policy re-encodes the complete raw history with its own weights. Anchor
  caches and student caches are separate; cached hidden states are not exchanged.
  Only the existing legal `batch()` input reaches either policy. Reward/advantage
  labels are used solely in loss diagnostics, not as policy inputs.
- Weight digests are checked before/after inference and backward, anchor
  parameters receive no gradients, training states must be policy/train, and
  held-out rows never enter gradient calculations. JSON records pin all source
  files and checkpoints. The probe never rewrites them.

The production loss, model, feature, sequence, update and export files used by
this probe are byte-identical between the formal source `d2e6da5` and the current
baseline `cc28f23`. The historical run still has a 60-turn continuation objective;
these gradients do not simulate the future 30-turn objective from #235.

## Measurements

Both formats completed on Ubuntu. Every reconstructed early/late rehearsal pool
matches the original log's source identities and excluded-row count: 1024 of the
2048 returned rows are excluded, and the sampled auxiliary states are policy-only.
All weight/source-isolation assertions in the probe pass.
[Duel JSON](duel.json), [team JSON](team2v2.json),
[duel execution](duel.log), [team execution](team2v2.log).

### Conditional behavior, not a strength score

| Format / checkpoint | KL(BC \|\| policy), nats | Total variation | BC top-choice agreement | Policy entropy, nats |
| --- | ---: | ---: | ---: | ---: |
| Duel BC v38 | 0 | 0 | 100% | 0.318 |
| Duel selected v100 | 0.215 | 0.139 | 86.13% | 0.398 |
| Duel latest v940 | 0.641 | 0.385 | 74.61% | 1.225 |
| Team BC v53 | 0 | 0 | 100% | 0.808 |
| Team selected v100 | 0.189 | 0.185 | 82.23% | 1.062 |
| Team latest v284 | 0.381 | 0.305 | 73.83% | 1.446 |

Each format has 512 decisions from 16 games. These span only **five duel and
eleven team physical scenarios**, so decisions are not independent strength
observations. This smaller, fixed sample is not the old 2048-row teacher-label
probe or the BC gate. Its scores measure agreement with BC, not teacher accuracy.

All duel rows occur through turn 30. Of the team rows, 352 occur through turn 30:
their latest KL is 0.405, TV 0.316 and BC top-choice agreement 72.73%. The other
160 rows have KL 0.327 and agreement 76.25%. Drift is therefore present within
the official horizon, not just in the discarded late-game portion.

The JSON also separates action kinds by the **BC model's** preferred action.
Examples: latest duel agrees on 53.66% of 41 attack choices and 74.51% of 102
recruit choices; latest team agrees on 62.16% of 37 recruit choices and 66.07%
of 56 end-turn choices. These small, correlated strata identify behaviors to
monitor; they do not rank their usefulness. The current 37-candidate cap remains
part of this conditional comparison.

### Auxiliary gradient on the same eligible self-policy states

All norms include the applicable coefficient. `Actor` is the unclipped/clipped
PPO policy term at the recorded pre-update weights; value uses 0.5, entropy 0.01,
and either auxiliary target uses 0.1. No optimizer step is taken.

| Format / pre-update version | Actor norm | Value norm | Historical-action auxiliary norm | Frozen-BC auxiliary norm | Historical auxiliary vs actor cosine | BC auxiliary vs actor cosine |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Duel v38 | 10.643 | 2.033 | 0.750 | 3.25e-7 | +0.124 | undefined at numerical zero |
| Duel v939 | 3.845 | 2.897 | 0.508 | 0.484 | -0.116 | -0.154 |
| Team v53 | 5.682 | 0.622 | 0.616 | 1.53e-7 | -0.107 | undefined at numerical zero |
| Team v283 | 6.770 | 1.710 | 0.826 | 0.722 | +0.200 | +0.223 |

At the BC endpoint, the proposed loss has the expected near-zero signal, while
the finite hard-action sample still moves the policy. Later, the two auxiliary
norms are comparable but their directions differ: their mutual cosine is 0.529
in duel and 0.809 in team. The anchor/actor relationship is negative in late
duel and positive in late team; this does not support claiming the auxiliary
always dominates or always fights PPO. Late BC-anchor norms are about 12.6%
and 10.7% of actor norms in these two samples.

Raw JSON retains float32 calculations, including tiny norm/cosine roundoff;
identity self-cosines overshoot 1 by less than 0.00009. The near-zero BC-start
cosines are not interpreted. No population confidence interval, optimizer
trajectory, training speedup or strength effect is inferred from these four
gradient samples. Their value is that the candidate provides a different,
measurable retention signal at a comparable diagnostic scale.

## One proposed change: replace self-replay targets with frozen BC probabilities

Use the same eligible policy rehearsal states and quotas, but replace the
historical single action target with:

```text
q = stop_gradient(softmax(last_bc(legal_observation, raw_history, candidates)))
L_aux = beta * mean(KL(q || current_policy))
```

Apply the existing logical-window/microbatch weights around this term. The
diagnostic uses `beta = 0.1` for a direct target-only comparison; it does not
establish 0.1 as a good training coefficient. No value-head distillation is
proposed. The shared representation can still receive both value and policy
gradients. The frozen anchor needs an extra inference pass; efficiency results
for the old loss are not a measured cost estimate for this new loss.

The important semantic difference is testable: when the student equals the
anchor, distribution KL and its gradient are zero, whereas a finite sampled
hard-action CE usually still has a gradient. Later, this anchor opposes drift
from the **same BC endpoint**, not drift from an evolving mixture of PPO actions.
It can also oppose useful improvements, so behavioral similarity alone cannot
be its acceptance criterion.

### Allowed origin and evaluation relationship

This is explicitly qualified **self-policy distillation** under
[#60](https://github.com/t66sun/wesnothLearning/issues/60): use the student's own
frozen, complete BC endpoint, not the control implementation or its online
labels. The BC endpoint's Astra initialization lineage remains recorded; this
does not manufacture an independent teacher or an unseen evaluation opponent.
No Astra label becomes eligible by renaming its source.

For the first implementation, limit states to the currently supported,
provenance-bearing policy/train replay stream. Preserve control implementation
and source-hash exclusions, faults/schema checks and physical scenario splits.
Held-out teacher states remain diagnostics. Native/human expansion and a new
teacher are separate decisions, not prerequisites for this candidate.

Freeze the chosen endpoint at the BC-to-PPO boundary. Record its checkpoint and
parameter hashes, format/schema/feature/architecture identities, parent-run
lineage, coefficient and target mode in the existing run/checkpoint contract.
Resume must restore the same anchor and reject a missing or mismatched anchor
before updating. Do not silently repoint it to a later `last_bc.pt`, retarget a
historical manifest, or substitute the selected/latest PPO policy. A forced
PPO start without a qualifying BC endpoint cannot claim this retention mode.

### Minimal implementation boundary

The existing manifest/phase-boundary code owns the frozen target identity;
`FormatExperiment.finish_train` owns loading/passing the model, and `ppo.update`
owns the auxiliary loss. Keep the existing sampler and stopping contract.
An optional target mode is enough; this does not require a new training framework,
teacher plugin, candidate/model change, or another policy pool.

Do not combine this change with disabling DAgger, removing rejected source reads,
changing the KL limit, rollout count, learning rate, reward objective or model.
The old control exclusion still has a purpose. #226 separately measures the
unconsumed-label/read cost; #235 separately aligns the objective.

## Acceptance for that later implementation and experiment

1. Synthetic Ubuntu assertions must cover exact zero at the anchor, forward-KL
   direction, finite gradients with padded candidates, detached/frozen target,
   independent recurrent histories and preservation of the existing control
   exclusions. A full runner/resume fixture must pin the anchor and coefficient,
   reject changed/missing identity before an update, and keep #56's KL batch
   settlement unchanged. The present three algebra tests do not implement those
   future runner/resume fixtures.
2. In a separately authorized, bounded comparison, start both arms from the same
   accepted BC checkpoint. Keep the 30-turn objective, scenario schedule, seed
   sets, PPO parameters and evaluation design equal. The only difference is the
   eligible replay target: historical action versus frozen BC distribution.
   Record actual games, independent scenes, committed steps and total cost so
   fewer updates due to anchor inference cannot be mistaken for retention.
3. Report train and held-out BC-distribution KL/TV, per-kind behavior, through-30
   turns, plus separate actor/value/auxiliary gradient norms and cosines at fixed
   checkpoints. These diagnose retention and interference; there is no universal
   acceptable KL or cosine threshold established here.
4. Decide usefulness using the official 30-turn **own-points** metric and matched
   BC/latest comparisons from #222, with at least 12 distinct validation scenes,
   full seat/teammate contexts and scenario-cluster intervals. Require evidence
   that retaining behavior also retains/improves useful performance; a similarity
   increase alone is insufficient. Freeze any non-inferiority margin and the
   experiment's improvement criterion before collecting its games. Holdout stays
   independent of coefficient selection.

The already recorded real matches remain inconclusive: latest minus BC own score
is -0.083333 for duel (95% interval [-0.319444, +0.152778]) and +0.017361 for team
([-0.065972, +0.093750]). No new matches were played for this issue.
[Recomputed paired evidence](../paired_progress_20261106/REPORT.md#read-only-recomputation-of-real-recorded-matches).
Distribution drift therefore does not prove strength regression, and this
proposal does not yet prove improved retention or PPO strength.

## Verification and reproduction

The diagnostic source is **`7432fae8be520c96fe04b474bd1bf5627307dfab`**,
archived from branch `codex/issue225-bc-retention`, transferred by `scp`, and
extracted into the fresh Ubuntu directory
`/home/tongshu/acceptance/bc_retention_20261106_7432fae/source`.
Python is `/home/tongshu/venv/bin/python` (3.12.3); Torch version is recorded in
each JSON. The existing compiled rules are
`/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered`,
SHA-256 `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`.
The already provisioned extension is inherited through the formal source's
`.extension` path; no build or game execution is part of this check.

From that extracted source directory:

```bash
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PWD:/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension"
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
python=/home/tongshu/venv/bin/python
run=/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/runs/formal_30h_scratch
"$python" -m unittest discover -s verification/bc_retention_20261106 -p test_probe.py -v
"$python" -m unittest tests.v5.test_rehearsal_source -v
"$python" verification/bc_retention_20261106/probe.py "$run" ../duel.json --format duel
"$python" verification/bc_retention_20261106/probe.py "$run" ../team2v2.json --format team2v2
```

The fresh archive also links `data/rules/1.18.8` to the existing map directory
`/home/tongshu/myDev/wesnothLearning/WesnothLearning/rules/1.18.8`.
The output paths must be new: the probe opens them exclusively.

- **Three analytical loss checks pass**, 0.003 seconds: zero loss/gradient when
  matching the anchor (and nonzero hard-action gradient), the analytic soft-target
  gradient with candidate padding and no anchor gradient, and forward-KL direction.
  [algebra.log](algebra.log), [test_probe.py](test_probe.py).
- **Six existing source-isolation checks pass**, 1.569 seconds: control-only
  rejection, eligible self/human replay, source-hash versus environment provenance,
  and the disabled-auxiliary case. Their synthetic temporary model updates are
  unit fixtures; no formal-run policy or optimizer is changed.
  [source_filter.log](source_filter.log).
- Both frozen probes exit successfully; all four training-cohort pool/log
  comparisons and all frozen-weight, no-anchor-gradient and source assertions pass.
  Input identities cover 7,528 files for duel and 2,260 for team. Production source,
  frozen input data, manifests and old verification reports were not edited.

| Output | SHA-256 |
| --- | --- |
| `duel.json` | `be2fed82e8bad0515ae7f09c3287b7ffcea58ffd253dbf7aa36fbff7b1b17183` |
| `team2v2.json` | `b130ca38213cc6d74f2b80c6d228ca5cdec201dc76d8c461348e783d12dcc8d5` |

Implementation of the proposed objective and its runner/resume assertions is
future work. Nothing from this research is entered in TEST.md as an implemented
production change awaiting acceptance.
