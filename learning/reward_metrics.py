"""Measured, map-matched evidence for the reward controller.

This module does not launch games or infer missing teacher measurements. The
sampler attaches summarize_game(...) as `reward_diagnostics`, and only to the
validation and reward-reference rows this controller reads.
"""
from collections import defaultdict
import math
import hashlib
import json
from statistics import mean

from .features import ENTITY, GLOBAL
from .formats import PLAYERS
from .rewards import RewardConfig, terminal_rewards, transition_reward

MIN_REFERENCE_GAMES = 4
METRICS_VERSION = 'terminal-horizons-v2'
HORIZONS = (5, 10)
_GLOBAL = {name: (index, scale) for index, (name, scale) in enumerate(GLOBAL)}
_ENTITY = {name: (index, scale) for index, (name, scale) in enumerate(ENTITY)}


def _field(observation, name):
    index, scale = _GLOBAL[name]
    # Rollout observations name the vector ``global``; memory snapshots emitted
    # by the Lua host name it ``global_features``. Both are the same vector.
    values = observation.get('global')
    if values is None or len(values) == 0:
        values = observation.get('global_features', [])
    return float(values[index]) * scale if values is not None and len(values) > index else None


def _own_units(observation, side):
    units = {}
    for entity in observation.get('spatial', {}).get('entities', []):
        if entity.get('side') != side:
            continue
        values = entity.get('features', [])
        def get(name):
            index, scale = _ENTITY[name]
            return float(values[index]) * scale
        if len(values) >= 18:
            units[str(entity['id'])] = (get('hp'), get('max_hp'))
    total = _field(observation, 'own_units')
    # An entity list capped at 128 must not turn omitted own units into deaths.
    complete = total is not None and abs(total - len(units)) < 1e-6 and total < 160
    return units, complete


def _snapshot(row, after=False):
    if after and row.get('reward_after') and row.get('memory_write'):
        return dict(row['memory_write'], reward_raw=row['reward_after'], turn=row['turn'])
    return row


def _horizon(rows, side, turn):
    selected = [row for row in rows if int(row['turn']) <= turn]
    if not selected:
        return None
    last = selected[-1]
    absorbing = last.get('metric_event') in ('eliminated', 'terminal')
    if not absorbing and not any(int(row['turn']) == turn for row in selected):
        return None
    raw = last.get('reward_after') or last.get('reward_raw')
    if not raw:
        return None
    snapshots = []
    for row in selected:
        snapshots.append(row)
        if row.get('memory_write') and row.get('reward_after'):
            snapshots.append(_snapshot(row, after=True))
    previous, capacity, damage, seen = {}, 0., 0., set()
    leader = None
    complete = True
    for observation in snapshots:
        units, full = _own_units(observation, side)
        complete = complete and full
        for ident, (hp, maximum) in units.items():
            if ident not in seen:
                capacity += maximum
                seen.add(ident)
            if ident in previous:
                damage += max(0., previous[ident][0] - hp)
        if full:
            damage += sum(hp for ident, (hp, _) in previous.items() if ident not in units)
        previous = units
        fraction = _field(observation, 'leader_hp_fraction')
        if fraction is not None:
            leader = float(fraction > 0)
    explored, control = float(raw['explored']), float(raw['control'])
    if last.get('metric_event') == 'eliminated':
        control, leader = 0., 0.
    if not all(math.isfinite(value) for value in (explored, control)) or not 0 <= explored <= 1 or not 0 <= control <= 1:
        return None
    return dict(coverage=explored, control=control, leader_survival=leader,
                loss=damage / capacity if capacity > 0 and complete else None,
                loss_definition='observed-own-hp-decrements/unique-own-unit-max-hp',
                snapshot_turn=int(last['turn']) if absorbing else turn, absorbing=absorbing,
                entity_coverage_complete=complete)


def _reward_statistics(rows, result, side, job):
    config = job.get('reward_config') or rows[0].get('reward_config')
    if config is None or result.get('reason') == 'turn_limit':
        return None
    frozen = RewardConfig(**config)
    expected_terminal = terminal_rewards(result)[side]
    terminal = rows[-1]['terminal_reward'] if rows[-1].get('schema')==6 else expected_terminal
    if terminal!=expected_terminal: raise ValueError('terminal reward differs from game outcome')
    squares = 0.
    for index, row in enumerate(rows):
        final = index == len(rows) - 1
        following = row.get('reward_after', row['reward_raw']) if final else rows[index + 1]['reward_raw']
        next_turn = row['turn'] if final else rows[index + 1]['turn']
        total, pieces = transition_reward(row['reward_raw'], following, frozen, terminal=final,
                                     terminal_reward=terminal if final else 0.,
                                     delta_turn=max(0, next_turn - row['turn']), components=True)
        if row.get('reward_step') is not None and abs(row['reward_step']-total)>1e-9:
            raise ValueError('reward step differs from recorded transition')
        squares += sum(value for name, value in pieces.items() if name != 'terminal') ** 2
    return dict(shaping_square_sum=squares, terminal_square_sum=terminal ** 2, transitions=len(rows))


def summarize_game(records, result, job, snapshots=()):
    """Extract actual own-view metrics; absent horizons remain explicitly missing.

    Loss counts legal own HP decrements (including observed deaths), divided by
    the max HP capacity of each unique own unit observed so far. Recruitment
    cannot hide damage by raising aggregate own HP. Truncated entity snapshots
    yield no loss metric rather than a guessed death count.
    """
    meta = job.get('meta', {})
    groups = defaultdict(list)
    for index, row in enumerate(records):
        if row.get('reward_raw') and row.get('committed', True):
            groups[int(row['side'])].append((int(row['turn']), row.get('decision', index), row))
    if not result.get('faults'):
        survivors = result.get('survivors')
        for snapshot in snapshots:
            side = int(snapshot['side'])
            event = snapshot.get('metric_event')
            eliminated = event == 'eliminated' and survivors is not None and side not in survivors and str(side) not in survivors
            terminal = event == 'terminal' and not result.get('truncated') and result.get('reason') in ('victory','last_team','last_leader')
            if not (eliminated or terminal or event == 'initial'):
                continue
            # Diagnostic-only observations have no action, post-action memory or
            # bootstrap value. They must never become supervised/on-policy rows.
            row = {k: snapshot[k] for k in ('side','turn','global','spatial','reward_raw',
                   'source','teacher','format','rules_version','metric_event') if k in snapshot}
            groups[side].append((int(row['turn']), -1 if event=='initial' else float('inf'), row))
    diagnostics = []
    factions = result.get('factions') or job.get('factions', [])
    for side, indexed in sorted(groups.items()):
        rows = [item[2] for item in sorted(indexed, key=lambda item: item[:2])]
        horizons = {str(turn): _horizon(rows, side, turn) for turn in HORIZONS}
        first = rows[0]
        teacher = first.get('teacher')
        source = first.get('source', 'astra' if teacher else 'policy')
        diagnostic = dict(game_id=job['id'], game_family=job.get('game_family', job['id']), side=side,metrics_version=METRICS_VERSION,
                          format=meta.get('format', first.get('format')), engine_id=job.get('engine', 'native'),
                          rules_version=job.get('rules_version', first.get('rules_version', 'native-1.18.8' if job.get('engine', 'native') == 'native' else None)),
                          map=meta.get('map'), map_sha256=meta.get('map_sha256'),
                          map_partition=meta.get('map_partition'), context=meta.get('context', 'baseline_partner' if job.get('teams') else 'solo'),
                          faction=factions[side - 1] if len(factions) >= side else None,
                          source=source, teacher=teacher, faults=result.get('faults', []), horizons=horizons)
        missing = [f'turn{turn}' for turn in HORIZONS if horizons[str(turn)] is None]
        for name in ('format', 'map', 'map_sha256', 'map_partition', 'faction', 'rules_version'):
            if diagnostic[name] is None:
                missing.append(name)
        if all(horizons.values()):
            survivors = result.get('survivors')
            diagnostic.update(coverage5=horizons['5']['coverage'], coverage10=horizons['10']['coverage'],
                              control=mean(horizons[str(turn)]['control'] for turn in HORIZONS),
                              leader_survival=float(side in survivors or str(side) in survivors) if survivors is not None else horizons['10']['leader_survival'],
                              loss=horizons['10']['loss'])
            missing.extend(name for name in ('leader_survival', 'loss') if diagnostic[name] is None)
        diagnostic['complete'] = not missing and not diagnostic['faults']
        diagnostic['missing'] = missing
        action_rows = [row for row in rows if not row.get('metric_event')]
        diagnostic['reward_statistics'] = _reward_statistics(action_rows, result, side, job) if action_rows else None
        diagnostics.append(diagnostic)
    return diagnostics


def _stratum(row):
    return tuple(row.get(name) for name in ('format', 'engine_id', 'rules_version', 'map', 'map_sha256', 'faction', 'context','metrics_version'))


def _diagnostics(evidence):
    for entry in evidence:
        if entry.get('status') not in (None, 'complete') or entry.get('faults') or entry.get('result', {}).get('faults'):
            continue
        rows = entry.get('reward_diagnostics', [entry] if 'horizons' in entry else [])
        for row in rows:
            if row.get('complete') and not row.get('faults'):
                yield row


def _official_score(result, side):
    # Keep formal score independent of training reward centering.
    if result.get('teams'):
        winner = result['winning_team']
        return 1. if not winner else 3. if result['teams'][side - 1] == winner else 0.
    if len(result['bots']) == 2:
        return 1. if not result['winner'] else 3. if result['winner'] == side else 0.
    ranks = result['rank_points']
    return ranks.get(side, ranks.get(str(side), 0)) / (len(result['bots']) - 1)


def build_control_metrics(validation_jobs, validation_results, teacher_evidence, comparison):
    """Build new complete rotation blocks using genuine, matched Astra games.

    `teacher_evidence` contains completed sampler results with reward_diagnostics
    from dedicated validation-map Astra reference games. Four independent game
    families per exact map/faction/engine/rules/context stratum are required.
    No training-map or final-holdout fallback exists. Call with newly finished
    panels; the controller additionally deduplicates globally unique block IDs.

    `new_games=0`: PPO collection supplies its own incremental trajectory count;
    validation games here contribute evidence, never a second count of games.
    """
    references = defaultdict(dict)
    for row in _diagnostics(teacher_evidence):
        if row.get('source') != 'astra' or row.get('teacher') != 'gpt6astra' or row.get('map_partition') != 'validation':
            continue
        references[_stratum(row)][row['game_family']] = row
    lookup = {row['id']: row for row in validation_results}
    grouped = defaultdict(list)
    excluded = []
    for job in validation_jobs:
        meta = job.get('meta', {})
        if meta.get('map_partition') != 'validation':
            excluded.append(dict(job=job['id'], reason='not validation partition'))
            continue
        if not meta.get('map_sha256'):
            excluded.append(dict(job=job['id'], reason='missing map sha256'))
            continue
        group = (meta.get('format'), job.get('engine', 'native'), meta.get('label'), meta.get('control'), meta.get('block'))
        grouped[group].append(job)
    blocks, statistics = [], []
    for group, jobs in sorted(grouped.items(), key=lambda item: str(item[0])):
        fmt, engine, label, opponent, block_index = group
        contexts = {job['meta']['context'] for job in jobs}
        expected = PLAYERS.get(fmt, 0)
        full = expected > 0 and len(jobs) == expected * len(contexts) and all(
            {job['meta']['rotation'] for job in jobs if job['meta']['context'] == context} == set(range(expected)) for context in contexts)
        full = full and all(lookup.get(job['id'], {}).get('status') == 'complete' and not lookup[job['id']].get('result', {}).get('faults') for job in jobs)
        if not full:
            excluded.append(dict(block=str(group), reason='incomplete or faulted rotation block'))
            continue
        calibrated = defaultdict(list)
        scores, missing = [], []
        local_statistics = []
        for job in jobs:
            outcome = lookup[job['id']]
            actual = {row['side']: row for row in _diagnostics([outcome])}
            policy_sides, control_sides = job['meta']['policy_sides'], job['meta']['control_sides']
            scores.append(mean(_official_score(outcome['result'], side) for side in policy_sides) - mean(_official_score(outcome['result'], side) for side in control_sides))
            for side in policy_sides:
                row = actual.get(side)
                if row is None:
                    missing.append(dict(job=job['id'], side=side, reason='missing complete policy horizons'))
                    continue
                key = _stratum(row)
                reference = list(references.get(key, {}).values())
                if len(reference) < MIN_REFERENCE_GAMES:
                    missing.append(dict(job=job['id'], side=side, reason='insufficient exact Astra calibration',
                                        stratum=list(key), reference_families=len(reference)))
                    continue
                values = {name: float(row[name]) for name in ('coverage5', 'coverage10', 'control', 'leader_survival', 'loss')}
                values.update({f'astra_{name}': mean(float(ref[name]) for ref in reference) for name in values})
                calibrated[(row['map'], row['faction'])].append(values)
                if row.get('reward_statistics'):
                    local_statistics.append(row['reward_statistics'])
        if missing:
            excluded.extend(missing)
            continue
        strata = [dict(map=map_name, faction=faction, **{name: mean(row[name] for row in rows) for name in rows[0]})
                  for (map_name, faction), rows in sorted(calibrated.items())]
        if not strata:
            excluded.append(dict(block=str(group), reason='missing calibrated strata'))
            continue
        # A digest of the frozen job IDs avoids collisions across policy versions,
        # opponents, engines and repeated panel labels/block indices.
        frozen = dict(group=group, jobs=[dict(id=job['id'], policy=job['meta'].get('policy'),
                                              family=job.get('game_family'), seed=job.get('seed'),
                                              map_sha256=job['meta'].get('map_sha256'))
                                          for job in sorted(jobs, key=lambda job: job['id'])])
        identity = hashlib.sha256(json.dumps(frozen, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        score = mean(scores)
        blocks.append(dict(id=identity, format=fmt, engine_id=engine, label=label, control=opponent,
                           block=block_index, complete=True, faults=[], partition='validation', strata=strata,
                           fixed_score=score if engine != 'native' else None,
                           native_score=score if engine == 'native' else None,
                           comparison_status=comparison.get(fmt, {}).get('status') if isinstance(comparison, dict) else None))
        statistics.extend(local_statistics)
    metrics = dict(partition='validation', new_games=0, faulted_games=0, validation_blocks=blocks,
                   excluded_evidence=excluded, reference_min_families=MIN_REFERENCE_GAMES)
    count = sum(row['transitions'] for row in statistics)
    if count:
        metrics.update(shaping_rms=math.sqrt(sum(row['shaping_square_sum'] for row in statistics) / count),
                       terminal_rms=math.sqrt(sum(row['terminal_square_sum'] for row in statistics) / count))
    return metrics
