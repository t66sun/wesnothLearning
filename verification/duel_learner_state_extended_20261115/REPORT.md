# Qualified archived learner-state BC data and panel

[#334](https://github.com/t66sun/wesnothLearning/issues/334) passes after the authorized expansion of the same pure-Astra archive. The original 12-batch [census](../duel_learner_state_20261115/REPORT.md) remains the baseline. The extension checks one further settled eight-game batch per source cell at a time and stops at the first common prefix satisfying all three plans.

| Batches per source cell | Archived games | Maximum exact pairs | 1,024-pair gate |
| ---: | ---: | ---: | --- |
| 12 | 288 | 829 | Short |
| 13 | 312 | 951 | Short |
| **14** | **336** | **1,093** | **Passed** |

The first qualifying prefix adds 48 already-completed learner games. It has 6,627 real queries and 2,851 retained recruit/move labels. Of these, 1,177 differ from the recorded learner action. The teacher corpus, exact map/seat/faction/action/round-band match, distinct row requirement and coverage gates follow the original protocol. Independently summing the lesser count in each stratum confirms the 1,093-pair maximum. [Raw census](audit.json) · [Prefix trace](extend.log)

Seeds 202611151, 202611152 and 202611153 each select exactly 1,024 pairs without reusing a target within the matched slots and cover 116, 117 and 116 learner game families respectively. Each covers four physical layouts, both seats and all six factions. Each 64-step plan supplies 48 shared disjoint teacher rows and 16 matched pairs per step for both arms. Source shard hashes and stable decision ordinals bind records to their complete original raw histories. [Frozen corpus and target plan](corpus.json.gz)

## Static panel

All three unmodified village-bearing boards match their historical evaluation hash. The panel verified no overlap with initialization, optimization or checkpoint-selection exposure using the original initializer evidence and 1,359 schedule files. Historical evaluation exposure is recorded in the protocol. Both seats rotate through all 30 ordered nonmirror faction pairs per board. The resulting 180 matched slots and seven roles produce 1,260 scheduled games.

| Board | Villages | Prior panel |
| --- | ---: | --- |
| The Road to Weldyn | 13 | #306 |
| A Summer of Storms | 24 | #306 |
| Ur-Thorodor | 10 | #322 |

The formal plan remains three paired seeds, 64 Adam steps and 4,096 target visits per cell, and the four-hour cap. The adoption gate is +5 points over each of the two comparators and a positive lower 95% paired bound for each difference. [Frozen settings, seeds and identities](inputs.json)

## Ubuntu reproduction

The extension used source `ca5fac76bf91bae34a6e6b01bbc1e8c18b45096d` with Git archive SHA-256 `aa31f29cbb49859bcedc51f5094c00d51be013b5c0ab7c753e7a4a67aee369f9` and took 90.261 seconds. The static panel used source `0503bfc91e03d64b61ad41d1d917fdfa481e7d12` with Git archive SHA-256 `21a91e0d0f0a9a6fde983f599ef7722742d89c1dd82fbb5cef5b3c97013c6e49`. It uses the provisioned 1.18.8 historical map directory from the same server. The extended corpus SHA-256 is `f7e3544ed07826a7350375f6bc00a1b1e3f14f1858121e9bc07859103713744e` before gzip. The inputs JSON SHA-256 is `3a1b250a8ac2e7a11b1328f6a73524ad6ba6a711c5393f2ad36bffe8910cfccf`. Preparation consumed zero optimizer steps and new games.

```sh
audit=/home/tongshu/acceptance/duel-learner-state-20261115-Wt2pkM
panel=/home/tongshu/acceptance/duel-learner-state-20261115-zp4rjq
extension=/home/tongshu/acceptance/immutable_forecast_20261104/green/.extension
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
cd "$audit/source"
PYTHONPATH="$PWD:$extension" /home/tongshu/venv/bin/python -m verification.duel_learner_state_extended_20261115.extend \
  "$audit/recount" ca5fac76bf91bae34a6e6b01bbc1e8c18b45096d "$audit/source.tar"
cd "$panel/source"
PYTHONPATH="$PWD:$extension" /home/tongshu/venv/bin/python -m verification.duel_learner_state_extended_20261115.protocol \
  "$panel/recount" "$audit/design" 0503bfc91e03d64b61ad41d1d917fdfa481e7d12 "$panel/source.tar"
```
