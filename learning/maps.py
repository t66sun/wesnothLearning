"""Frozen native maps; held-out layouts never enter training or reward calibration."""
from pathlib import Path
import hashlib
import json
from .common import ROOT

SPLITS={
    'duel':dict(train=('the_freelands','weldyn_channel','sablestone_delta'),validation=('hamlets',),holdout=('caves_of_the_basilisk','ruined_passage')),
    'ffa4':dict(train=('clash','isars_cross'),validation=('loris_river',),holdout=('morituri',)),
    'team2v2':dict(train=('clash','isars_cross'),validation=('loris_river',),holdout=('morituri',)),
}

SPLIT_RULE = 'scenario-v2'


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def scenario_identity(job):
    """Identify the physical starting scenario, independent of run seed or paths."""
    from .adapters import COMBAT_VERSION, ENGINE_VERSION
    from .features import schema

    meta = job.get('meta', {})
    board = job['map_override']
    engine = job.get('engine', 'lite')
    rules = meta.get('rules_sha256') or meta.get('rules_version')
    if rules is None and job.get('rules_dir'):
        directory = Path(job['rules_dir'])
        path = directory / 'catalog-summary.json'
        if not path.exists():
            path = directory / 'catalog.json'
        rules = json.loads(path.read_text(encoding='utf-8'))['rules_file_sha256']
    identity = dict(format=meta.get('format'),
                    board=dict(terrain=board['terrain'], starts=board['starts'],
                               width=board.get('width', len(board['terrain'][0])),
                               height=board.get('height', len(board['terrain']))),
                    factions=job['factions'], teams=job.get('teams'),
                    engine_id=meta.get('engine_version', ENGINE_VERSION if engine == 'lite' else 'native-1.18.8'),
                    combat_version=meta.get('combat_version', COMBAT_VERSION if engine == 'lite' else 'native-1.18.8'),
                    rules_version=rules or schema()['rules_sha256'],
                    max_turns=job.get('max_turns', 30), fog=job.get('fog', True),
                    shroud=job.get('shroud', False), share_view=job.get('share_view', True),
                    share_maps=job.get('share_maps', True))
    if job.get('game_spec'):
        identity['initial_spec'] = {key: value for key, value in job['game_spec'].items()
                                    if key not in ('seed', 'allow_approximate')}
    return identity


def scenario_family(job):
    return _digest(scenario_identity(job))


def run_family(job):
    """Preserve the original seed-bearing family bytes for existing consumers."""
    meta = job['meta']
    return _digest(dict(format=meta['format'], map=meta['map_sha256'], seed=job['seed'],
                        factions=job['factions'], teams=job.get('teams')))


def bind_scenario(job):
    """Refresh after engine/rules overrides, before freezing the schedule."""
    job['scenario_family'] = scenario_family(job)
    job['split_rule'] = SPLIT_RULE
    return job


def freeze_map(source,name,output=None,catalog=None):
    """Convert a genuine native .map; the distribution inventory proves its version."""
    import re
    source=Path(source);raw=source.read_bytes();text=raw.decode('utf-8-sig')
    if not re.fullmatch(r'[a-z0-9_]+',name): raise ValueError('map name must be a lowercase slug')
    provenance=json.loads(Path(catalog or ROOT/'data/rules/1.18.8/catalog.json').read_text(encoding='utf-8'))
    digest=hashlib.sha256(raw).hexdigest()
    inventories=[entry.get('source_manifest',{}).get('files',{}) for entry in provenance.get('captures',[])]
    if provenance.get('source_version')!='1.18.8' or not any(digest in inventory.values() for inventory in inventories):
        raise ValueError('map source is absent from the frozen 1.18.8 distribution inventory')
    border=1;terrain=[];starts={}
    for line in text.splitlines():
        line=line.strip()
        if not line or line.startswith('#'): continue
        if '=' in line and ',' not in line:
            key,value=line.split('=',1)
            if key.strip()=='border_size': border=int(value)
            continue
        row=[]
        for x,cell in enumerate(line.split(',')):
            match=re.fullmatch(r'\s*(?:(\d+)\s+)?([^\s,]+)\s*',cell)
            if not match: raise ValueError('invalid native map cell')
            side,code=match.groups();row.append(code)
            if side: starts[int(side)]=[x+1-border,len(terrain)+1-border]
        terrain.append(row)
    if not terrain or any(len(row)!=len(terrain[0]) for row in terrain): raise ValueError('native map must be rectangular')
    if border: terrain=[row[border:-border] for row in terrain[border:-border]]
    if not starts or sorted(starts)!=list(range(1,len(starts)+1)): raise ValueError('map needs contiguous starting positions')
    height=len(terrain);width=len(terrain[0])
    if any(not 1<=x<=width or not 1<=y<=height for x,y in starts.values()): raise ValueError('starting position outside playable map')
    data=dict(native_version='1.18.8',name=name,source_path=str(source.resolve()),source_sha256=digest,
        board=dict(width=width,height=height,terrain=terrain,starts=[starts[i] for i in sorted(starts)]))
    from .common import write_json
    path=Path(output or ROOT/'data/rules/1.18.8/maps')/(name+'.json')
    if path.exists(): raise FileExistsError(path)
    write_json(path,data);return path


def frozen_map(name):
    path=ROOT/'data/rules/1.18.8/maps'/(name+'.json')
    if not path.exists(): raise ValueError(f'missing frozen 1.18.8 map: {path}; export it before collecting')
    data=json.loads(path.read_text(encoding='utf-8'))
    if data.get('native_version')!='1.18.8' or not data.get('source_sha256'):
        raise ValueError('map lacks native version/source hash: '+name)
    board=data['board']
    if len(board['terrain'])!=board['height'] or any(len(row)!=board['width'] for row in board['terrain']): raise ValueError('invalid map dimensions')
    return board,hashlib.sha256(path.read_bytes()).hexdigest()


def decorate(job,format_name,index,phase):
    if phase=='train' and index%2==0:
        from .common import VENDOR
        path=VENDOR/'maps'/f'arena{len(job["bots"])}.json'
        board=json.loads(path.read_text(encoding='utf-8'));digest=hashlib.sha256(path.read_bytes()).hexdigest();name=path.stem
    else:
        split='train' if phase=='train' else 'holdout' if phase=='final' else 'validation'
        names=SPLITS[format_name][split];name=names[(index//2 if split=='train' else index)%len(names)]
        board,digest=frozen_map(name)
    job['map_override']=board
    job.setdefault('meta',{}).update(format=format_name,map=name,map_sha256=digest,map_partition=phase)
    job['game_family']=run_family(job)
    if phase=='train': job['max_turns']=60
    return bind_scenario(job)
