"""Resolve frozen job roles before either backend loads executable teacher code."""
import copy
from pathlib import Path

from .registry import ROLES, describe, execution_identity


def resolve_job(job, engine):
    roles = job.get('teacher_roles')
    if roles is None:
        return {}, None
    from ..formats import infer_format
    if job['format'] != infer_format(job):
        raise ValueError('job teacher format differs from the actual seats')
    if set(roles) != set(ROLES):
        raise ValueError('job teacher roles are incomplete')
    packages = {}
    for spec in roles.values():
        path = str(Path(spec['package']).resolve())
        if path not in packages:
            packages[path] = describe(path, job['format'])
        if spec != packages[path]:
            raise ValueError('job teacher differs from the frozen descriptor')
    seats = {str(side): packages[str(Path(bot).resolve())] for side, bot in enumerate(job['bots'], 1)
             if bot != 'baseline' and str(Path(bot).resolve()) in packages}
    learning = job.get('learning') or {}
    query = None
    if learning.get('dagger_teacher'):
        query = roles['supervision']
        if Path(learning['dagger_teacher']).resolve() != Path(query['package']).resolve():
            raise ValueError('DAgger package differs from supervision role')
    return seats, query


def prepare_job(job, engine):
    """Legacy jobs keep their frozen behavior; versioned jobs pin every teacher seat."""
    seats, query = resolve_job(job, engine)
    result = copy.deepcopy(job)
    if job.get('teacher_roles') is None:
        return result
    result['seat_timeouts'] = dict(job.get('seat_timeouts', {}))
    result['seat_entries'] = dict(job.get('seat_entries', {}))
    for side, spec in seats.items():
        result['seat_timeouts'][side] = {k: spec[k] for k in ('timeout', 'first_timeout')}
        result['seat_entries'][side] = spec['entry']
    for side, training in (result.get('learning') or {}).get('sides', {}).items():
        if training.get('teacher'):
            if str(side) not in seats:
                raise ValueError('supervised seat has no frozen teacher package')
            spec = seats[str(side)]
            role='reward_reference' if job.get('meta',{}).get('phase')=='reward_reference' else 'supervision'
            if spec != job['teacher_roles'][role]:
                raise ValueError('supervised seat differs from '+role+' role')
            training.update(teacher=spec['teacher'], teacher_identity=execution_identity(spec, engine))
    if query:
        result['learning']['dagger_spec'] = query
        for training in result['learning']['sides'].values():
            if not training.get('teacher'):
                training.update(dagger_entry=query['entry'], dagger_timeout=query['timeout'],
                                dagger_first_timeout=query['first_timeout'],
                                dagger_identity=execution_identity(query, engine))
    return result


def dagger_rows(records, identity, *, value_valid=False):
    """Keep every student's committed history and every available teacher intent."""
    rows = []
    for row in records:
        label = row.get('dagger') or {}
        context = {k: v for k, v in row.items() if k != 'dagger'}
        context.update(identity, choice=-1, source='teacher' if identity.get('teacher_contract') else 'astra',
                       data_pool='dagger', value_valid=value_valid)
        if identity.get('teacher_contract'):
            context['teacher_impl'] = identity['teacher']
        if label:
            context['teacher_query'] = {k: v for k, v in label.items() if k not in ('actual', 'intent')}
        if not label.get('error') and label.get('actual'):
            context.update(label)
        rows.append(context)
    return rows


def query_metrics(records):
    labels = [row['dagger'] for row in records if row.get('dagger')]
    times = sorted(label.get('query_ms', 0) for label in labels)
    return dict(queries=len(labels), valid=sum(not r.get('error') and r.get('choice', -1) >= 0 for r in labels),
                errors=[r['error'] for r in labels if r.get('error')],
                unmatched=sum(not r.get('error') and r.get('choice', -1) < 0 for r in labels),
                seconds=sum(times)/1000, max_ms=max(times, default=0),
                p95_ms=times[min(len(times)-1, int(len(times)*.95))] if times else 0)
