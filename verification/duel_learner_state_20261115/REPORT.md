# Archived learner-state BC support gate

[#334](https://github.com/t66sun/wesnothLearning/issues/334) stopped at the frozen support gate on Ubuntu cpuServer. The census found **829 distinct matched target pairs** against the required **1,024**, a shortfall of **195**. All three declared seeds encounter the same maximum. The pairs cover 93 learner game families, all four physical training maps, both seats and all six factions. This is a data support result. The route stops before implementation and formal acceptance, with zero new optimizer steps or games. [Census, per-stratum counts and gate](audit.json)

## Archived cohort and matching

The first 12 settled eight-game batches from each of the three pure-Astra #322 cells supplied 288 completed, training-eligible learner games. These were sampled by v38 through v49 in each cell, with 36 cell/version references and 34 distinct model-file hashes. The audit joined both raw shards to the complete learner job and settled schedule. It checked decision order and committed memory writes across the entire paired streams. Each real query had the same visible actor inputs and candidate ordering as its corresponding learner decision. The audit counted 5,630 actual queries, including 2,740 recruit or move queries. Of these, 2,389 exactly matched retained candidates, and 990 differed from the recorded sampled learner action. [Archived source run](../ppo_opponent_acceptance_20261115/REPORT.md)

The original v38 corpus contains 240 train games with 28,077 raw rows, of which 25,397 have retained labels. The original split reserves another 60 games for validation. There are 14,775 eligible original recruit/move targets. Each match requires the same physical layout, learner seat, own faction, labeled action kind and round band (1–5 or 6–30). Each original and learner target may occur once per matched sample.

| Physical layout | Original teacher targets | Learner targets | Maximum pairs | Learner targets with no teacher stratum |
| --- | ---: | ---: | ---: | ---: |
| Arena2 | 2,531 | 598 | 273 | 325 |
| Sablestone Delta | 4,400 | 404 | 219 | 185 |
| The Freelands | 4,108 | 642 | 146 | 496 |
| Weldyn Channel | 3,736 | 745 | 191 | 554 |
| **All** | **14,775** | **2,389** | **829** | **1,560** |

An independent calculation summed the lesser count in each stratum to obtain the 829-pair upper bound. Every stratum with eligible teacher support had enough teacher rows to pair all of its eligible learner rows. Of the 1,560 unmatched learner targets, 969 were on a map and seat combination with zero eligible original targets: Arena2 seat 2 (265), Sablestone Delta seat 1 (2), The Freelands seat 1 (334), and Weldyn Channel seat 1 (368). The other 591 lacked an exact faction, action-kind and round-band match within a represented map and seat. The source gap is visible in the original split. No target plan or launch was emitted under this gate.

## Reproduction

The read-only census ran in 80.950 seconds on cpuServer from source commit `20e06e8a58f27efc152657cfcc5bf9e5e08b3107`. Git archive SHA-256 was `f76d936462eedec584a0618862ab4c248c31366d984b3034f22dd9e83c08137b`. The [audit JSON](audit.json) SHA-256 is `0eb31e3b2e9fd4a180bbc784e386d8f4139b1951a0cb71ec42e2fe237cccfdd6`, and the [command output](corpus.log) SHA-256 is `63a65979731d200ad36c1cda84795d2ad21cd53a27948151f7d0412c0c7c7f1c`. The process exited zero after recording the failed support gate.

```sh
root=/home/tongshu/acceptance/duel-learner-state-20261115-7q70Mi
cd "$root/source"
export PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export WESNOTH_RULES_DIR=/home/tongshu/acceptance/filters_compiled_20261103/data/rules/1.18.8-combat-filtered
export PYTHONPATH="$PWD:/home/tongshu/acceptance/immutable_forecast_20261104/green/.extension"
/home/tongshu/venv/bin/python -u -m verification.duel_learner_state_20261115.corpus \
  "$root/design" 20e06e8a58f27efc152657cfcc5bf9e5e08b3107 "$root/source.tar"
```

The [frozen v38 endpoint](../duel_ppo_acceptance_20261107/REPORT.md) and the derived Astra source, Lite extension, rules and candidate identities are recorded in the census. Use a fresh output path when repeating the command.
