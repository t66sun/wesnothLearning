# Integrated Lite worker component costs

On the frozen v10 team validation board, 13,682 hypothetical combat requests used 2.360 CPU seconds. **Two disjoint parts of their preparation used 1.452 seconds**: 0.947 to clone the referee game and 0.505 to materialize the original public roster for two ID checks. The clone then constructs another public roster at the hypothetical landing. Together the measured preparation costs were 8.41% of the 17.269-second instrumented worker. A single original public roster can supply both ID checks and an immutable hypothetical attacker. An isolated public-information test below identifies a correctness condition on that projection. [Raw scope totals, caller edges, payload samples and Python profile](profile-results.tar.gz)

## Component attribution

The table uses thread CPU seconds. Each row's inclusive total includes its arguments, the Rust operation and its result conversion. Scope overhead and dispatch account for the difference. The raw archive records all 74 scopes and 113 caller/callee pairs with call counts, inclusive and exclusive CPU and wall nanoseconds. Nested rows must be interpreted using their parent edges.

| Lua → Rust bridge operation | Calls | Inclusive CPU | Argument conversion | Rust operation | Result to Lua |
| --- | ---: | ---: | ---: | ---: | ---: |
| forecast | 13,682 | 2.360 | 0.025 | 2.238 | 0.064 |
| step | 1,250 | 1.801 | 0.004 | 1.518 | 0.253 |
| reach | 16,639 | 1.216 | 0.020 | 0.994 | 0.161 |
| legal | 1,150 | 0.907 | 0.001 | 0.590 | 0.273 |
| view | 1,031 | 0.327 | 0.002 | 0.097 | 0.208 |
| path | 635 | 0.174 | 0.001 | 0.172 | 0.001 |
| rules | 1 | 0.131 | <0.001 | 0.069 | 0.054 |

| Python extension endpoint, across 1,031 calls each | Lua function | Lua result to JSON value | JSON encoding |
| --- | ---: | ---: | ---: |
| Decision | 10.922 | 0.122 | 0.028 |
| Execute | 2.485 | 0.322 | 0.030 |

Dispatching each action into Lua added 0.004 seconds of JSON decoding and 0.007 seconds of argument conversion. Direct Python JSON decoding of the execution results took 0.147 seconds cumulatively. A sample of returned fields every 64th call measured `view` at 98.4% of Astra execution payload bytes and 70.9% of student execution bytes. The worker reads turn, current side, finish/truncation, winner and side elimination fields. The full execute-side marshalling, encoding and direct Python decoding measured about 0.500 seconds. Lua separately consumes the Rust step's public view to update its own map and units. The timed all-side verification itself accounted for 0.469 seconds in the batch-observe endpoint and 0.595 seconds of Python JSON decoding.

Astra evaluation used 8.606 inclusive CPU seconds. Its context, recruit, threat-map, attack and movement phases used 0.065, 0.908, 1.377, 3.424 and 2.827 seconds respectively. The repeated movement-landing loop used 2.771 seconds inclusive and 2.311 exclusive of the other timed helpers. Public map `find` used 0.872 seconds. Student candidate generation used 1.497 seconds inclusive and 0.864 exclusive. Public observation capture took 0.589 seconds inclusive, including 0.541 seconds in spatial capture. All 128 fp64 tensor choices together took 0.501 CPU seconds. [Detailed profile](profile-results.tar.gz)

## Identical legal inputs, different hypothetical damage

A separate static probe used the official, uninstrumented `7889264` extension and the actual filtered catalog. On a seven-by-seven board, both twin states had deep water at zero-based positions 17 and 6, a visible side-1 Spearman at 22 and a visible enemy Skeleton at 24. The same submerged enemy Death Knight occupied 17 in one twin and 6 in the other. It was absent from both original public views. Neither twin executed an action. Both allowed the movement to 23 and had bit-identical public observations, public legal lists and student scenes before the query.

The same teacher-facing melee forecast from 23 to 24 produced mean attacker HP of **18.0 versus 23.4**. Both defender means were 28.6. Two ordinary generated `move_attack` candidates also differed in `expected_self_damage`, 0.360 versus 0.252. The candidate generator ran before the probe's additional diagnostic query. The old cloned-game projection can reveal a third-party aura donor solely because of the hypothetical landing. The Death Knight is in the catalog and outside the sealed 158-unit training closure. The witness demonstrates a full-catalog public-information defect and does not establish that a historical training trajectory encountered it. [Board specifications, exact probability distributions and candidate differences](hidden-fixture.tar.gz)

The public view hash was `f8fb7cbf21abf2d1e285757dc30699c69b2ed6cdff6efc31b1da8f38a5ee0e6a`; the legal-list hash was `ee07a79494f2d6f76f6bda0af6abbfd26d4bf5f047a59825b2a98c011be5529e`. Both authoritative game snapshots remained equal to their respective pre-query snapshots.

## Reproduction and limits

`cpuServer` received `git archive` of `84e8d63c523166d52932a01690b3b402b4ff6dbd`, archive SHA256 `fa46c7d52af5ffa40cd878cce719ac3be2eb7c933a8333dcbbe7baf6a7cd1b2d`, which adds only diagnostic sources to integrated `7889264e74a5151ebd21d7185f7b220662818c37`. `prepare.py` copied that exact crate into a separate directory and added timers there. The release diagnostic binary SHA256 was `96b78a131720ffae96c4fe254dc1693120f435390206f05dd357a0c3ae5d2cfb`. Native scopes used the thread CPU clock and monotonic wall time. A synthetic read-only teacher query verified balanced scopes before the one validation game.

```sh
cd /home/tongshu/acceptance/worker_components_20261104/src
python -B verification/worker_components_20261104/prepare.py ../diagnostic
cargo build --release --offline --manifest-path ../diagnostic/Cargo.toml
export PYTHONPATH=.extension:.:vendor/arena
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export SOURCE_COMMIT=84e8d63c523166d52932a01690b3b402b4ff6dbd
timeout --signal=TERM --kill-after=3s 150s /home/tongshu/venv/bin/python -B -u \
  verification/worker_components_20261104/measure.py \
  /home/tongshu/acceptance/bc_v6_readiness_20261103/runs/bc_readiness ../profile --score-only-astra
```

The matched draw took 17.269 CPU / 17.273 wall seconds, compared with 17.010 / 17.013 for the [unmodified release](../lite_intent_legality_20261104/REPORT.md). All 1,031 committed actions and all 4,128 public observations retained their expected hashes. The exit status was 0. The duration difference includes instrumentation and timing variation. Absolute application speedups cannot be inferred by removing an inclusive total.

The static witness shipped as commit `3e7ee8460a85b98d56711e53316087592646d4ac`, archive SHA256 `7d7467d50d171d1ac874017084ea84d25d084d91c8c18e53febaaeba67ce3e3b`. In a second fresh source directory it ran `hidden_forecast.py "$WESNOTH_RULES_DIR/rules.json" ../hidden-forecast.json` with the original release extension `fa0519eb3e5c8eced558e00598046950ae2edb8a2c0cd5f9352ccf7f84a13d69`. It exited 0 after two static queries. Archive hashes are `6620d8815bdb5e0576d6e540b1cf7ed05bffcf2120303c6a855c78a4ec4742e9` for the profile and `73b18d8e012a84d6d6e57a08ea93478e7bf8fdf920551607ae076ef87ae96b72` for the hidden-state witness.
