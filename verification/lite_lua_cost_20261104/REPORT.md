# Lua hex distance in the Lite worker

The Lite worker spent 7,829 of 29,342 sampled Lua instructions (26.7%) inside `wesnoth.map.distance_between` on one v10 team validation board. Astra's `dist` wrapper accounted for another 3,110 samples. Its movement rating repeatedly compares each legal landing with village goals and nearby friends. The measured host change computes the same hex distance from two signed axial offsets. The frozen Astra strategy and model inputs retain their existing identities.

The matched game took **23.273 seconds before and 21.955 seconds after** the distance change, a 5.7% wall reduction on one worker. The decision/action trace remained `3a0ddf8a35de37fe1a8463cfbd42d2acbc43b42c33609ef63e85b6e3517a70d1` across the baseline, sampling and optimized runs. Each matched the archived official result with 903 Astra actions, 128 policy actions, zero faults and a 30-turn draw. [Sampled stacks, matched replays and test logs](stacks-and-replays.tar.gz)

| Process CPU seconds | Original | Direct axial calculation |
| --- | ---: | ---: |
| Astra decision | 10.936 | 9.851 |
| Astra execution | 5.259 | 5.229 |
| Policy decision in host | 3.004 | 2.726 |
| Policy execution in host | 2.594 | 2.660 |
| Entire worker | 23.268 | 21.951 |

## Identity and procedure

The November 4 Ubuntu probe used the [same archived game, tensor, teacher, rules and seed](../lite_final_worker_20261104/REPORT.md) with fp64 tensor inference and score-only Astra. Each source was shipped by `git archive` into a fresh directory under `/home/tongshu/acceptance/lite_lua_cost_20261104`. Python 3.12.3 and torch 2.9.1+cpu ran with the three numerical thread limits set to one. Both timed replays used Python call profiling and no Lua instruction hook.

| Purpose | Git commit | Archive SHA256 |
| --- | --- | --- |
| Diagnostic source and original timing | `0ddc5182357ac03f6231c935fbf811b5d68cb37d` | `a5cf312f45c63eedf107ebfa3beec0b1b3368c89990a7b51b480405e4aca7ca1` |
| Failing work assertion | `b29a2a7ff9b8bfb376faf6bab56eef5ca99fa996` | `d384abd0a0305e87837f47c6f316fa72f14f472363ab2065a40412685ba2d990` |
| Optimized source | `d4e2f5d5cbd7a043c4a52a2aa587b42268d387da` | `32180dcafa92cc5e822444a707e83c347096b140c004998a4f11258931ae422b` |

The diagnostic build copied the shipped crate using `build_sampler.py`, installed an mlua hook in that copy and recorded a stack every 50,003 VM instructions. The raw collapsed stacks are stored in `lua-stacks.json`. Instruction shares measure interpreter activity. Process timings measure the original and optimized game. The diagnostic itself took 26.985 seconds and preserved the same action trace. The original release extension SHA256 was `385f18c03e4c08d9b13d8970470f9decf131ff83053119d5a115b3c9d5bdbc1f`. The optimized release extension SHA256 was `4d228e11e980ee3f91b93d79b71b9efbb429b8ea0eb3797bb18a2afbae512263`.

With each source's `PYTHONPATH` set to its extension, repository root and `vendor/arena`, and `WESNOTH_RULES_DIR` bound to the archived filtered rules, the commands were

```sh
cargo build --release --offline --manifest-path engine_lite/Cargo.toml
timeout --signal=TERM --kill-after=3s 120s /home/tongshu/venv/bin/python -B -u \
  verification/lite_final_worker_20261104/profile_job.py \
  /home/tongshu/acceptance/bc_v6_readiness_20261103/runs/bc_readiness ../distance-after --score-only-astra
/home/tongshu/venv/bin/python -B -m unittest tests.v5.test_lite_hex_distance \
  tests.v5.test_lite_score_astra tests.v5.test_teacher_state_reuse \
  tests.v5.test_allied_village_goal tests.test_lua_contracts -v
```

The original timing used `../distance-before` and the original release extension. For sampling, `build_sampler.py ../instrumented` prepared the diagnostic crate and `LITE_LUA_SAMPLE_FILE` pointed to a new JSON file. The timing and test commands exited 0 on the optimized source. All **20 affected tests passed** in 0.710 seconds. The original work assertion failed at 6,307,000 instructions. The optimized implementation used 3,684,000 against the same 6,307,000-instruction reference. Geometry matched for every signed coordinate pair in the test grid, including zero, negative and off-map locations. The raw archive SHA256 is `c4cc069471d78410b50eca7c2318fe7b7326c0ca89ca049dbfe9db3f482ceac7`.

This board establishes a single-worker gain. The [eight-worker estimate](../lite_panel_throughput_20261104/REPORT.md) used the preceding worker version. Neither measurement establishes final holdout throughput.
