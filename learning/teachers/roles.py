"""Experiment role routing; legacy runs retain their original frozen behavior."""
from .registry import ROLES, role, execution_identity
from .provenance import engine_identity, TEACHER_FIELDS


def descriptor(runner, name='supervision'):
    return role(getattr(runner,'manifest',{}),runner.fmt,name)


def package(runner, name='supervision'):
    spec=descriptor(runner,name)
    return spec['package'] if spec else runner.teachers[0]


def identity(runner, name='supervision', engine=None):
    spec=descriptor(runner,name)
    if spec is None:return None
    engine=engine or runner.config['engine']
    return dict(engine_identity(engine),**execution_identity(spec,engine))


def identities(runner, engine=None):
    if descriptor(runner) is None:return {}
    return {name:identity(runner,name,engine) for name in ROLES}


def expected_supervision(runner):
    if descriptor(runner) is None:return None
    return {engine:identity(runner,engine=engine) for engine in ('native','lite')}


def fixed(runner, engine=None, name='opponent'):
    engine=engine or runner.config['engine']
    if descriptor(runner,name) is None:
        if engine=='native':return runner.native_fixed if hasattr(runner,'native_fixed') else runner.fixed
        return runner.teachers
    return [package(runner,name)]+(['baseline'] if engine=='native' else [])


def contexts(runner, engine=None):
    if (engine or runner.config['engine'])=='native':return ('baseline_partner','self_team')
    return ('teacher_partner' if descriptor(runner) else 'astra_partner','self_team')


def bind_job(runner, job):
    """Pin each consumer before its immutable schedule is written."""
    if descriptor(runner) is None:return
    job['format']=runner.fmt
    job['teacher_roles']={name:descriptor(runner,name) for name in ROLES}
    actual=identities(runner,job['engine'])
    job['meta'].update(teacher_set=runner.manifest['teacher_set']['name'],teacher_roles=actual,
                       reference_teacher=actual['reward_reference'])
    name='reward_reference' if job['meta'].get('phase')=='reward_reference' else 'supervision'
    job['meta'].update(actual[name])
    job['rules_sha256']=runner.manifest['rules']['rules_sha256']
    if job['meta'].get('phase')=='teacher':
        job['timeout']=1;job['first_timeout']=10
    if job['engine']=='lite':
        job['bots']=[package(runner,'opponent') if bot=='baseline' else bot for bot in job['bots']]
        if job['meta'].get('context') in ('baseline_partner','astra_partner'):
            job['meta']['context']='teacher_partner'


def quota_matches(runner, result):
    if descriptor(runner) is None:return True
    meta=result.get('meta',{})
    expected=identity(runner,engine=meta.get('engine_id',result.get('engine','native')))
    return all(meta.get(key)==expected[key] for key in TEACHER_FIELDS)
