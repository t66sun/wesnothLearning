"""Stable training entry point.

Learners live in :mod:`learning.bc` and :mod:`learning.ppo`; callers keep
importing ``train``, ``checkpoint``, ``restore_rng``, ``auxiliary_loss`` and
``imitation_quality`` from here.
"""
from . import bc, ppo
from .bc import auxiliary_loss, imitation_quality
from .checkpoints import checkpoint, restore_rng


def train(model, optimizer, records, method, epochs=4, minibatch=256, deadline=float('inf'),
          progress=None, on_step=None, bc_records=None, shaping_weight=None, entropy=.01, bc_aux=.1,
          allow_policy_rehearsal=False, plan_seed=0, rehearsal_exclude=None):
    if method not in ('bc', 'ppo'):
        raise ValueError('method must be bc or ppo')
    if method == 'bc':
        return bc.update(model, optimizer, records, bc_records=bc_records, epochs=epochs, minibatch=minibatch, deadline=deadline,
                         progress=progress, on_step=on_step)
    return ppo.update(model, optimizer, records, bc_records=bc_records, epochs=epochs, minibatch=minibatch,
                      deadline=deadline, progress=progress, on_step=on_step, shaping_weight=shaping_weight,
                      entropy=entropy, bc_aux=bc_aux, allow_policy_rehearsal=allow_policy_rehearsal,
                      plan_seed=plan_seed,rehearsal_exclude=rehearsal_exclude)
