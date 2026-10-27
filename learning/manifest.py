from pathlib import Path
import importlib.metadata
import platform
import sys
from .common import ROOT, write_json, sha256
from .features import schema
from .model import ARCHITECTURE,Policy
from .updates import BATCH_CONTRACT
from .rowpack import ROW_SCHEMA
import native


def output_path(value):
    path=Path(value)
    path=(ROOT/path).resolve() if not path.is_absolute() else path.resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError('output must be inside WesnothLearning: '+str(path))
    return path


def tree_hashes(directory):
    root=Path(directory)
    return {p.relative_to(root).as_posix():sha256(p) for p in sorted(root.rglob('*'))
            if p.is_file() and not {'__pycache__','target','.pytest_cache'}.intersection(p.parts) and p.suffix!='.pyc'}


def dependency_versions():
    versions={}
    for name in ('torch','numpy','lupa','matplotlib'):
        try: versions[name]=importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: versions[name]=None
    return dict(python=sys.version,platform=platform.platform(),packages=versions)


def teacher_identity(kind):
    """Registered label capabilities; a native engine is not a query capability."""
    common=dict(kind=kind,version='1.18.8',rules_sha256=schema()['rules_sha256'],capture_sha256=None)
    if kind=='wesnoth_default_rca':
        return dict(common,query='none',action_source='engine_events')
    if kind=='gpt6astra':
        from .teachers import source_digest
        return dict(common,query='per_decision',action_source='lua_wrapper',source_sha256=source_digest())
    raise ValueError('unknown teacher kind: '+str(kind))


def active_teacher(manifest):
    record=manifest.get('teacher',{})
    if not isinstance(record,dict) or not record.get('kind'):
        raise ValueError('legacy teacher manifest requires the original frozen sources')
    expected=teacher_identity(record['kind'])
    if any(record.get(key)!=expected[key] for key in ('version','query','action_source')):
        raise ValueError('teacher identity declares an unsupported capability')
    if manifest.get('rules') and record.get('rules_sha256')!=manifest['rules']['rules_sha256']:
        raise ValueError('teacher rules differ from the frozen run')
    if record['kind']=='wesnoth_default_rca' and manifest.get('baseline') and record.get('runtime_sha256')!=manifest['baseline']['sha256']:
        raise ValueError('stock teacher runtime differs from the frozen baseline')
    return dict(record)


def freeze(run_dir, opponents, wesnoth, config):
    if config.get('evaluation_engine','native')!='native':
        raise ValueError('stock RCA reference evaluation is native-only')
    run_dir=Path(run_dir)
    (run_dir/'frozen/opponents').mkdir(parents=True)
    exe=native.find_wesnoth(wesnoth)
    versions=dependency_versions()
    if not str(versions['packages']['torch']).startswith('2.9.1'):
        raise ValueError('PyTorch 2.9.1 is required; run setup.sh')
    from .rules_catalog import load, resolve_dir
    rules_dir=resolve_dir(config.get('rules_dir'))
    catalog=load(rules_dir)
    teacher=teacher_identity('wesnoth_default_rca')
    teacher.update(rules_sha256=catalog['rules_file_sha256'],runtime_sha256=sha256(exe))
    manifest=dict(schema=4,config=config,features=schema(),architecture=ARCHITECTURE,
        batch_contract=BATCH_CONTRACT,
        row_schema=ROW_SCHEMA,
        rules=dict(directory=str(rules_dir),rules_sha256=catalog['rules_file_sha256'],
                   source_hash=catalog['source_hash'],training_acceptance=catalog.get('training_acceptance')),
        parameters=sum(p.numel() for p in Policy('duel').parameters()),dependencies=versions,
        opponents=[],baseline=dict(name='baseline',version='1.18.8',path=exe,sha256=sha256(exe)),
        teacher=teacher,
        rehearsal_policy=dict(bc='teacher_initialisation',ppo='exclude_evaluation_control'),
        source={folder:tree_hashes(ROOT/folder) for folder in ('learning','lua','vendor/arena','engine_lite','rules','benchmarks')},
        baseline_in_2v2=dict(teacher_partner=True,rollout_partner_fraction=.25,
                             opponent_pool=True,control_candidate=True,
                             evaluation_contexts=['baseline_partner','self_team']))
    write_json(run_dir/'manifest.json',manifest)
    return manifest,['baseline']


def verify_frozen(manifest):
    if manifest.get('batch_contract') != BATCH_CONTRACT:
        raise ValueError('legacy batch eligibility requires the original frozen sources; '
                         'use a new run for the scenario-v2 contract')
    active_teacher(manifest)
    if manifest.get('rules'):
        from .rules_catalog import load
        frozen=manifest['rules'];current=load(frozen['directory'])
        if current['rules_file_sha256']!=frozen['rules_sha256'] or current['source_hash']!=frozen['source_hash']:
            raise ValueError('frozen rules changed since the experiment started')
        if schema()['rules_sha256']!=frozen['rules_sha256']:
            raise ValueError('feature vocabulary differs from the frozen rules')
    for opponent in manifest['opponents']:
        if sha256(opponent['path'])!=opponent['sha256']:
            raise ValueError('frozen opponent changed: '+opponent['path'])
    if sha256(manifest['baseline']['path'])!=manifest['baseline']['sha256']:
        raise ValueError('official runtime changed since the experiment started')
    for folder,hashes in manifest['source'].items():
        if tree_hashes(ROOT/folder)!=hashes:
            raise ValueError('source changed since the experiment started: '+folder)
