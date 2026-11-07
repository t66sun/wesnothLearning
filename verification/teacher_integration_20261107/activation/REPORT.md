# Mixed teacher default activation

The authorized Ubuntu rerun passed all six Native/Lite integration cells: 48/48 games completed in 874.746 seconds (14m 35s), with no faults, hard timeouts, identity errors or stored-label audit errors. New experiments now default to `mixed-20261107` for supervision, PPO teacher seats, evaluation and reward references. Explicit `--teacher-set astra` remains available; resume keeps the frozen experiment identity.

The user explicitly excluded action coverage from this activation gate and requested a minimal implementation. Coverage is retained below as a diagnostic. The teacher algorithms, candidate set, training algorithms and formal BC qualification rules were not changed. This run used fixed untrained students and no optimizer; its samples were not promoted into a formal corpus.

## Sources and execution

- Panel and coverage-gate check: `909f077dbaadf3993efad42027499df47527a1ed`.
- Default activation and teacher-set checks: `ee6bd577fb1d32db27f758e07bc30d508808bdef`.
- Frozen selected package SHA-256: `6b461de4e99303321b0119a7b88babd575c2d786500b28da4cb45d3c2bdabdb3`.
- Rules SHA-256: `e6b4f6200b0a8ad58a536b844fff37cfa9e0091bf0a0b702a8982155310f2f17`; task `official-score-30-v1`; seed `20261107`; eight workers; one-hour panel deadline.
- Host: `cpuServer`, Ubuntu, Wesnoth 1.18.8, isolated `teacher-host-v1` extension. Source transfer used the existing commit/archive/upload script and existing server dependencies.
- Raw schedule, game logs and shards remain at `/home/tongshu/myDev/wesnothLearning/verification/teacher_integration_20261107/activation_20261107T1115`.
- Copied [manifest](manifest.json), [results](results.json) and [summary](summary.json) retain their original server bytes. Each check directory records its source, command, output and exit code.

Commands, run from the local source tree to execute on Ubuntu:

```text
python tests/ship_teacher_integration.py activation_gate -- bash tests/build_teacher_host.sh /home/tongshu/venv/bin/python -m unittest tests.test_teacher_integration_panel -v
python tests/ship_teacher_integration.py activation_panel -- bash tests/build_teacher_host.sh /home/tongshu/venv/bin/python -m tests.acceptance_teacher_integration --output /home/tongshu/myDev/wesnothLearning/verification/teacher_integration_20261107/activation_20261107T1115
python tests/ship_teacher_integration.py activation_default -- bash tests/build_teacher_host.sh /home/tongshu/venv/bin/python -m unittest tests.test_teacher_set -v
```

The existing panel-design test passed (1 test), including the assertion that low coverage alone does not block activation while incorrect stored DAgger labels do. All 11 teacher-set checks passed, including the new-experiment default assertion and the existing per-role strategy, package, backend and resume checks. Logs: [gate](checks/20261107T111436_activation_gate_909f077dbaad/output.txt), [panel](checks/20261107T111513_activation_panel_909f077dbaad/output.txt), [defaults](checks/20261107T113049_activation_default_ee6bd577fb1d/output.txt).

## Observed panel results

Each cell contains four BC games and four PPO/DAgger games, including all focal seats. All 48 stored-row audits passed. There were 333 teacher queries and 312 valid stored DAgger labels, yielding 3,413 usable supervision records including BC. Panel-wide throughput was 14,046 usable records/hour, using total panel wall time as the denominator.

| Backend / format | Completed | Valid DAgger / queries | Usable supervision | Maximum query ms | BC action coverage (diagnostic) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Native duel | 8/8 | 39/42 | 495 | 700.0 | 80.99% |
| Native FFA4 | 8/8 | 53/54 | 939 | 39.0 | 92.58% |
| Native 2v2 | 8/8 | 42/50 | 491 | 714.0 | 65.07% |
| Lite duel | 8/8 | 41/45 | 372 | 603.9 | 78.81% |
| Lite FFA4 | 8/8 | 98/102 | 728 | 21.7 | 91.84% |
| Lite 2v2 | 8/8 | 39/40 | 388 | 709.9 | 71.08% |

Per-action counts, unmatched-action reasons, query timing and per-game audits are in the summary. The original coverage criteria are not satisfied in five cells; those results were neither relabelled nor used to block activation under the revised instruction.

## Activated configuration and scope

| Format | All four teacher roles |
| --- | --- |
| duel | `clean_fortified_pruned` |
| FFA4 | maintained Astra |
| 2v2 | `clean_fortified_pvs` |

The already accepted [role routing](../roles/REPORT.md), [Native](../native/REPORT.md) and [Lite](../lite/REPORT.md) checks remain applicable. The [previous failed panel](../panel/REPORT.md) is unchanged. The rerun used its corrected `LearningSupport` namespace and required no additional runtime fix. The only new runtime change is the default teacher-set value; the corresponding 11 checks ran after that change.

This accepts integration and default activation. It does not establish BC qualification, student strength or Native/Lite strength equivalence, and starts no formal collection or neural training.
