"""Full-set BC representation diagnostics and an explicitly invoked tiny-fit probe.

Input aliases describe indistinguishable model inputs. They never create action
equivalence classes or soften labels. Diagnostics accept uncovered raw decisions.
"""
from collections import Counter, defaultdict
import copy
import hashlib
import json
import random


INTENT_FIELDS = dict(end_turn=(), recruit=('type', 'x', 'y'),
    move=('x', 'y', 'tx', 'ty', 'full'), attack=('x', 'y', 'tx', 'ty', 'weapon'),
    move_attack=('x', 'y', 'tx', 'ty', 'ex', 'ey', 'weapon'))


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _entity_input(entity):
    """Only features/type embedding enter the entity projector; IDs are handles."""
    return dict(features=entity['features'], type_index=entity['type_index'])


def _scene_input(row):
    spatial = row['spatial']
    return dict(global_features=row['global'], opponents=row['opponents'],
                board=spatial['board'], entities=[_entity_input(e) for e in spatial['entities']])


def _candidate_input(candidate, scene_entities):
    """Mirror Policy.gather: attended scene token wins over candidate payload.

    Different IDs with identical scene token features receive identical attention
    outputs (the model has no positional embedding). Keep attended/direct paths
    distinct; equal direct projections do not prove equal attention outputs.
    """
    result = {key: candidate.get(key) for key in ('features', 'local', 'geometry')}
    for role in ('actor', 'target'):
        entity = candidate.get(role)
        if not entity:
            result[role] = None
        elif entity.get('id') in scene_entities:
            result[role] = dict(path='attended', token=_entity_input(scene_entities[entity['id']]))
        else:
            result[role] = dict(path='direct', token=_entity_input(entity))
    return result


def _decision_input(row, candidates):
    result = _scene_input(row)
    result['candidates'] = candidates
    result['turn'] = row['turn']
    result['history'] = [dict(_scene_input(past), turn=past['turn']) for past in row.get('_history', [])]
    return result


def intent_key(action):
    kind = action.get('kind')
    return kind, tuple(action.get(k) for k in INTENT_FIELDS.get(kind, ()))


def _kind(kind):
    return 'attack' if kind == 'move_attack' else kind or 'unknown'


def _turn_band(turn):
    return 'opening' if turn <= 5 else 'middle' if turn <= 15 else 'late'


def _empty():
    return Counter(decisions=0, covered=0, missing_intent=0, alias_decisions=0,
        teacher_aliased=0, teacher_nonfirst_alias=0, missing_actor=0,
        missing_target=0, missing_local=0, missing_geometry=0)


def _finish(counts):
    result = dict(counts)
    known = counts['decisions'] - counts['missing_intent']
    result['coverage'] = counts['covered'] / known if known else None
    result['coverage_denominator'] = known
    result['nonfirst_alias_rate'] = counts['teacher_nonfirst_alias'] / counts['covered'] if counts['covered'] else None
    return result


def audit_bc(records):
    """Consume the complete fixed validation iterable; no reservoir or rounding."""
    from .features import VERSION
    totals = _empty()
    strata = defaultdict(_empty)
    examples = []
    input_labels = defaultdict(Counter)
    intent_sources = Counter()
    for row in records:
        if row.get('faults'):
            continue
        if row.get('schema') != VERSION:
            raise ValueError('BC audit requires the current schema; old vectors are not new observations')
        candidates = row['candidates']
        selected = row.get('choice', -1)
        intent = None
        for field in ('teacher_intent', 'teacher_action', 'intent', 'actual'):
            if isinstance(row.get(field), dict) and 'kind' in row[field]:
                intent = row[field]
                intent_sources[field] += 1
                break
        if intent is None and 0 <= selected < len(candidates):
            intent = candidates[selected]
            intent_sources['label_only'] += 1
        indices = [i for i, c in enumerate(candidates) if intent is not None and intent_key(c) == intent_key(intent)]
        chosen = selected if selected in indices else indices[0] if indices else None
        kind = _kind(intent.get('kind') if intent else None)
        keys = [('all', 'all'), ('format', row.get('format', 'unknown')),
            ('map', row.get('map', row.get('map_id', 'unknown'))),
            ('faction', row.get('faction', 'unknown')), ('action', kind),
            ('turn', _turn_band(row['turn'])), ('source', row.get('source', 'unknown')),
            ('engine', row.get('engine_id', row.get('engine', 'unknown'))),
            ('format_action', str(row.get('format')) + '/' + kind)]
        groups = defaultdict(list)
        scene_entities = {e['id']: e for e in row['spatial']['entities']}
        candidate_inputs = [_candidate_input(candidate, scene_entities) for candidate in candidates]
        for i, candidate in enumerate(candidates):
            # Candidate-independent context is the same inside a decision. Explicit
            # actor/target/local/geometry are included, unlike schema-3 vector audits.
            groups[_canonical(candidate_inputs[i])].append(i)
        alias = any(len(ids) > 1 for ids in groups.values())
        aliases = next((ids for ids in groups.values() if chosen in ids), []) if chosen is not None else []
        metrics = dict(decisions=1, covered=int(chosen is not None), missing_intent=int(intent is None),
            alias_decisions=int(alias), teacher_aliased=int(len(aliases) > 1),
            teacher_nonfirst_alias=int(bool(aliases) and chosen != aliases[0]),
            missing_actor=int(any(c.get('kind') != 'end_turn' and not c.get('actor') for c in candidates)),
            missing_target=int(any(c.get('kind') in ('attack', 'move_attack') and not c.get('target') for c in candidates)),
            missing_local=int(any(not c.get('local') for c in candidates)),
            missing_geometry=int(any(not c.get('geometry') for c in candidates)))
        totals.update(metrics)
        for axis, value in keys:
            strata[(axis, str(value))].update(metrics)
        if chosen is not None:
            context = _decision_input(row, candidate_inputs)
            digest = hashlib.sha256(_canonical(context).encode()).hexdigest()
            input_labels[digest][chosen] += 1
        if aliases and chosen != aliases[0] and len(examples) < 32:
            examples.append(dict(game_family=row.get('game_family'), game_id=row.get('game_id'),
                side=row.get('side'), turn=row['turn'], choice=chosen, aliases=aliases,
                intents=[dict(candidates[i]) for i in aliases]))
    conflicts = [values for values in input_labels.values() if len(values) > 1]
    by_axis = defaultdict(dict)
    for (axis, value), counts in sorted(strata.items()):
        by_axis[axis][value] = _finish(counts)
    coverage = totals['covered'] / max(1, totals['decisions'] - totals['missing_intent'])
    class_checks = {kind: by_axis.get('action', {}).get(kind, {}).get('coverage') for kind in ('recruit', 'move', 'attack')}
    sufficient = totals['missing_intent'] == 0 and all(v is not None for v in class_checks.values())
    return dict(schema=VERSION, status='measured' if sufficient else 'inconclusive',
        totals=_finish(totals), strata=dict(by_axis), intent_sources=dict(intent_sources),
        identical_decision_inputs=len(input_labels), conflicting_exact_input_groups=len(conflicts),
        conflicting_exact_input_decisions=sum(sum(c.values()) for c in conflicts),
        nonfirst_alias_examples=examples,
        coverage_pass=sufficient and coverage >= .90 and all(v >= .80 for v in class_checks.values()),
        interpretation='Input identity is a representation collision, never evidence of equal action value. Actual-only coverage may differ after interrupted movement.')


def small_set(records, format_name, size=64, seed=19):
    """Choose fixed, kind-stratified supervised rows after complete prefix replay."""
    from .sequences import attach_histories
    rows = list(records)
    if not all('_history' in r for r in rows):
        rows = attach_histories(rows)
    unique = {}
    for row in rows:
        if row.get('format') == format_name and row.get('choice', -1) >= 0 and not row.get('faults'):
            decision=row.get('decision',row.get('action_index'))
            if decision is None: decision=_canonical(row)
            identity = (row.get('game_id'), row.get('side'), row['turn'],decision)
            unique.setdefault(identity, row)
    rows = list(unique.values())
    rng = random.Random(seed)
    buckets = defaultdict(list)
    for row in rows:
        buckets[_kind(row['candidates'][row['choice']]['kind'])].append(row)
    if size < 3 or len(rows) < size or any(not buckets[k] for k in ('recruit', 'move', 'attack')):
        raise ValueError('tiny fit needs 64 unique decisions including recruit/move/attack')
    chosen = []
    for kind in ('recruit', 'move', 'attack'):
        chosen.append(rng.choice(buckets[kind]))
    remaining = [r for r in rows if all(r is not c for c in chosen)]
    rng.shuffle(remaining)
    chosen.extend(remaining[:size-len(chosen)])
    return chosen


def fit_small_set(model, records, steps=1000, learning_rate=1e-3, seed=19):
    """Explicit future diagnostic entry point; trains a copy, never writes a checkpoint."""
    import torch
    from .model import batch
    if steps < 1 or learning_rate <= 0:
        raise ValueError('tiny fit needs positive steps and learning rate')
    rows = small_set(records, model.format_name, seed=seed)
    probe = copy.deepcopy(model)
    device = next(probe.parameters()).device
    target = torch.tensor([r['choice'] for r in rows], device=device)
    optimizer = torch.optim.Adam(probe.parameters(), lr=learning_rate)
    # manual_seed seeds every CUDA generator, so restore every initialized device
    # as well as CPU; the probe must not perturb another format's random stream.
    with torch.random.fork_rng(devices=list(range(torch.cuda.device_count())) if torch.cuda.is_available() else []):
        torch.manual_seed(seed)
        probe.train()
        for _ in range(steps):
            optimizer.zero_grad()
            logits, _ = probe(*batch(rows, device))
            loss = torch.nn.functional.cross_entropy(logits, target)
            if not torch.isfinite(loss):
                raise ValueError('tiny fit produced nonfinite loss')
            loss.backward()
            optimizer.step()
        probe.eval()
        with torch.no_grad():
            logits, _ = probe(*batch(rows, device))
            predicted = logits.argmax(1).tolist()
            loss = float(torch.nn.functional.cross_entropy(logits, target))
    correct = sum(p == r['choice'] for p, r in zip(predicted, rows))
    by_kind = defaultdict(lambda: dict(samples=0, correct=0))
    equivalent = equivalent_count = 0
    for p, row in zip(predicted, rows):
        metric = by_kind[_kind(row['candidates'][row['choice']]['kind'])]
        metric['samples'] += 1
        metric['correct'] += int(p == row['choice'])
        if row.get('equivalence_evidence') and row.get('equivalent_choices'):
            equivalent_count += 1
            equivalent += int(p in set(row['equivalent_choices']) | {row['choice']})
    return dict(format=model.format_name, samples=len(rows), steps=steps, cross_entropy=loss,
        accuracy=correct / len(rows), passed=correct / len(rows) >= .90,
        action_types=dict(by_kind), equivalent_samples=equivalent_count,
        equivalent_accuracy=equivalent / equivalent_count if equivalent_count else None,
        seed=seed, status='measured', changes_original_model=False)
