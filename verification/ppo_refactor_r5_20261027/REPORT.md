# R5 rehearsal source separation — 2026-10-27

Issue #60, parent #48. Runtime implementation `9fee653`; acceptance source `e7342e2ad2eb4f6cbf118b68470bb6c5e5d6d54b` adds the manifest assertion, based on R4 main `9a836f8`.

## Result

`BCSampler` accepts implementation/hash exclusions and reports excluded rows and admitted source identities. PPO passes the run's evaluation teacher/control identity through `train`; a positive auxiliary coefficient with only control data fails before any parameter change. Mixed control/human pools sample human records only. Qualified policy rehearsal still requires the existing explicit opt-in. Human/policy records' environment teacher metadata is not treated as their action-label source; policy weights, when explicitly recorded, can be excluded by their own hash.

BC sampling uses no exclusion and retains teacher initialisation and RNG behavior. The default auxiliary coefficient remains 0.10; an explicitly zero auxiliary term needs no rehearsal pool or sampling. No coefficient default or gate changes. The manifest records BC teacher initialisation versus PPO control exclusion. Existing historical shards remain readable and unchanged. Resumption tests use compatible human rehearsal rather than the now-ineligible control labels; their original arithmetic, counter, RNG and checkpoint assertions remain.

## Local reference

Initial named assertion failed because `BCSampler` lacked the exclusion interface. After implementation, four new source tests plus BC cancellation RNG passed (5 checks, 3.022 s). Final affected group passed: 23 checks, 14.093 s. Adding the direct manifest-policy assertion reran only the three opponent/manifest checks: 3 PASS, 0.544 s.

Coverage includes a control-only production runner failure before parameter change, SHA-based exclusion, human environment metadata, default BC behavior, a 20-update tiny synthetic chain, zero auxiliary term, exact resume and KL accounting. These are implementation fixtures, not formal training.

## Ubuntu isolated acceptance

Directory `/home/tongshu/myDev/wesnothLearning/acceptance_ppo_r5_20261027_e7342e2`; existing dependencies and frozen read-only data reused. Python 3.12.3, torch 2.9.1+cpu; rule hash `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`. [Environment](ubuntu/environment.log).

Source-only archive: 2,068,480 bytes, SHA-256 `4d16f900c00805143eb0ccfddde0093dc6e083f0d877bf98d436ce394f5f30a6`.

```powershell
scp tmp/refactor_r5_20261027/source.tar cpuServer:/tmp/wesnoth-r5-e7342e2.tar
scp verification/ppo_refactor_r5_20261027/run_ubuntu.sh cpuServer:/tmp/wesnoth-r5-e7342e2.sh
ssh cpuServer "bash /tmp/wesnoth-r5-e7342e2.sh 4d16f900c00805143eb0ccfddde0093dc6e083f0d877bf98d436ce394f5f30a6"
```

[Script](run_ubuntu.sh) runs the 23 source/resume/KL/plan/BC-RNG/manifest checks through stdlib unittest because pytest is unavailable. The deliberate semantic revert disables only the exclusion predicate in the disposable data module, preserving the new callable signature; this proves behavior rather than failing on an unsupported argument. It is restored before the final assertion and source comparison.

| Check | Observed | Evidence |
| --- | --- | --- |
| Affected minimal group | 23 PASS, 9.545 s | [targeted](ubuntu/targeted.log) |
| Exclusion predicate disabled; named control assertion | Expected FAIL: `ValueError not raised` | [reverted](ubuntu/reverted.log) |
| Fixed module restored; named assertion | PASS | [restored](ubuntu/restored.log) |
| Source identities before/after probe | Identical | [before](ubuntu/source_before.sha256), [after](ubuntu/source_after.sha256), [status](ubuntu/status.log) |

## Limits

No real game, collection, new corpus, full suite or formal training. No strength or convergence claim. This removes the documented objective conflict; its effect on strength remains unproven. A teacher-only run has no qualified PPO rehearsal at positive coefficient and fails explicitly; supplying suitable data is a separate data decision, not an implicit permission to collect or lower the coefficient. R1–R4 evidence is reused where unchanged. R6–R10 and native capture fixtures remain unimplemented/not run; N1 and existing numerical/package failures remain open.
