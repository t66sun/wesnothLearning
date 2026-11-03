# File-backed Python/Lua export audit

Eight Ubuntu checks passed on `b9b03fc`. The trained duel checkpoint returned the same maximum Python/Lua error across all 1,202 retained policy and DAgger rows as the original serial audit. The file-backed audit completed in 48.59 seconds, down from 192.65 seconds. [Original input hashes](../bc_ordinary_v6_20261103/metadata/artifacts.json) · [Raw commands, logs and timings](checks.tar.gz)

## Method and identities

The original implementation was `7b83580b7b209654163e42c695e9a114a3d91352`. The accepted implementation was `b9b03fcf09a7e2f3327003c8fdd33d20b9c6fc1a`. Both ran independently from committed source archives on Ubuntu `cpuServer`, Linux 7.0.0-38-generic x86_64, Python 3.12.3, torch 2.9.1+cpu. OpenMP, OpenBLAS and MKL each used one thread. The three model inputs come from the completed v6 ordinary BC run. Its filtered rules SHA256 is `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`.

Each archive was created with `git archive --format=tar.gz --output=<file> HEAD -- learning lua engine_lite tests vendor benchmarks`, copied with `scp`, hashed on both hosts and extracted into a fresh directory under `/home/tongshu/acceptance/`.

| Ubuntu directory | Commit | Source archive SHA256 |
| --- | --- | --- |
| audit_workers_base_20261104 | 7b83580 | 6603ae1c556c001b777830e0f3d3506771d072416ef5d0ddefa8099654d04dce |
| audit_workers_red_20261104 | 7e93110 | fea18035449eeabc576535240106ea7723222d789b63a5a3fc65c053124e662c |
| audit_workers_green_20261104 | d419789 | 3912566f137d7d78687440e81d0b584eaa65f3525a056cbd35c23268f37be082 |
| audit_workers_verified_20261104 | ec93fa3 | 9e624336e3ad9b9f9bc8c0b4d3f3a20e2f4c5deb5a0a4307fe757180f92e881d |
| audit_workers_pooled_20261104 | b9b03fc | e30ca7d5b30f63cd6b7ddf0f3f8ca3ad6ed348d6254f59dc4897ffe2a080a51d |

The two regression tests initially errored on absent worker dispatch and sequence grouping at `7e93110`. The first worker implementation exposed a real input discrepancy in the existing 128-entity fixture. Recursive Lua table conversion dropped an element of a reused entity-feature list. The maximum error was 0.02785435 regardless of Python history caching. The established serializer gave 1.39e-16 on the same fixture. Constructing each container separately restored every compared input and passed the original tolerance. On 54 actual decisions, this conversion took 0.126 s against 0.328 s parsing equivalent Lua text. Caching frozen Python history reduced its forward time from 0.451 to 0.166 s with a maximum output difference of 1.42e-14.

The final test command in `audit_workers_pooled_20261104` was

```sh
/home/tongshu/venv/bin/python -m unittest tests.v5.test_parallel_export_audit \
  tests.v5.test_learning_core.AuditExportTests.test_verify_numerics_requires_full_budget_and_two_turns \
  tests.v5.test_learning_core.AuditExportTests.test_verify_numerics_37_candidates_two_turns \
  tests.v5.test_learning_core.AuditExportTests.test_verify_numerics_memory_overflow_and_128_entities \
  tests.v5.test_checkpoint_export_identity tests.v5.test_weight_export -v
```

Exit 0, eight checks in 22.397 seconds. Both serial and parallel audit paths matched in a two-format fixture with transitive sequence overlap across three files. The candidate and turn gates operated over each whole format. A changed memory write forced separate scoring of both sources. The three-model SDK package check reported 12,718,530 bytes.

## Retained duel benchmark

The benchmark used `last_bc.pt` SHA256 `7047c53595bfe634bfc90cc2b6d733a861a24b34ee8d55ba0da24c7f4e4014df` and the complete eight files matched by `duel/data/rollout-00036-duel-g*.jsonl.gz` under the ordinary v6 run. The four policy/DAgger pairs had 133, 302, 54 and 112 raw decisions per source. Their total compressed size was 12,803,483 bytes. All four pairs had equal initial history and byte-identical ordered model inputs and memory writes. Both streams underwent schema validation and supplied turn and candidate evidence. [Benchmark driver](benchmark.py)

| Implementation | Wall seconds | User CPU seconds | Peak single process KiB | One-second sampled tree peak PSS KiB | Maximum error |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original serial, all rows in one list | 192.65 | 190.72 | 1,592,808 | unmeasured | 5.684341886080802e-14 |
| Independent grouped audit, eight workers | 61.30 | 271.27 | 628,628 | 3,181,160 | 5.684341886080802e-14 |
| Shared pool with exact input reuse, four independent groups | 48.59 | 97.58 | 947,952 | 2,309,392 | 5.684341886080802e-14 |

The original command was `/usr/bin/time -v timeout 360s /home/tongshu/venv/bin/python -B -u bench-base.py`. The final command used the same interpreter and `/usr/bin/time -v timeout 240s` with `benchmark.py` and eight permitted workers. The last run sampled peak tree RSS of 2,720,728 KiB. These observations measure this duel corpus.

## Three-format export proxy

The separately frozen proxy uses the same three BC checkpoints, the first four duel and eight FFA/team teacher shards by name, and all four retained duel policy/DAgger pairs. Its 24 games have 28 physical archives and 5,236 raw rows. The full CLI and SDK packaging share a 300-second wall ceiling. The plan records every input hash, byte/row count, checkpoint identity, command and host load before launch. [Frozen plan](proxy-plan.json) · [Proxy driver](proxy.py)
