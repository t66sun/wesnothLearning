# Opt-in Lite duel combat-choice worker

[#327](https://github.com/t66sun/wesnothLearning/issues/327). The experiment job runs the usual frozen greedy learner. On a greedy combat pick, the Astra arm queries the current learner's public view once, matches the complete combat intent against the actor's ordered candidates and executes the matching candidate when different. The regular executor supplies the committed turn write. The control records how many combat decisions it made. Both roles separately report query outcomes and worker time.

## Ubuntu evidence

The fixed board uses a two-weapon Archer and an adjacent low-HP enemy. In both learner seats Astra chooses the other retained weapon and the executor commits that choice. The new tests cover complete move-attack identity, unchanged observation and memory with same/missing/noncombat proposals, and zero queries following a greedy noncombat pick. Replacing the selector's return value with the original greedy index fails the actual executed-action assertion in both seats. [Reversion output](revert-test.txt)

The full scoped suite ran 30 tests, with 29 passing and one failure. `ScoreAstraTests.test_query_and_bootstrap_decisions_get_full_candidates` fails its stored `bootstrap_value` assertion on this source and on the original worker from `90f05b748110fd86c6d09c468ee549b04d116e1d`. The finite-task external-cut regression passed. [Scoped suite](ubuntu-tests.txt) · [Baseline failure](baseline-tests.txt)

The test and preflight source was `c6aeba9c04cd4bd9559f56ec2a0c33685c731c15`, archived to SHA-256 `eb7021f15c7fbb7e61e2dff85ca587e17c470882ca0838645bd7d896f7bbe12f`. The isolated baseline overlay archive SHA-256 is `5e53cd143efa595f9a4cde3b88a8639cee2f05303a0a28700ee8d1981a3c98a8`.

```sh
/home/tongshu/venv/bin/python -m unittest -v \
  tests.v5.test_lite_combat_choice tests.v5.test_lite_score_policy \
  tests.v5.test_lite_score_astra tests.v5.test_teacher_state_reuse tests.v5.test_finite_score
```

## Frozen formal launch

The no-game preparation exported the common v38 policy and checked 240 jobs against the frozen slots. The synthetic audit consumed 240 synthetic replies and recovered the expected +100 percentage points and [100, 100] interval. The schedule SHA-256 is `7923fe2217d8b72f8c79fb5a5946987fd0c5a392b2882d2b510f04974216ec23`. The [launch manifest](launch.json) SHA-256 is `2dcc6cc1ae1dfcce57511089dd03ede4adedb505c44fbfbf05177bc7e5789dda`. No formal games ran.

After explicit authorization, use the frozen Ubuntu extraction and launch manifest.

```sh
base=/home/tongshu/acceptance/duel-combat-20261114-vtMYiL
ext=/home/tongshu/myDev/wesnothLearning/formal_30h_scratch_20261104_2041/source/.extension
export PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
cd "$base/source"
PYTHONPATH="$PWD:$ext" /home/tongshu/venv/bin/python -u \
  -m verification.duel_combat_choices_20261114.driver run "$base/panel" \
  --launch-sha256 2dcc6cc1ae1dfcce57511089dd03ede4adedb505c44fbfbf05177bc7e5789dda
```
