"""The fixed competition objective, separate from engine sampling limits."""

LEGACY_TASK = 'continuation-v1'
TASK_ID = 'official-score-30-v1'
TASK_TURNS = 30
FORMULA_ID = 'v5-official-score-potential-1'


def require_task(task_id):
    if task_id != TASK_ID:
        raise ValueError('training task differs: use a new official-score-30-v1 run; '
                         'legacy weights require explicit weights-only initialization')


def validate_run(config):
    require_task(config.get('task_id'))
    if config.get('training_max_turns') != TASK_TURNS:
        raise ValueError('training_max_turns must be 30 for official-score-30-v1')


def reward_config(task_id=TASK_ID, **changes):
    from .rewards import RewardConfig
    if task_id == LEGACY_TASK:
        return RewardConfig(**changes).to_dict()
    require_task(task_id)
    return RewardConfig(task_id=TASK_ID, reward_formula_id=FORMULA_ID,
                        explore=0., gamma=1., **changes).to_dict()


def job_reward(job):
    from .rewards import RewardConfig
    task_id = job.get('task_id', LEGACY_TASK)
    config = job.get('reward_config') or reward_config(task_id)
    if RewardConfig(**config).task_id != task_id:
        raise ValueError('job task differs from reward configuration')
    if task_id == TASK_ID:
        limit = job.get('game_spec', {}).get('max_turns', job.get('max_turns', TASK_TURNS))
        if not 1 <= limit <= TASK_TURNS or job.get('max_turns', limit) != limit:
            raise ValueError('finite task requires matching sample limits in [1, 30]')
    return config


def bind_result(result, job):
    """A turn-limit result is final only after the complete declared task round.

    Native reports the completed round (30); Lite has advanced to round 31.
    The actual engine cap distinguishes that from a cut after round 29.
    """
    task_id = job.get('task_id', LEGACY_TASK)
    if task_id == LEGACY_TASK:
        return result
    require_task(task_id)
    limit = job.get('game_spec', {}).get('max_turns', job.get('max_turns', TASK_TURNS))
    if not 1 <= limit <= TASK_TURNS:
        raise ValueError('finite task sample limit must be in [1, 30]')
    if job.get('max_turns', limit) != limit:
        raise ValueError('job and engine sampling limits differ')
    capped = result.get('reason') == 'turn_limit'
    if capped and result.get('turns', 0) < limit:
        raise ValueError('turn-limit result precedes the complete sampling round')
    result.update(task_id=task_id, task_terminal=not capped or limit == TASK_TURNS)
    return result


def is_truncated(result, side):
    if result.get('reason') != 'turn_limit':
        return False
    if result.get('task_id', LEGACY_TASK) == TASK_ID and result['task_terminal']:
        return False
    survivors = result.get('survivors')
    if survivors is None:
        return True
    if result.get('teams'):
        return any(result['teams'][s-1] == result['teams'][side-1] for s in survivors)
    return side in survivors


def require_rows_task(rows, task_id):
    require_task(task_id)
    for row in rows:
        if row.get('task_id') != task_id or row.get('reward_config', {}).get('task_id') != task_id:
            raise ValueError('training data task differs from the frozen run; legacy rows cannot be relabelled')


def value_target(row):
    """BC and complete PPO returns share the same terminal-potential convention."""
    from .rewards import terminal_reward_key
    target = row.get(terminal_reward_key(row)) or 0.
    if row.get('task_id') == TASK_ID and row.get('value_valid', True):
        raw, config = row['reward_raw'], row['reward_config']
        target -= config['economy'] * raw['economy'] + config['control'] * raw['control']
    return target
