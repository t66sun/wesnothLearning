# Spatial and history information: paired public-state diagnosis

Investigation for [#229](https://github.com/t66sun/wesnothLearning/issues/229).
Two bounded spatial losses are demonstrated. A fully known map pair has different
ground connectivity but **identical complete actor input**. A second pair has
different board tensors but is indistinguishable after the current convolution
and mean-pooling encoder in real arithmetic. Existing local, entity and knowledge
inputs distinguish the compensation controls. No network or training code changed.

The fixtures do not establish which recruit wins a match, the frequency of either
case in the training corpus, or an effect on trained strength. The history fixture
shows an actual omission of within-turn move order, without demonstrating harm.

## Method and source boundary

The primary sources are the current shared [Lua spatial capture](../../lua/spatial.lua#L34),
[legal observation](../../lua/observation.lua#L43),
[Python encoder](../../learning/model.py#L47),
[history attachment](../../learning/sequences.py#L57) and
[online memory commit](../../lua/relational.lua#L140). Exact file hashes are in
[results.json](results.json). The source is
`815105aab7d8552eb6b957e3b488b990496c0ae1`, based on
`ad7256e838fa941d76d92bf5d56a4683f75b37cd`.

[fixtures.py](fixtures.py) constructs six small spatial pairs and legal synthetic
move-order traces. It uses the real Rust/Lua host and candidate generator with a
declared synthetic rules catalogue. Ground units pay 99 on water and have maximum
movement 5; the water-capable Ghost pays 1. Both rules and all initial specifications
are retained in [paired_fixtures.json](paired_fixtures.json), along with complete
actor rows and raw memory writes. These are fixtures, not native-rule acceptance.
The last-seen control uses the existing deterministic public-view Lua API double.

Main spatial pairs have no fog or shroud: every terrain difference in their
connectivity/location witness is public. The hidden-truth negative control is
explicitly separate. Its differing scenario tiles are test setup, never appended
to actor rows. No referee snapshot, teacher action, reward, or hidden unit is added
to model inputs. Candidate intents and every tensor returned by the real `batch()`
are compared, including entity coordinates, actor/target gathers and local patches.
Histories and current turn are equal in the main spatial pairs.

## 1. Exact input collision: a public route opens or closes inside one bin

The map is 32 by 16. All tiles at x=20 form a water barrier except the alternate
gap at y=8. The only two changed tiles are in one board bin:

| Public tile | Open map | Closed map |
| --- | --- | --- |
| (19, 8) | water `Ww` | grass `Gg` |
| (20, 8) | grass `Gg` | water `Ww` |

`spatial.capture` adds each tile's nine channels into
`floor((x-1)*16/width), floor((y-1)*16/height)` and divides by the same bin-area
factor. Swapping these two tiles leaves every bin sum unchanged. Both are known,
visible, unoccupied, non-village and non-castle; water and terrain-ID contributions
are permuted, not changed. [Exact aggregation](../../lua/spatial.lua#L51)

The public hex-graph witness is a route from (4,8) to (28,8):

| Movement capability | Open map | Closed map |
| --- | ---: | ---: |
| Ground, water inaccessible | 24 hex steps | unreachable |
| Water-capable | 24 hex steps | 24 hex steps |

This witness measures terrain connectivity, not combat outcomes or a full game
planner. It is relevant to future recruit mobility: both maps offer the same
**seven legal retained choices**, including ground/water-capable recruits and
end-turn. It is not a forced single-action state.

Every actor tensor is exactly equal, and the complete serialized actor rows share
SHA-256 `709e2148c64f8395760d02416df9a21e9966a1c76f57d02c7473fc5554701120`.
Entity coordinates, global/opponent summaries, candidate tactical features and
19-hex local patches do not compensate in this fixture: the changed gate is far
from the units and all current candidate destinations. **Any policy receiving
these identical inputs must assign the same conditional action distribution.**
This establishes loss of publicly available, movement-relevant topology; it does
not prove that the optimal current recruit differs or that this causes observed
training weakness.

## 2. Encoder collision: distant terrain location disappears in mean pooling

On a 16 by 16 map, a single publicly known hill moves from (8,5) to (8,11).
Its public hex distance from the own leader at (2,5) changes from 6 to 9.
Both sides again have seven equal candidate intents. The complete tensors differ
only in two elements of the board's terrain-ID channel. The board input is thus
**not** identical; all other model inputs are equal.

The network uses two 3x3, stride-one, padding-one convolutions with ReLU, followed
by a global mean. Each output cell is a shared function of a 5x5 raw patch. To
account for the actual first-convolution boundary and the second convolution's
zero padding, the diagnostic includes a board-validity mask in each patch's
comparison signature. The two boards have exactly the same multiset of these
boundary-aware 5x5 patches. The changed hill is separated from units, candidate
patches and boundary interactions. [Actual convolution/pooling](../../learning/model.py#L58)

Therefore, for **any convolution weights in real arithmetic**, corresponding
patches produce the same outputs and the global mean is equal. Since the other
scene/action/history inputs are equal, the encoder and resulting policy cannot
retain this location distinction. This is a structural argument, not an inference
from untrained predictions. Two deterministic coefficient sets provide only an
arithmetic sanity check: maximum double logit differences are `1.39e-17` and
`6.94e-18`, and both value differences are zero. Floating-point reduction order
means this argument does not promise bitwise equality for all weights/devices.

The location is public and potentially relevant to route or defensive planning.
No outcome label or optimal-action oracle is supplied, so tactical harm and
corpus prevalence remain unmeasured.

## 3. Compensation and negative controls

| Pair/control | Board alone | Other inputs / conclusion |
| --- | --- | --- |
| Nearby hill swap (5,8)/(6,8), same bin | identical | 8 local-patch elements differ; complete actor inputs distinguish it |
| Visible enemy moves (25,8) to (26,8), same bin | identical | entity x-coordinate and opponent-distance inputs differ |
| Known terrain under fog versus unexplored terrain | different | known/visibility and local channels preserve available knowledge |
| Previously seen enemy at (6,4) versus (7,4), now fogged | identical current board | last-seen entity x-coordinate differs; stored age is retained |
| Different gate terrain entirely under unexplored shroud | identical complete actor inputs | correct partial observability, not an encoding defect |

These controls prevent treating a board-only match as a complete-policy alias.
The known/visible channels and last-seen entity memory are active compensation,
not missing mechanisms. [Known terrain and stale entities](../../lua/spatial.lua#L40),
[candidate geometry/local patches](../../lua/spatial.lua#L74).

All **439** declared terrain vocabulary entries, including the unknown entry,
have distinct float32 normalized scalars. The smallest adjacent difference is
`0.0022830963134765625`. Thus this diagnostic finds no single-tile collision among
declared terrain IDs. Treating categories as ordered scalars imposes an arbitrary
numeric relationship, but that is an inductive-bias concern, not itself proof of
information loss. A categorical embedding alone would not undo a permutation
inside the existing symmetric board-bin sum.

## 4. History: what is omitted, retained and differentiated

Two traces perform the same first legal own move, then swap the order of two
independent legal own moves. All six moves commit successfully through the shared
Lua executor. Intermediate public entity positions differ; final current actor
tensors and the first post-action memory observation are identical. Attaching the
complete raw traces retains exactly one turn-1 memory write in both cases.
Therefore, the later move order is absent from the recurrent history. The fixture
has no opponent action between those independent moves and establishes no harmful
future consequence; it is evidence of the sampling boundary, not a reason to
increase memory frequency. [One write per turn](../../learning/sequences.py#L82),
[post-action source](../../lua/bot.lua#L62).

The three time scopes remain distinct:

| Scope | Observed assertion |
| --- | --- |
| Available raw history | 40 supplied own-turn scenes are encoded; the first raw scene remains present |
| Differentiable recurrent suffix | 32 prefix GRU steps run without gradients, then 8 with gradients |
| Attention summary storage | at most 32 summary slots; older history can still affect the GRU prefix |
| Reward credit | on a 12-own-turn algebra fixture with zero intermediate rewards/values and terminal reward 1, first advantage is `0.95^11 = 0.5688000922764596` |

The 40-turn fixture repeats a legal public scene with explicit turn indices to
audit replay mechanics; it is not a newly played 40-turn trajectory. The reward
fixture is algebra on the baseline's existing GAE implementation. Neither eight
differentiable turns nor 32 slots defines a hard reward-credit horizon. No claim
is made that learned weights actually retain useful information for 40 turns.
[Replay boundary](../../learning/model.py#L76), [GAE recurrence](../../learning/data.py#L309).

## 5. Consequences and bounded repair costs

There is now a concrete follow-up target for spatial encoding. It is not necessary
to enlarge every model or add search to demonstrate the loss.

| Finding | A bounded direction to test later | Required cost / limitation |
| --- | --- | --- |
| Within-bin order/topology lost | preserve ordered subcells or a full-resolution public map | changes feature/checkpoint contract and Lua/Python parity; this 32x16 map has twice the cells of 16x16, before any other change |
| Mean pool loses distant location | retain position in the spatial read or test coordinate-conditioned features | changes model/export contract and requires new weights; breaking this symmetry does not establish better planning |
| Terrain scalar remains injective | a category representation could alter inductive bias | increases input/embedding state; does not recover already-aggregated order |
| Later within-turn writes omitted | no change justified by this harmless order fixture | per-action writes would change replay/commit semantics; this example would use three writes instead of one |

These are scope/cost descriptions, not measured performance claims or a chosen
implementation. The next spatial change should address one demonstrated collision
and preserve candidate/visibility contracts, then be evaluated separately. This
investigation does not select a training hyperparameter or authorize a new run.

## Execution and artifacts

The committed source was shipped with `git archive` and `scp`, then extracted to
`/home/tongshu/acceptance/representation_information_20261106_815105a/source`.
Archive SHA-256:
`8f9b9056d5a1217b426b069e129d7835a97f0f21282299865543ae20909cbf23`.
Ubuntu Python 3.12.3 and Torch 2.9.1+cpu used the existing compiled extension and
compiled rule vocabulary. Rules SHA-256 is
`e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`.
All probe assertions passed on the first execution, exit 0: [probe.log](probe.log).
No optimizer, training run, match runner or corpus collection was used. No Windows
tests or throughput measurements were performed. Production code and frozen inputs
remain unchanged; synthetic states are confined to this evidence directory.

From the fresh source directory:

```bash
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$PWD:/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension"
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
/home/tongshu/venv/bin/python verification/representation_information_20261106/probe.py ../evidence_NEW
```

The output directory must not exist; reproduction never overwrites evidence.
The source links `data/rules/1.18.8` to the existing map directory
`/home/tongshu/myDev/wesnothLearning/WesnothLearning/rules/1.18.8`.

| Artifact | SHA-256 |
| --- | --- |
| `paired_fixtures.json` | `cb6cabda2f2a47b9deda38628e8c6959601d9887f711e04d28482089ea1ba74a` |
| `results.json` | `ad1fb2cd7a2ff03a5ac9c81548c730f783053c7b1b0ea04c2686038c5aa67351` |
| `probe.log` | `a7172a5fa34e4cd11f7067a6ecef31584110fad93e12c86c0f55cbc526bec163` |
