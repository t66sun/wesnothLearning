# PPO retained-action headroom and the restored-control result

Ubuntu cpuServer, 2026-11-15. [#360](https://github.com/t66sun/wesnothLearning/issues/360) · [#352](https://github.com/t66sun/wesnothLearning/issues/352)

## Measured decision

The fixed v38 alternative changed the normalized official score by **−5.88 pp** across 17 matched states, with a game-clustered 95% interval of **[−25.49, +11.76] pp**. One pair improved, three declined and 13 tied. The archived PPO choices finished 8/4/5 W/D/L (28/51 points). The same sampled PPO and Astra after the forced v38 choice finished 7/4/6 (25/51 points). All four changes occurred in history 202611081. The other two histories had no changes in this slate. A single fixed move-to-end-turn intervention flipped one loss to a win. The slate did not support nominating a training change.

The experiment estimates one continuation draw per selected state. It leaves other retained alternatives and the omitted-action group unmeasured. The source archive retains the candidate list presented to the model. It has no capture of the full legal public intent set or an existing referee snapshot for any selected state.

## Exact archive and restore control

The original fixed #355 jobs preserve the scenario, combat and policy sampling seeds, weights, Astra identity and public learner rows. The first proof replayed six original-seed prefixes and stopped at a public hash mismatch before any identical-action suffix started. Each first mismatch was a forced one-candidate state with an original packed float32 shard line. Projecting the public fields onto a smaller row activated the general JSON fallback. The pinned Lua computes the turn feature as `turn / 30`, so its live float64 value differs from the stored float32. Changing only that value to the pinned formula reproduced the mismatch on each of the six archived rows. The corrected comparison uses the original source row's precision and preserves all candidate metadata and ordering. Its archive-only check also detects a genuine injected change. [Initial manifest](first-proof/proof-launch.json) · [Initial result](first-proof/proof-result.json) · [Storage checks](corrected-proof/stored-precision-check.json)

The corrected proof ran on the same six games and decision cuts. Six original-seed baselines and six identical-action suffixes reproduced 1,230 and 563 learner rows respectively. Public inputs, choices, archived action log-probabilities, public recurrent memory and the full official terminal summaries agreed. All six controls matched with a maximum log-probability error of zero. The corrected proof took 61.651 seconds. [Corrected manifest](corrected-proof/proof-launch.json) · [Corrected result](corrected-proof/proof-result.json)

The stock Lite loop reconstructs each archived prefix from its original seed. The test captures the Rust and Lua snapshot in memory at the predetermined decision. The referee restores engine, opponent-memory and combat-RNG state in a fresh host. The policy receives only its legal public inputs and restored public recurrent history. Both suffixes consume the same first sample draw. The varied suffix substitutes the frozen retained alternative once, then resumes the same PPO sampling and frozen Astra. The test uses `official-score-30-v1` with 3/1/0 points.

| Phase | Original starts / complete | Identical suffix starts / complete | Alternate suffix starts / complete | Wall seconds |
| --- | ---: | ---: | ---: | ---: |
| Initial proof | 6/0 | 0/0 | 0/0 | 15.437 |
| Corrected proof | 6/6 | 6/6 | 0/0 | 61.651 |
| Retained trial | 17/17 | 17/17 | 17/17 | 241.424 |

The retained trial matched 4,361 archived learner rows in the original replays and 2,410 in the identical suffixes. The maximum log-probability difference was `2.89e−15`. Seventeen alternate terminal summaries matched the planned game identities and had zero faults. There were zero optimizer updates. [Frozen retained cases](retained-launch.json) · [Raw results](retained-result.json) · [Independent recount](recount.json)

## Opportunity coverage

Eight evenly spaced learner rows from each of the 72 archived PPO games yielded 576 probes. In 52 rows (9.03%) across 40 distinct original games (55.56%), the observed sampled action was also PPO greedy and the v38 policy ranked a different retained action first. The selection used the same public observation and recurrent prefix for both policies. Up to two states per turn-band and alternate-action class were drawn by a fixed hash order, with one selection per original game. The final 17 cases cover three histories (7, 5 and 5), three layouts (8 Fallenstar Lake, 6 The Freelands and 3 Weldyn Channel) and both learner seats (5 and 12). Rates refer to the archived eight-row probe schedule. [Opportunity census, probabilities and observed GAE](retained-opportunities.json) · [Selection code](opportunities.py)

| Learner turns | End turn eligible / used | Recruit eligible / used | Movement eligible / used | Combat eligible / used |
| --- | ---: | ---: | ---: | ---: |
| 1–5 | 1/1 | 10/2 | 0/0 | 3/2 |
| 6–15 | 0/0 | 4/2 | 5/2 | 20/2 |
| 16–30 | 0/0 | 2/2 | 3/2 | 4/2 |

## Decision-level official scores

The role column gives training suffix, roster block and learner seat. The 95% interval resamples these 17 distinct original games 10,000 times. Effects are normalized by three.

| Layout | History / block / seat | Turn / decision | Archived action | Fixed alternative | Official points |
| --- | --- | --- | --- | --- | ---: |
| Weldyn Channel | 081 / 8 / 2 | 4 / 60 | move (24,12)→(23,13) | end turn | 0 → 3 |
| Fallenstar Lake | 083 / 24 / 2 | 16 / 358 | recruit Walking Corpse at (40,6) | recruit Walking Corpse at (41,8) | 1 → 1 |
| The Freelands | 081 / 0 / 2 | 5 / 70 | move-attack (14,16)→(12,13)→(12,12), w2 | move-attack (21,20)→(25,18)→(25,17), w1 | 3 → 0 |
| Fallenstar Lake | 082 / 8 / 2 | 22 / 485 | move (40,8)→(34,10) | move (35,6)→(29,4) | 1 → 1 |
| Fallenstar Lake | 083 / 24 / 1 | 10 / 168 | recruit Elvish Shaman at (1,7) | recruit Elvish Fighter at (1,7) | 0 → 0 |
| The Freelands | 082 / 8 / 1 | 20 / 383 | move-attack (15,16)→(17,15)→(17,16), w1 | attack (16,15)→(17,16), w1 | 3 → 3 |
| Fallenstar Lake | 081 / 8 / 1 | 12 / 219 | move (16,19)→(12,20) | move (16,19)→(15,16) | 1 → 1 |
| Fallenstar Lake | 081 / 0 / 1 | 1 / 1 | recruit Drake Clasher at (1,7) | recruit Drake Fighter at (1,7) | 3 → 1 |
| The Freelands | 082 / 0 / 1 | 9 / 137 | move-attack (30,19)→(26,16)→(25,17), w2 | move-attack (30,19)→(25,18)→(25,17), w2 | 3 → 3 |
| The Freelands | 083 / 0 / 2 | 20 / 348 | move-attack (28,5)→(24,3)→(24,2), w2 | recruit Dwarvish Fighter at (18,20) | 3 → 3 |
| Fallenstar Lake | 081 / 16 / 2 | 5 / 68 | move (27,5)→(26,8) | move-attack (27,5)→(21,5)→(20,5), w2 | 0 → 0 |
| Weldyn Channel | 082 / 24 / 2 | 25 / 453 | move (17,19)→(22,16) | move (23,13)→(23,8) | 3 → 3 |
| Weldyn Channel | 082 / 16 / 2 | 8 / 134 | recruit Thief at (13,19) | recruit Footpad at (13,19) | 0 → 0 |
| The Freelands | 081 / 8 / 2 | 19 / 371 | move-attack (19,8)→(18,4)→(19,5), w1 | move-attack (19,6)→(18,4)→(19,5), w2 | 3 → 3 |
| Fallenstar Lake | 083 / 8 / 2 | 13 / 271 | move (40,6)→(36,10) | move (40,8)→(34,11) | 3 → 3 |
| Fallenstar Lake | 083 / 16 / 2 | 1 / 7 | recruit Dwarvish Fighter at (41,9) | recruit Dwarvish Fighter at (41,8) | 0 → 0 |
| The Freelands | 081 / 24 / 2 | 6 / 93 | move-attack (19,20)→(20,16)→(20,15), w1 | move-attack (27,16)→(26,14)→(26,13), w1 | 1 → 0 |

At the improved Weldyn state, PPO assigned 46.85% probability to the archived full move and 26.27% to ending the turn. v38 assigned 99.66% to ending the turn on the same public row. The archived action's GAE was −0.650 and the observed terminal score moved from 0 to 3 under the intervention. In the three degrading pairs, the logged archived-action GAE was positive (+0.975, +1.316 and +0.145). A single matched continuation gives a realized effect for that state. The archived GAE applies to the sampled action. The study does not observe a counterfactual training advantage or a subsequent historical optimizer update.

## Evidence and reproduction

| Phase | Source commit | Git archive SHA-256 | Launch SHA-256 | Result SHA-256 |
| --- | --- | --- | --- | --- |
| Initial proof | `88262eda1299babeb15c2be6b0acd1d51701ee59` | `95d06b27c06146d3ed0ffe2bbd332ee99120d1b84d2957c445baf58ca4e99bc9` | `bc7c7c2d028f51e15c570a730433d5a2b9abee17f6d2490ea37d8466e7d3c781` | `229e5cf2ce737d8581e31149fb6c40d259cdc020964c954246f80e5b21d880fc` |
| Corrected proof | `5e8c716299ba7fd0665f42e3e4ce0ed979a5b584` | `8b181d2c689fe561ca27a4763ad1a70552bb0971b204fb3f62fa2e1a1547cd58` | `4d66d5e357d84821abd239816c7577c0bc4bca94876c4ef819502d34253d4a26` | `c59a0817a4fa555f38a0c307b17587aca7124bd8c114939be462b79289fd3c7e` |
| Retained trial | `352b1cf32eb0c303a89c98cdf4c60c8bdaa662d4` | `9a012b7409d00025eedecb4560f9b03eeea1d1f352b976fe4f4f98cf45fe02eb` | `868aaea15d6a97381d9112a29e3acaaae9a828afc38fb26ffef230175a602403` | `288f12b22081a333a9ec7890f38911bd6d77907d7b67ac9160ac671a0985fb14` |

[Initial launch receipts](first-proof/proof-receipts.tar.gz) · [Corrected launch receipts](corrected-proof/proof-receipts.tar.gz) · [Retained launch receipts](retained-receipts.tar.gz)

The independent recount used Git commit `a41f8a558753930c328d5fe30a38624655f42055` and tar SHA-256 `0ec9c043cb93d716abb6f4a8c008eb3fb39290ac1c6434b493caee28cbd279ab`. Its JSON SHA-256 is `63b8b26dc1ad6ea7bf85174d86ab9d5524070f3f56a232b9354688babd64fb90`.

To recount the existing raw results and verify the archived baseline joins without simulation, use the pinned server paths.

```bash
audit=/home/tongshu/acceptance/ppo-headroom-retained-20261115-g8a6CF
review=/home/tongshu/acceptance/ppo-headroom-recount-20261115-vtsqhj
capture=/home/tongshu/acceptance/ppo-diagnosis-20261115-Z8O0k3/capture
out=$(mktemp -d /home/tongshu/acceptance/ppo-action-headroom-recount-XXXXXX)
/home/tongshu/venv/bin/python -u "$review/verification/ppo_action_headroom_20261115/recount.py" \
  "$audit/main" "$capture" 868aaea15d6a97381d9112a29e3acaaae9a828afc38fb26ffef230175a602403 "$out/recount.json"
```
