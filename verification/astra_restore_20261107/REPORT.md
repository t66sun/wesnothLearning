# Astra restoration acceptance

- Requested integration baseline: `5dd440d274a5e57610372eac08d553342af338ca`.
- Tested source: `0119385ab61f282a1298c18d12efbb1df1a01eee`.
- Fresh experiments again use maintained Astra for collection, DAgger, PPO teacher seats, evaluation and reward references. The independent experimental teacher, its tests/tools and its optional arena seat budgets have also been retired.
- The unrelated bounded duel acceptance delivered at the requested baseline is retained.

## Archive

The ignored local `archive/new_teacher_20261107_c8fa714.tar.gz` preserves 383 tracked files from `c8fa714cd45cb9e22e62e229396f86d303d12b86`, including original shared-file contents, dedicated implementation/tests, delivery and dated teacher evidence. Its entries were checked against the Git path list before removal. It is not included in the source shipment or Git history.

SHA256: `bb580dc2fd726e15c73ac6019ef9b19da318890559117907983e5848883ed189`.

## Ubuntu checks

An isolated release extension was built from the tested commit on `cpuServer`; the existing environment and rule packages were reused. [Commands](commands.sh), [build output](build.log), [loaded extension](extension.txt), [source identity](SOURCE_COMMIT) and [rules identity](rules_identity.json) record the inputs.

```sh
python -m unittest tests.v5.test_lite_default tests.v5.test_teacher_state_reuse -v
```

**11 tests passed in 1.224 seconds, exit 0.** [Output](unittest.txt). The new assertion checks that a fresh manifest freezes only `gpt6astra`, with no teacher-set contract. Existing checks cover CLI defaults, resume, scheduling, final evaluation controls, rule binding, and real Rust/Lua teacher queries across snapshot/restore and host reuse.

Static review found only the retired experimental modules and two research-only arena budget hooks differ from the requested baseline in active runtime directories. `git diff --check` passed. The two unchanged pre-existing source line-limit exceptions remain. No collection, training, full native games or strength certification was run.
