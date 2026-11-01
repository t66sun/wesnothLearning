# Scope of omitted native weapon weights

Date: 2026-11-02 (Asia/Shanghai).

Question: does the known missing weapon-weight declaration support explain a current six-faction training mismatch, and should it trigger another combat-profile change?

## Identity and method

- Source: `822bb975b90a756a8459ae2b9926201d5aea69b5`, based on `914a504`.
- Source archive SHA-256: `190533b87f113d1c8ca69d17b43a8b2fffe1923dc15d3f5c0e45fb924ec924a6`.
- Frozen rules SHA-256: `d6fceafe7d0c9c67c750551b9901dbfb2b22290992a8daa1616a460e11826dca`.
- Ubuntu host `cpuServer`, existing `/home/tongshu/venv/bin/python` (Python 3.12.3). Source was shipped by `git archive`, scp and extracted into fresh `/home/tongshu/myDev/wesnothLearning/weapon_weights_20261102`; `data/rules` links to the unchanged main-tree input.
- [audit.py](audit.py) reuses the existing raw-WML child reader and actual training-closure traversal. It verifies the rules hash and every capture hash before reporting. It reads top-level base-unit attacks, excluding runtime objects, modifications and variations. Explicit values equal to the native default 1 are omitted from the result.

```bash
cd /home/tongshu/myDev/wesnothLearning/weapon_weights_20261102
SOURCE_COMMIT=822bb975b90a756a8459ae2b9926201d5aea69b5 \
/home/tongshu/venv/bin/python verification/weapon_weights_20261102/audit.py \
  --rules-dir data/rules/1.18.8-training \
  --output verification/weapon_weights_20261102/result.json
```

Observed exit **0**, approximately 2.3 s including SSH. Full structured output: [result.json](result.json); command summary: [ubuntu.log](ubuntu.log). No tests, games, collection, training or native battle were launched. Windows ran source/data inspection only.

## Findings

All **20** frozen captures pass their hashes and cover **587** unit IDs, with **11,093** attack declarations including repetition across scopes. The six-faction leader/recruit/advancement/plague closure has **158** unit IDs.

There are **26** nondefault base-type weight declarations when scope-dependent declaration positions are kept distinct. They are on Caravan, Eyestalk, four scorpion-family units and Quenoth units. **None belongs to the current 158-unit training closure.** Scope lists and exact weights are retained in the structured output. This establishes reachability for these captured base types only.

`engine_lite/lua/export_rules.lua:205` exports weapon damage/strikes/type/range/specials without weights; `engine_lite/src/model.rs:13` has no weight fields; `engine_lite/src/combat.rs:108` initially filters counters by range. The omission is real, but this base-declaration subset cannot explain a current six-faction training failure.

The installed 1.18.8 source at `/home/tongshu/myDev/wesnothLearning/WesnothLearning/.runtime/wesnoth-1.18.8/src/actions/attack.cpp` has SHA-256 `948a388df8d9c34ef47b345227b98e940ccc602627ceb12ea22be515a0b3217e`. Read with `sed -n '570,663p'` after locating symbols with grep (rg unavailable on the host). At lines 587–603, automatic defender selection filters nonpositive defense weights and disabled weapons, and prioritizes a counter disabling the attacker. Lines 531–534 skip nonpositive attack weights in automatic attacker selection; that is not evidence that an explicitly chosen attack is illegal. Full native filtering remains broader than the audited fields.

## Decision and limits

Do not change the current combat profile or regenerate frozen rules to repair a declaration absent from the supported training closure. Retain the wider-inventory gap and the approximation boundaries. A future change supporting the affected units must capture the actual weight/disable semantics and produce new rule/source identities; existing frozen evidence must remain unchanged.

This diagnosis does not establish full native weapon equivalence or validate dynamic declarations. Lite kill/death/status certainty remains a structural difference. Ordinary v2 BC readiness, selected-checkpoint final evaluation and the full training loop still require their own authorized execution; no strength or convergence result follows from this audit.
