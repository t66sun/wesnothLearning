# Matched recruit supervision on the frozen team v10 checkpoint

## Inputs and stopping rule

Use the team2v2 branch at Ubuntu `/home/tongshu/acceptance/team_bc_branch_20261102` (runtime source `bdecbbd4f9f18fc6c1b7a01bc6ff4bce5b3e5e30`). The checkpoint SHA-256 is `b74350699b445e63cdd11fd07f317e0d818fe3d3166d49705b1342b00336035e`. Its saved model, Adam state and Python/Torch RNG initialize each arm independently. Use its 48 frozen teacher shards and the original v2 extension. Verify the files against the branch's input hash inventory.

Keep the committed 2,048 training rows (seed 20261110), 1,024 validation rows (seed 20261101), all legal recurrent prefixes, minibatch 256, one CPU thread and original equal-window sampler. Fifty-four windows at four windows per step imply 14 updates per epoch. Each arm runs 16 complete epochs, **224 updates**, 896 window visits, a 600-second wall limit including endpoint measurement and a 1,500-second external limit across both arms and preparation. One seed and one endpoint per arm. Stop on a failed precondition, deadline or mismatch. Treat interrupted arms as incomplete.

## Single comparison

Run the original BC objective as control. For the experiment, only when the supervised action is recruit, replace the auxiliary actor identity for each recruit candidate with its unit type. All placements of that type contribute to the same marginal. Keep exact-action cross-entropy, the auxiliary coefficient of 0.1, kind and destination terms, all other rows, the value loss and optimizer unchanged. This intervention applies only to the diagnostic's loss calculation. The policy receives its original inputs.

Before fitting, verify the analytical swap case, the recorded v10 validation and training counts, the four gate thresholds and common row and initial-state hashes. Record the ordered list of sampled windows by update. Restore each arm from the checkpoint. Require matching initial hashes, ordered visits and decisions seen before comparing endpoints. Write the evidence under this new directory. Frozen input directories stay read-only.

## Decision

The primary outcome is the complete held-out BC gate, computed with the original imitation function and frozen corpus, coverage and scenario-design evidence. Validation requires at least 32 samples per scored class, cross-entropy below 85% of uniform, overall accuracy at least 40%, recruit at least 60%, move and attack at least 35%. The recorded v10 start is 34/85 recruits, 426/667 moves and 56/141 attacks. Recruit requires 51/85. The original nonblocking opening probe stays recorded.

Report train and validation recruit exact/type/slot, all original validation class counts, CE, overall accuracy, elapsed time, step counts and input identities. A passing experiment with a failing control supports a current-profile ordinary BC check. A passing control cannot credit this intervention for crossing the gate. A failing experimental arm does not support adopting this loss from the probe. This copy experiment performs no ordinary run, collection, PPO, final evaluation or export.
