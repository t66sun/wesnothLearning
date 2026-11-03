# BC uses the recorded terminal outcome

The BC value head reads `terminal_reward` on schema 6 rows and `reward` on schema 5 rows. The reader and transition-reward calculation share the schema field selector. Rows with `value_valid=false` remain excluded from value supervision. Policy labels, sampling and imitation thresholds retain their existing definitions.

## Observed on frozen data

The v10 team2v2 run at `/home/tongshu/acceptance/team_bc_branch_20261102/runs/team_bc_branch` identifies 48 teacher shards in `team2v2/state.json`. Their SHA256 digests matched [the frozen inventory](../team_bc_branch_20261102/input_model_hashes.json). For each gzip JSONL record, the read-only count took its metadata from `json.loads(line)['m']`, filtered to `choice >= 0` and `value_valid`, then compared `terminal_reward` with the previous BC expression `row.get('reward', 0) or 0`.

All 308 eligible value labels in these shards were schema 6 training rows with recorded terminal outcome −1. The old BC expression returned zero for every one. Teacher games 00019, 00022 and 00024 contributed 122, 102 and 84 rows respectively. These counts cover the full corpus, before the bounded reader selected its training batch.

## Ubuntu verification

The regression passes a toy two-decision sequence through `learning.train.train(..., method='bc')` and performs one SGD step. With only the final value bias trainable and a starting prediction of 0.75, a verified win must move it to 1.0. The second decision has its value masked. The two subcases exercise a newly written schema 6 shard and schema 5 human decisions (verified win plus unknown outcome).

| Source commit | Source archive SHA256 | Ubuntu directory under `/home/tongshu/acceptance` | Observed result |
| --- | --- | --- | --- |
| `cb3bab8ca5f0ba06ac434fbcdc6611c6a680c70f` | `6a917250678b499df688b2c563fdc5a89bbbb9fc788cf38d57c9427187ab5de2` | `bc_value_target_red_20261103` | Schema 6 produced 0.25000066, expected 1.0. Schema 5 passed. Exit 1. [Regression](red.log.gz) |
| `e3cca9f387ecf6d7d0440e930be9eb527a9a6e73` | `0d59fb8ba25443330868e9a605994c0bdb775307c2058dd1740cb11db3147e9f` | `bc_value_target_fixed_20261103` | Both regression subcases and six other tests passed. One older truncation fixture errored while reading the retired `reward` key. Exit 1. [Suite](fixed.log) |
| `c402b972fc9541ce0c02a4f0d20a7d72896abdb1` | `cc974409090a834bcbbb75273ae160780117deaa0f581e473b2c55ee48168a59` | `bc_value_target_mask_20261103` | The corrected field assertion passed. The fixture then supplied an incomplete bootstrap, leading to a missing `reward_step`. Exit 1. [Fixture](field.log) |
| `427ba929c2687ff05a88a1eed3be4ad6a67b5c52` | `a2b92b550e1403ad56290e762b0709afd32b850fe04429a4a9541d600540bdf5` | `bc_value_target_bootstrap_20261103` | The fixture supplied its legal raw reward snapshot. All original assertions passed. Exit 0. [Fixture](bootstrap.log) |

The stale field assertion also errored on the pre-fix source, exit 1. [Baseline fixture](red-fixture.log) Across the final code and fixture, all eight affected tests have passing evidence. The last two commits change only the truncation fixture.

Each source was shipped with `git archive --format=tar.gz --output=ARCHIVE COMMIT -- . ':(exclude)verification'`, uploaded to cpuServer, checked with `sha256sum` and extracted with `tar -xzf` into its fresh directory. The fixture used the synthetic rules in `tests/v5/helpers.py` and the existing rules directory linked as `data/rules` from `/home/tongshu/acceptance/teacher_slow_attribution_green_20261103/data/rules`. The provisioned feature catalog has rules SHA256 `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`. The isolated v6 extension had SHA256 `63b1c119670d4d0981925fafef4f781ab274f05fb0aa2fedafc8b24dfd503059`. Ubuntu ran Python 3.12.3 and PyTorch 2.9.1+cpu.

```sh
export PYTHONPATH=/home/tongshu/acceptance/teacher_slow_attribution_green_20261103/.extension:.:vendor/arena
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
py=/home/tongshu/venv/bin/python

# Regression-only on cb3bab8
"$py" -B -m unittest -v tests.v5.test_reward_row_schema.RewardRowSchemaTests.test_bc_value_update_uses_the_valid_terminal_outcome_in_each_schema

# Affected suite on e3cca9f
"$py" -B -m unittest -v tests.v5.test_reward_row_schema \
  tests.test_human.HumanTests.test_capture_requires_complete_native_evidence_and_unknown_value_is_masked \
  tests.v5.test_learning_core.RewardTests.test_gae_hand_computed_and_truncated_tail \
  tests.test_training_revision.RevisionTests.test_faults_are_excluded_and_truncated_teacher_value_is_masked

# Truncation fixture on cb3bab8, c402b97 and 427ba92
"$py" -B -m unittest -v tests.test_training_revision.RevisionTests.test_faults_are_excluded_and_truncated_teacher_value_is_masked
```

The checks establish the BC value target and masking behavior. No corpus fitting or collection was run. The effect on held-out recruitment and ordinary BC readiness remains unmeasured.
