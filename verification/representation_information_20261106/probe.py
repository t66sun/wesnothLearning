"""Audit exact spatial/history information losses without training any model."""
import argparse
from collections import Counter, deque
import copy
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fixtures
from learning.common import sha256
from learning.data import advantages
from learning.features import GLOBAL, TERRAIN_TYPES, schema
from learning.model import ARCHITECTURE, Policy, batch
from learning.sequences import attach_histories


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False).encode()).hexdigest()


def tensor_inputs(row):
    inputs = batch([row], dtype=torch.float64)
    named = dict(zip(('global', 'opponents', 'actions', 'opponent_mask', 'action_mask'), inputs[:5]))
    named.update({key: value for key, value in inputs[5].items() if torch.is_tensor(value)})
    return named


def differences(a, b):
    left, right = tensor_inputs(a), tensor_inputs(b)
    result = {}
    for key in left:
        x, y = left[key], right[key]
        if x.shape != y.shape:
            result[key] = dict(left_shape=list(x.shape), right_shape=list(y.shape))
        elif not torch.equal(x, y):
            indices = torch.nonzero(x != y).tolist()
            result[key] = dict(count=len(indices), first_indices=indices[:8],
                max_abs=float((x.to(torch.float64)-y.to(torch.float64)).abs().max()))
    return result


def patch_multiset(board):
    """Two 3x3 convs see 5x5; include validity to bind intermediate zero padding."""
    values = np.asarray(board, dtype=np.float64)
    values = np.concatenate([values, np.ones((1, 16, 16))])
    padded = np.pad(values, ((0, 0), (2, 2), (2, 2)))
    return Counter(hashlib.sha256(padded[:, y:y+5, x:x+5].tobytes()).hexdigest()
                   for y in range(16) for x in range(16))


def neighbors(x, y, width, height):
    q, r = x-1, y-1-(x-1)//2
    for dq, dr in ((1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1)):
        nq, nr = q+dq, r+dr
        nx, ny = nq+1, nr+nq//2+1
        if 1 <= nx <= width and 1 <= ny <= height:
            yield nx, ny


def public_distance(spec, start, goal, *, water_passable=False):
    width, height = spec['width'], spec['height']
    queue, seen = deque([(start, 0)]), {start}
    while queue:
        position, cost = queue.popleft()
        if position == goal:
            return cost
        for nx, ny in neighbors(*position, width, height):
            terrain = spec['terrain'][(ny-1)*width+nx-1]
            if (nx, ny) not in seen and (terrain != 'Ww' or water_passable):
                seen.add((nx, ny))
                queue.append(((nx, ny), cost+1))
    return None


def intents(row):
    fields = ('kind', 'type', 'x', 'y', 'tx', 'ty', 'ex', 'ey', 'weapon', 'full')
    return [{key: action[key] for key in fields if key in action} for action in row['candidates']]


def spatial_cases():
    result, raw = {}, {}
    for name, (a, b) in fixtures.pairs().items():
        _, original_a = fixtures.capture(a)
        _, original_b = fixtures.capture(b)
        row_a, row_b = fixtures.actor_row(original_a), fixtures.actor_row(original_b)
        changed = [dict(x=i % a['width']+1, y=i//a['width']+1, left=x, right=y)
                   for i, (x, y) in enumerate(zip(a['terrain'], b['terrain'])) if x != y]
        diff = differences(row_a, row_b)
        pools = patch_multiset(row_a['spatial']['board']) == patch_multiset(row_b['spatial']['board'])
        result[name] = dict(terrain_changes=changed, candidate_count=[len(row_a['candidates']), len(row_b['candidates'])],
            candidate_intents_equal=intents(row_a) == intents(row_b), tensor_differences=diff,
            all_actor_tensors_equal=not diff, board_equal=row_a['spatial']['board'] == row_b['spatial']['board'],
            boundary_aware_5x5_multisets_equal=pools, actor_input_sha256=[digest(row_a), digest(row_b)])
        raw[name] = dict(left=dict(spec=fixtures.public_spec(a), actor=row_a),
                         right=dict(spec=fixtures.public_spec(b), actor=row_b))
        if name == 'resampling_connectivity':
            witness = result[name]['public_route'] = dict(start=[4, 8], goal=[28, 8],
                ground_steps=[public_distance(s, (4, 8), (28, 8)) for s in (a, b)],
                water_capable_steps=[public_distance(s, (4, 8), (28, 8), water_passable=True) for s in (a, b)])
            assert witness['ground_steps'][0] is not None and witness['ground_steps'][1] is None
            assert result[name]['all_actor_tensors_equal']
            assert len(row_a['candidates']) > 1
        elif name == 'pooling_location':
            assert set(diff) == {'board'} and pools and result[name]['candidate_intents_equal']
            result[name]['public_hill_distance'] = [public_distance(s, (2, 5), point)
                                                   for s, point in ((a, (8, 5)), (b, (8, 11)))]
            numeric = []
            # These are arithmetic witnesses, not claims about learned behavior.
            for seed in (3, 41):
                torch.manual_seed(seed)
                model = Policy('duel').double().eval()
                with torch.no_grad():
                    logits, values = model(*batch([row_a, row_b], dtype=torch.float64))
                numeric.append(dict(seed=seed, max_logit_abs=float((logits[0]-logits[1]).abs().max()),
                                    value_abs=float((values[0]-values[1]).abs())))
            result[name]['floating_point_sanity_only'] = numeric
            assert all(entry['max_logit_abs'] < 1e-12 and entry['value_abs'] < 1e-12 for entry in numeric)
        elif name in ('local_patch_compensation', 'entity_compensation'):
            assert result[name]['board_equal'] and diff
            assert ('local' in diff) if name == 'local_patch_compensation' else ('entities' in diff)
        elif name == 'knowledge_mask_compensation':
            assert 'board' in diff
            result[name]['classification'] = 'known terrain under fog remains distinct from unexplored terrain'
        else:
            assert result[name]['all_actor_tensors_equal']
            result[name]['classification'] = 'legal partial observability, not encoding loss'
    return result, raw


def history_cases():
    spec, traces = fixtures.within_turn_traces()
    attached = [attach_histories(rows) for rows in traces]
    result = dict(within_turn=dict(
        first_write_equal=traces[0][0]['memory_write'] == traces[1][0]['memory_write'],
        later_public_state_differs=bool(differences(traces[0][2], traces[1][2])),
        final_actor_differences=differences(attached[0][-1], attached[1][-1]),
        retained_histories_equal=attached[0][-1]['_history'] == attached[1][-1]['_history'],
        retained_turns=[r['turn'] for r in attached[0][-1]['_history']],
        scope='Order of two independent legal own moves is omitted; harmful future consequence is not demonstrated.'))
    within = result['within_turn']
    assert within['first_write_equal'] and within['later_public_state_differs']
    assert not within['final_actor_differences'] and within['retained_histories_equal']
    assert within['retained_turns'] == [1]

    current = copy.deepcopy(attached[0][-1])
    current['turn'] = 41
    current['_history'] = []
    for turn in range(1, 41):
        slot = copy.deepcopy(traces[0][0]['memory_write'])
        slot['turn'] = turn
        current['_history'].append(slot)
    model = Policy('duel').double()
    gru_calls = []
    original = model.gru.forward
    def observed(*args, **kwargs):
        gru_calls.append(torch.is_grad_enabled())
        return original(*args, **kwargs)
    cache = {}
    with patch.object(model.gru, 'forward', side_effect=observed):
        logits, _ = model(*batch([current], dtype=torch.float64, history_cache=cache))
    logits.sum().backward()
    result['history_scope'] = dict(raw_prefix_turns=len(current['_history']),
        gru_steps_with_grad=sum(gru_calls), gru_steps_without_grad=len(gru_calls)-sum(gru_calls),
        cached_raw_scenes=len(cache['scenes']), summary_slot_limit=ARCHITECTURE['memory_slots'],
        differentiable_suffix=ARCHITECTURE['replay_turns'])
    assert result['history_scope'] == dict(raw_prefix_turns=40, gru_steps_with_grad=8,
        gru_steps_without_grad=32, cached_raw_scenes=40, summary_slot_limit=32, differentiable_suffix=8)

    # Prove the first historical scene remains an input to the GRU, rather than
    # interpreting similar predictions under arbitrary untrained coefficients.
    row = current['_history'][0]
    result['history_scope']['first_raw_turn_present'] = any(value[0] is row for value in cache['scenes'].values())
    assert result['history_scope']['first_raw_turn_present']
    from learning.rewards import RewardConfig
    credit_rows = [dict(game_id='credit-algebra', side=1, turn=turn, value=0., schema=5,
        reward=1. if turn == 12 else 0., reward_raw=dict(economy=0., control=0., explored=0.),
        reward_config=RewardConfig().to_dict()) for turn in range(1, 13)]
    credit, _ = advantages(credit_rows)
    assert abs(credit[0] - .95**11) < 1e-12 and credit[0] > 0.
    result['reward_credit'] = dict(turns=12, gamma=1., gae_lambda=.95, first_advantage=credit[0],
        explanation='Zero intermediate rewards/values, terminal reward 1: credit propagates beyond eight own turns.')

    seen = fixtures.last_seen_pair()
    last_seen_differences = differences(*seen)
    assert seen[0]['spatial']['board'] == seen[1]['spatial']['board']
    assert 'entities' in last_seen_differences
    result['last_seen_compensation'] = dict(board_equal=True, tensor_differences=last_seen_differences,
        previous_visible_positions=[[6, 4], [7, 4]], current_visible_enemies=0,
        explanation='Previously observed enemy location and age remain in entity inputs after it becomes fogged.')
    return result, dict(public_initial_spec=spec, ordered_move_traces=traces, last_seen=seen,
                        long_prefix_probe='40 repeated public first-write scenes with turns 1..40; current turn 41')


def terrain_scalar():
    values = np.asarray([i/max(1, len(TERRAIN_TYPES)-1) for i in range(len(TERRAIN_TYPES))], dtype=np.float32)
    assert len(np.unique(values)) == len(TERRAIN_TYPES)
    return dict(vocabulary_size=len(TERRAIN_TYPES), unique_float32_scalars=len(np.unique(values)),
                minimum_adjacent_difference=float(np.diff(values).min()),
                classification='Individual declared terrain IDs remain distinguishable; aggregation and ordinal bias are separate.')


def run(destination):
    destination.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(1)
    spatial, raw_spatial = spatial_cases()
    history, raw_history = history_cases()
    source_paths = ['lua/spatial.lua', 'lua/observation.lua', 'lua/relational.lua', 'lua/bot.lua',
                    'learning/model.py', 'learning/sequences.py', 'learning/lite_policy.py',
                    'learning/data.py', 'learning/rewards.py', 'learning/features.py']
    report = dict(schema=1, spatial=spatial, history=history, terrain_scalar=terrain_scalar(),
                  features=schema(), architecture=ARCHITECTURE,
                  source_sha256={name: sha256(ROOT/name) for name in source_paths},
                  python=sys.version, torch=torch.__version__, numpy=np.__version__,
                  scope='Synthetic legal state/transition fixtures only; no match, collection, optimizer or training.')
    fixtures_path = destination/'paired_fixtures.json'
    fixtures_path.write_text(json.dumps(dict(synthetic_rules=fixtures.rules(), spatial=raw_spatial,
        history=raw_history), sort_keys=True, separators=(',', ':'))+'\n', encoding='utf-8')
    report['paired_fixtures_sha256'] = sha256(fixtures_path)
    (destination/'results.json').write_text(json.dumps(report, sort_keys=True, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(spatial={key: dict(actor_equal=value['all_actor_tensors_equal'],
        differing_tensors=list(value['tensor_differences'])) for key, value in spatial.items()},
        history=history, terrain_scalar=report['terrain_scalar']), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    run(parser.parse_args().output)
