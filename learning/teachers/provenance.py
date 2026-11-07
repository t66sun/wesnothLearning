"""Teacher-label provenance without putting teacher answers into policy inputs."""
import hashlib
from functools import lru_cache

from .registry import DELIVERY, execution_identity, describe

TEACHER_SOURCES = ('astra', 'teacher')
ENGINE_FIELDS = ('engine', 'engine_version', 'rng_version', 'combat_version')
TEACHER_FIELDS = ('teacher_contract', 'teacher', 'teacher_profile', 'teacher_source_sha256',
                  'teacher_package_sha256', 'teacher_strategy', 'teacher_adapter_sha256',
                  'teacher_backend')


def is_teacher(row):
    return row.get('source') in TEACHER_SOURCES


def sampler_source(row):
    # Preserve legacy bucket ordering/RNG consumption and the 75/25 teacher/human
    # rule. The row itself retains its actual source and executable identity.
    return 'astra' if is_teacher(row) else row.get('source')


def engine_identity(engine):
    if engine == 'lite':
        from ..adapters import ENGINE_VERSION, RNG_VERSION, COMBAT_VERSION
        return dict(engine=engine, engine_version=ENGINE_VERSION,
                    rng_version=RNG_VERSION, combat_version=COMBAT_VERSION)
    if engine == 'native':
        return dict(engine=engine, engine_version='1.18.8',
                    rng_version='native-1.18.8', combat_version='native-1.18.8')
    raise ValueError('unsupported teacher backend')


@lru_cache(maxsize=12)
def _expected_identity(teacher, fmt, engine):
    from . import archive_bytes, identity
    if teacher == 'selected_teacher':
        spec = describe(DELIVERY/'selected_teacher.zip', fmt)
    elif teacher == 'gpt6astra':
        legacy = identity()
        spec = dict(teacher=teacher, profile=legacy['teacher_profile'],
                    source_sha256=legacy['teacher_source_sha256'], strategy='maintained_astra',
                    package_sha256=hashlib.sha256(archive_bytes()).hexdigest())
    else:
        raise ValueError('unknown teacher identity')
    return dict(engine_identity(engine), **execution_identity(spec, engine))


def expected_identity(teacher, fmt, engine):
    return dict(_expected_identity(teacher, fmt, engine))


def validate_identity(value, fmt):
    """Validate versioned execution metadata; legacy readers keep their own checks."""
    if value.get('teacher_contract') != 1:
        raise ValueError('unsupported or missing teacher identity contract')
    engine = value.get('teacher_backend')
    expected = expected_identity(value.get('teacher'), fmt, engine)
    if any(value.get(key) != expected[key] for key in TEACHER_FIELDS):
        raise ValueError('teacher execution identity differs')
    if any(value.get(key, expected[key]) != expected[key] for key in ENGINE_FIELDS):
        raise ValueError('teacher engine identity differs')
    if 'engine_id' in value and value['engine_id'] not in (engine, expected['engine_version'] if engine == 'lite' else 'native-1.18.8'):
        raise ValueError('teacher engine identity differs')
    if value.get('source') == 'astra' and value['teacher'] != 'gpt6astra':
        raise ValueError('search teacher cannot be labelled Astra')
    return expected


def require_rows_teacher(rows, expected_by_engine):
    """Changing teachers cannot inherit supervision or count it under a new name."""
    for row in rows:
        if not is_teacher(row):
            continue
        expected = expected_by_engine.get(row.get('teacher_backend'))
        if expected is None or any(row.get(key) != expected.get(key) for key in TEACHER_FIELDS):
            raise ValueError('supervision belongs to a different frozen teacher')


def metadata(value):
    keys = TEACHER_FIELDS if value.get('teacher_contract') else (
        'teacher', 'teacher_profile', 'teacher_source_sha256', 'teacher_parent_sha256')
    return {key: value.get(key) for key in keys}
