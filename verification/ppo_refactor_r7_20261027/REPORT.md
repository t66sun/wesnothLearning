# R7 stock teacher identity and native reference roles — 2026-10-27

Issue #64, parent #48. Implementation `e509a8d364495972bb8e4830ada4654a7220e3f7`, based on R6 main `c8826067f3fd2f89f00ff0414c70d1188a16e7e9`.

## Result

New manifests freeze stock RCA kind `wesnoth_default_rca`, version 1.18.8, rules/runtime identities, `query=none` and `action_source=engine_events`. No Astra archive is required or copied into frozen opponents. `capture_sha256` remains null until R8 implements capture; this is not a claim of an available label pipeline. Old manifests lacking a teacher record require their original frozen source. An explicit legacy registry record remains available for historical fixtures and paths.

The runner derives its native reference pool from that record: baseline only for stock. New reference evaluation defaults to native, and a new manifest cannot freeze a lite stock reference evaluator. Lite student rollouts use student/history seats only; all externally referenced baseline jobs are native. Baseline is never rewritten into an addon, including explicit legacy paths. Stock-reference validation/nomination/calibration jobs carry their actual native engine and teacher identity. New stock runs reject Astra labels and mismatched teacher records before update identity commitment.

Stock labels have separate native/rules/capture/runtime validation; batches cannot mix teacher identities. Existing legacy Astra native/lite checks remain. BC retains its existing human proportion with either one teacher source; PPO exclusion still uses the active control identity. Pure student Lite hosts do not load Astra modules; loading historical modules requires an explicit legacy teacher request. Stock Lite teacher/query requests fail. The native RPC's Astra action path is conditional on an explicit legacy implementation request; an unqualified teacher request does not fall back to it.

## Local reference

Six new identity tests cover freeze/reload with an empty opponent directory, actual runner role construction and foreign-label refusal, baseline preservation, native label identity/isolation, unsupported stock query/Lite requests, and pure Lite student/history/module composition. Named tests failed before each corresponding implementation: baseline became `gpt6astra.zip`, empty opponent freeze required Astra, runner lacked reference roles, stock record was treated as a path, and stock labels were unknown.

The affected identity/cadence/nomination/budget/resume group passed 16 tests (7.968 s). Identity/source/resume/cadence/manifest group passed 19 (7.233 s). Final identity/cadence/scenario/eligibility/nomination/budget checks passed 28 (6.746 s); the added production runner foreign-label assertion passed separately (2.615 s). Shared fixtures explicitly declare their historical Astra context rather than obtaining it as a default. No production identity check is weakened.

## Ubuntu isolated acceptance

Directory `/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r7_20261027_e509a8d`; existing dependencies and frozen read-only data reused. Python 3.12.3, torch 2.9.1+cpu; rule SHA-256 `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`. [Environment](ubuntu/environment.log).

Source-only archive: 2,088,960 bytes; SHA-256 `6572d2cb8650df6e2219691186215db3a6b5794943491ad6cfb265578157c186`.

```powershell
scp tmp/refactor_r7_20261027/source.tar cpuServer:/tmp/wesnoth-r7-e509a8d.tar
scp verification/ppo_refactor_r7_20261027/run_ubuntu.sh cpuServer:/tmp/wesnoth-r7-e509a8d.sh
ssh cpuServer "bash /tmp/wesnoth-r7-e509a8d.sh 6572d2cb8650df6e2219691186215db3a6b5794943491ad6cfb265578157c186"
```

Exact commands in [script](run_ubuntu.sh). The stdlib unittest runner preserves the planned assertions; pytest remains unavailable. The revert reinserts only the removed baseline substitution into the disposable source, preserving the new interfaces.

| Check | Observed | Evidence |
| --- | --- | --- |
| Identity/cadence/scenario/eligibility/nomination/budget/resume/source/manifest/BC-RNG checks | 39 PASS, 7.779 s | [targeted](ubuntu/targeted.log) |
| Native RPC Lua compilation | PASS; syntax only | [syntax](ubuntu/lua_syntax.log) |
| Baseline substitution reinserted; named two-seat assertion | Expected FAIL: baseline changed into `gpt6astra.zip` | [reverted](ubuntu/reverted.log) |
| Fixed module restored; repeat assertion | PASS | [restored](ubuntu/restored.log) |
| Source before/after probe | Identical | [before](ubuntu/source_before.sha256), [after](ubuntu/source_after.sha256), [status](ubuntu/status.log) |

## Limits and blockers

No native game or actual stock capture/query capability was exercised; the identity freeze/runner tests use a fake runtime reference that is never executed. They prove wiring and hash binding only. No corpus or formal training started. R8 event capture, FX1–FX3 and R9 protocol/status remain not run/unimplemented. Query-based teacher scheduling intentionally rejects the stock `none` capability; it must use R8 full native capture later. Packaging/benchmark/report migration remains R10. These changes alone do not make a new training run operable or establish native strength.

R4 scenario floors and R5 qualified-rehearsal prerequisites remain unresolved data/design blockers; they are not lowered. Historical data, packages, reports and installed models are unchanged. Earlier focused evidence is reused only for unchanged responsibilities; R6's local legacy/extension failures and N1/numerical/package limits remain explicit in their reports.
